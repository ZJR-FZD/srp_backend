# ESP32 BLE Beacon 与 Room Agent 绑定联动方案

## 概述

本方案实现ESP32广播的BLE Beacon与Room Agent的配置绑定，使Personal Agent能够：
1. 通过BLE Beacon识别当前房间（基于RSSI）
2. 通过mDNS发现对应Room Agent的MQTT Broker
3. 建立MQTT连接进行设备控制

---

## 架构流程

```
ESP32 (BLE Beacon)          Personal Agent              Room Agent (Python)
┌─────────────────┐          ┌──────────┐           ┌──────────────┐
│  Broadcast BLE   │  RSSI   │  Scan BLE │  mDNS   │  Advertise   │
│  Beacon Signal  │─────────▶│  Beacons  │─────────▶│  _room-agent  │
│                 │  -70dBm  │           │  Query  │  .tcp.local  │
│  UUID: SYSTEM │          │  Extract  │         │              │
│  Major: ROOM_ID│          │  Major    │         │  MQTT Broker │
│  Minor: ZONE   │          │  (Room ID)│         │  localhost:1883│
└─────────────────┘          └──────────┘           └──────────────┘
```

---

## 绑定关系

### 核心绑定参数

| 参数 | ESP32 Beacon | Room Agent | 说明 |
|------|-------------|------------|------|
| **房间ID** | `major` 值 | `room_id` | 必须一致 |
| **系统UUID** | `uuid` (16字节) | - | 所有房间共享 |
| **位置标识** | `minor` 值 | - | 房间内的区域位置 |
| **RSSI阈值** | 硬件发射功率 | -59 dBm | 标准beacon校准值 |

### 房间ID映射表

| 房间名称 | Major值 | Room Agent room_id | ESP32设备标识 |
|---------|---------|------------------|----------------|
| 客厅 | 1 | livingroom | esp32-beacon-living |
| 卧室 | 2 | bedroom | esp32-beacon-bedroom |
| 厨房 | 3 | kitchen | esp32-beacon-kitchen |
| 浴室 | 4 | bathroom | esp32-beacon-bathroom |
| 书房 | 5 | study | esp32-beacon-study |

**范围**：0-65535（推荐使用1-255，便于管理）

---

## ESP32 端配置

### 1. Arduino代码配置示例

```cpp
// BLE Beacon配置 - 与Room Agent绑定
struct BeaconConfig {
    // 系统UUID（所有房间共享）
    uint8_t uuid[16] = {
        0x01, 0x23, 0x45, 0x67,
        0x89, 0xAB, 0xCD, 0xEF,
        0x01, 0x23, 0x45, 0x67,
        0x89, 0xAB, 0xCD, 0xEF
    };

    // 房间ID（与Room Agent的room_id对应）
    uint16_t major = ROOM_ID;  // 1=livingroom, 2=bedroom, etc.

    // 区域/位置（房间内的子区域）
    uint16_t minor = ZONE_ID;  // 0=主区域, 1=角落, etc.

    // 校准RSSI值（1米处）
    int8_t measured_power = -59;  // 标准iBeacon值

    // 广播间隔（毫秒）
    uint16_t interval = 1000;  // 1秒
};

// 房间ID定义（通过编译选项或配置文件设置）
#define ROOM_ID_LIVINGROOM  1
#define ROOM_ID_BEDROOM  2
#define ROOM_ID_KITCHEN  3
#define ROOM_ID_BATHROOM  4
#define ROOM_ID_STUDY  5

// 编译时选择房间
// #define ROOM_ID ROOM_ID_BEDROOM  // 取决于ESP32安装位置
```

### 2. ESP32编译/烧录方案

**方案A：编译时选择房间**
```bash
# 烧录到卧室ESP32
idf.py build --ROOM_ID=ROOM_ID_BEDROOM
idf.py flash --port /dev/ttyUSB0

# 烧录到客厅ESP32
idf.py build --ROOM_ID=ROOM_ID_LIVINGROOM
idf.py flash --port /dev/ttyUSB1
```

**方案B：运行时配置（通过串口/配置文件）**
```cpp
// 从NVS存储读取房间ID
esp_err_t err = nvs_open_from_partition("nvs", NVS_READONLY, &handle);
uint16_t room_id;
nvs_get_u16(handle, "room_id", &room_id);

// 动态设置beacon参数
beacon_config.major = room_id;
```

---

## Room Agent 端配置

### 1. 配置文件更新（`config/room_agent.yaml`）

```yaml
# Room Agent配置
agent:
  id: "room-agent-bedroom"
  room_id: "bedroom"        # 与ESP32的major对应
  version: "1.0.0"

# BLE Beacon配置（绑定到ESP32）
beacon:
  enabled: false            # Python端不需要广播（ESP32负责）
  # 以下配置用于验证和文档
  uuid: "01234567-89AB-CDEF-0123456789ABCDEF"  # 与ESP32一致
  major: 2                   # 对应卧室（与ESP32 major一致）
  minor: 0                   # 主区域
  measured_power: -59        # 与ESP32校准值一致
  interval: 1               # 与ESP32广播间隔一致
  # ESP32设备标识（可选，用于调试）
  esp32_device_id: "esp32-beacon-bedroom"
  esp32_mac: "XX:XX:XX:XX:XX:XX"  # ESP32实际MAC地址

# MQTT客户端配置
mqtt:
  broker:
    host: "localhost"
    port: 1883

# mDNS服务广播
mdns:
  service_name: "bedroom-room-agent"
  service_type: "_room-agent._tcp.local"
  mqtt_port: 1883
  mqtt_ws_port: 9001

# 心跳配置
heartbeat:
  interval: 30

# 能力
capabilities:
  - "device_control"
  - "scene_activation"
```

### 2. 房间ID映射表

为方便管理，创建房间ID映射表：

```python
# config/room_mapping.py
ROOM_ID_MAPPING = {
    # Room Agent room_id -> Beacon Major值
    "livingroom": 1,
    "bedroom": 2,
    "kitchen": 3,
    "bathroom": 4,
    "study": 5,

    # 反向映射
    1: "livingroom",
    2: "bedroom",
    3: "kitchen",
    4: "bathroom",
    5: "study",
}

# 房间名称（中文）
ROOM_NAMES = {
    "livingroom": "客厅",
    "bedroom": "卧室",
    "kitchen": "厨房",
    "bathroom": "浴室",
    "study": "书房",
}
```

---

## Personal Agent 集成流程

### 1. BLE Beacon扫描（识别房间）

```python
# Personal Agent代码示例
from core.room_agent.beacon.beacon_config import BeaconConfig

async def scan_and_detect_room():
    """扫描BLE beacons并识别当前房间"""
    scanner = BeaconScanner()
    beacons = await scanner.scan(duration_ms=5000)

    # 过滤：只关心系统UUID的beacons
    system_beacons = [
        b for b in beacons
        if b.uuid == SYSTEM_UUID
    ]

    # 按RSSI排序（最强的信号）
    system_beacons.sort(key=lambda b: b.rssi, reverse=True)

    # 获取最强beacon
    if system_beacons:
        strongest = system_beacons[0]

        # RSSI阈值判断（-70dBm以上认为在房间内）
        if strongest.rssi >= -70:
            # 提取Major值 → 获取房间ID
            room_id = ROOM_ID_MAPPING.get(strongest.major)

            # 检查磁滞（避免在边界频繁切换）
            if should_switch_room(room_id, strongest.rssi):
                current_room = room_id
                print(f"检测到在房间: {ROOM_NAMES[room_id]} (RSSI: {strongest.rssi} dBm)")

                # 下一步：发现该房间的Room Agent
                await discover_room_agent(room_id)
```

### 2. mDNS发现Room Agent

```python
import zeroconf

async def discover_room_agent(room_id: str):
    """通过mDNS发现房间的Room Agent"""
    zeroconf = zeroconf.Zeroconf()

    # 浏览_room-agent._tcp.local服务
    services = await zeroconf.async_browser(
        type_="_room-agent._tcp.local",
        handlers=[]
    )

    # 查找目标房间的Room Agent
    for service in services:
        info = service.info
        properties = info.properties

        # 验证room_id匹配
        if b"room_id" in properties:
            service_room_id = properties[b"room_id"].decode()
            if service_room_id == room_id:
                # 找到目标房间的Room Agent
                mqtt_host = info.parsed_addresses()[0]
                mqtt_port = int(properties[b"mqtt_port"].decode())

                print(f"找到Room Agent: {service.name}")
                print(f"  MQTT Broker: {mqtt_host}:{mqtt_port}")

                # 连接到MQTT Broker
                await connect_to_room_agent(mqtt_host, mqtt_port)
                break
```

### 3. MQTT连接和设备控制

```python
import paho.mqtt.client as mqtt

async def connect_to_room_agent(host: str, port: int):
    """连接到Room Agent的MQTT Broker"""
    client_id = f"personal-agent-{unique_id}"
    client = mqtt.Client(client_id)

    # 订阅控制主题
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print(f"成功连接到Room Agent ({host}:{port})")

            # 订阅该房间的设备状态
            client.subscribe(f"room/{current_room}/agent/+/state")

            # 发布控制消息
            control_device(client, "light_1", "on")

    def on_message(client, userdata, msg):
        print(f"收到消息: {msg.topic} -> {msg.payload}")

    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(host, port)
    client.loop_start()
```

---

## 部署检查清单

### ESP32端
- [ ] 确认每个ESP32的`major`值唯一
- [ ] 所有ESP32使用相同的系统UUID
- [ ] `measured_power`校准为标准值（-59 dBm）
- [ ] 广播间隔设置（推荐1秒）
- [ ] 固件包含房间ID配置

### Room Agent端
- [ ] `room_id`与对应ESP32的`major`值一致
- [ ] `beacon.uuid`与ESP32的系统UUID一致
- [ ] `beacon.major`与ESP32配置一致
- [ ] `beacon.minor`与ESP32配置一致
- [ ] `beacon.measured_power`与ESP32校准值一致
- [ ] MQTT broker正常运行
- [ ] mDNS服务广播正常

### Personal Agent端
- [ ] BLE扫描功能正常
- [ ] RSSI阈值配置（-70 dBm）
- [ ] 磁滞逻辑实现（5 dBm）
- [ ] 房间ID映射表正确
- [ ] mDNS发现功能正常
- [ ] MQTT客户端功能正常
- [ ] 错误处理和重连机制

---

## 调试和验证

### 1. ESP32 Beacon验证

```bash
# 使用BLE扫描工具验证ESP32 beacon
hcitool lescan | grep SYSTEM_UUID

# 应该看到：
# XX:XX:XX:XX:XX:XX UUID=01234567-89AB-CDEF-0123456789ABCDEF,Major=2,Minor=0,RSSI=-55
```

### 2. Room Agent配置验证

```bash
# 验证Room Agent mDNS服务
avahi-browse _room-agent._tcp.local

# 应该看到：
# + 卧室-room-agent IPv4 192.168.1.100:1883
#   hostname = [192.168.1.100]
#   address = [192.168.1.100]
#   port = [1883]
#   txt = ["room_id=bedroom" "mqtt_port=1883" ...]
```

### 3. Personal Agent端到端测试

```python
# 运行Personal Agent测试脚本
python tests/integration/test_personal_agent_beacon.py

# 预期输出：
# [INFO] 扫描到3个beacons
# [INFO] 最强信号: bedroom (RSSI: -55 dBm)
# [INFO] 找到Room Agent: bedroom-room-agent
# [INFO] MQTT Broker: 192.168.1.100:1883
# [INFO] 成功连接到Room Agent
# [INFO] 设备控制成功: light_1 = on
```

---

## 故障排查

### 问题：Personal Agent扫描不到beacon
**检查项**：
1. ESP32供电正常
2. BLE广播功能启用
3. Personal Agent蓝牙权限
4. UUID匹配（大小写敏感）

### 问题：RSSI不稳定
**解决方案**：
1. 增加磁滞（5 dBm）
2. 多次采样平均
3. 调整`measured_power`校准值
4. 调整ESP32发射功率

### 问题：mDNS发现失败
**检查项**：
1. Room Agent和Personal Agent在同一网络
2. 防火墙允许mDNS（UDP 5353）
3. `room_id`匹配
4. 服务名称格式正确

### 问题：MQTT连接失败
**检查项**：
1. Broker地址和端口正确
2. 网络连通性（`ping <host>`)
3. 认证配置（如果启用）
4. TLS配置（如果启用）

---

## 安全考虑

1. **UUID管理**：
   - 生产环境使用唯一系统UUID
   - 避免使用默认UUID

2. **房间ID验证**：
   - Room Agent验证`major`值在预期范围
   - Personal Agent验证房间ID映射

3. **mDNS安全**：
   - TXT记录不包含敏感信息
   - MQTT认证启用

4. **MQTT安全**：
   - 使用TLS加密
   - 强制用户名/密码认证
   - Topic访问控制

---

## 配置示例：完整系统

### 客厅配置
**ESP32**：
```cpp
#define ROOM_ID 1  // 客厅
```

**Room Agent** (`config/room_agent_livingroom.yaml`):
```yaml
agent:
  room_id: "livingroom"
  id: "room-agent-livingroom"

beacon:
  uuid: "01234567-89AB-CDEF-0123456789ABCDEF"
  major: 1
  minor: 0
```

### 卧室配置
**ESP32**：
```cpp
#define ROOM_ID 2  // 卧室
```

**Room Agent** (`config/room_agent_bedroom.yaml`):
```yaml
agent:
  room_id: "bedroom"
  id: "room-agent-bedroom"

beacon:
  uuid: "01234567-89AB-CDEF-0123456789ABCDEF"
  major: 2
  minor: 0
```

---

## 参考资源

- **iBeacon规范**: https://developer.apple.com/ibeacon/
- **ESP32 BLE**: https://docs.espressif.com/projects/esp32/ble
- **mDNS规范**: https://tools.ietf.org/html/rfc6762
- **MQTT规范**: https://mqtt.org/mqtt-specification/
- **HomeSystemAgent.md**: 项目根目录
