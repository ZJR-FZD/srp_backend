#!/usr/bin/env python3
"""
ESP32 BLE Beacon配置代码生成器

根据Room Agent配置生成ESP32端的beacon配置代码
"""

import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import yaml
from config.room_mapping import ROOM_NAMES, get_major_for_room


def generate_esp32_beacon_config(room_config_path: str) -> str:
    """生成ESP32 beacon配置代码

    Args:
        room_config_path: Room Agent配置文件路径

    Returns:
        str: 生成的C代码
    """
    # 加载Room Agent配置
    config_path = Path(project_root) / room_config_path
    with open(config_path, 'r') as f:
        room_config = yaml.safe_load(f)

    # 提取beacon配置
    agent_config = room_config.get("agent", {})
    beacon_config = room_config.get("beacon", {})

    room_id = agent_config.get("room_id")
    room_name_cn = ROOM_NAMES.get(room_id, room_id)
    major = beacon_config.get("major")
    minor = beacon_config.get("minor", 0)
    interval = beacon_config.get("interval", 1)
    measured_power = beacon_config.get("measured_power", -59)

    # 解析UUID为字节数组
    uuid_str = beacon_config.get("uuid", "")
    uuid_bytes = []
    if uuid_str:
        # 移除连字符
        uuid_clean = uuid_str.replace("-", "")
        for i in range(0, len(uuid_clean), 2):
            uuid_bytes.append(f"0x{uuid_clean[i:i+2]}")

    # 生成C代码
    code = f"""/*
 * ESP32 BLE Beacon配置
 * 自动生成 - 基于: {room_config_path}
 * 房间: {room_name_cn} ({room_id})
 * 生成时间: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
 */

#ifndef ESP32_BEACON_CONFIG_H
#define ESP32_BEACON_CONFIG_H

#ifdef __cplusplus
extern "C" {{
#endif

// ========== BLE Beacon参数 ==========

// 系统UUID（16字节）- 所有房间共享
static const uint8_t BEACON_UUID[16] = {{
    {", ".join(uuid_bytes)}
}};

// 房间ID（Major值）- 对应{room_name_cn}}
#define BEACON_MAJOR_ROOM    {major}

// 区域/位置（Minor值）
#define BEACON_MINOR_ZONE    {minor}

// 校准RSSI值（1米处）
#define BEACON_MEASURED_POWER  {measured_power}

// 广播间隔（毫秒）
#define BEACON_INTERVAL_MS    {interval * 1000}

// ========== 房间信息 ==========

#define ROOM_ID_STR         "{room_id}"
#define ROOM_NAME_CN_STR    "{room_name_cn}"
#define ROOM_NAME_EN_STR    "{room_id}"

// ========== BLE Beacon配置结构 ==========

typedef struct {{
    const uint8_t *uuid;          // 16字节UUID
    uint16_t major;              // 房间ID (0-65535)
    uint16_t minor;              // 区域ID (0-65535)
    int8_t measured_power;      // RSSI校准值
    uint16_t interval_ms;       // 广播间隔
}} beacon_config_t;

// 默认配置（使用宏定义）
static const beacon_config_t default_beacon_config = {{
    .uuid = BEACON_UUID,
    .major = BEACON_MAJOR_ROOM,
    .minor = BEACON_MINOR_ZONE,
    .measured_power = BEACON_MEASURED_POWER,
    .interval_ms = BEACON_INTERVAL_MS,
}};

// ========== 辅助函数 ==========

/**
 * 获取beacon配置
 */
inline const beacon_config_t* get_beacon_config(void) {{
    return &default_beacon_config;
}}

/**
 * 打印beacon配置信息（调试用）
 */
inline void print_beacon_config(void) {{
    printf("\\n========== ESP32 BLE Beacon配置 ==========");
    printf("房间: %s (%s)\\n", ROOM_NAME_CN_STR, ROOM_ID_STR);
    printf("Major (房间ID): %u\\n", BEACON_MAJOR_ROOM);
    printf("Minor (区域ID): %u\\n", BEACON_MINOR_ZONE);
    printf("Measured Power: %d dBm\\n", BEACON_MEASURED_POWER);
    printf("Interval: %u ms\\n", BEACON_INTERVAL_MS);
    printf("UUID: ");
    for (int i = 0; i < 16; i++) {{
        printf("%02X", BEACON_UUID[i]);
        if (i == 3 || i == 7 || i == 11)
            printf("-");
    }}
    printf("\\n==========================================\\n\\n");
}}

#ifdef __cplusplus
}}
#endif

#endif // ESP32_BEACON_CONFIG_H
"""

    return code


def generate_esp32_main_snippet(room_config_path: str) -> str:
    """生成ESP32主程序代码片段

    Args:
        room_config_path: Room Agent配置文件路径

    Returns:
        str: 生成的C代码片段
    """
    import datetime

    # 加载配置
    config_path = Path(project_root) / room_config_path
    with open(config_path, 'r') as f:
        room_config = yaml.safe_load(f)

    agent_config = room_config.get("agent", {})
    beacon_config = room_config.get("beacon", {})

    room_id = agent_config.get("room_id")
    major = beacon_config.get("major")

    code = f"""/*
 * ESP32主程序 - BLE Beacon广播
 * 房间: {room_id}
 */

#include "esp_log.h"
#include "esp32_beacon_config.h"  // 使用生成的配置头文件
#include "esp_gap_ble_api.h"
#include "esp_wifi.h"

static const char *TAG = "ESP32_BEACON";

// 外设句柄
static uint16_t ble_beacon_gap_handle = 0;

// Beacon参数（从配置文件加载）
static esp_ble_beacon_data_t beacon_data = {{
    .set_min_adv_interval_ms = {beacon_config.get('interval', 1) * 1000},
    .set_max_adv_interval_ms = {beacon_config.get('interval', 1) * 1000},
}};

// 广播数据（iBeacon格式）
static uint8_t beacon_payload[25] = {{
    // Flags
    0x02, 0x01,
    // UUID (16字节)
    0x12, 0x23, 0x45, 0x67, 0x89, 0xAB, 0xCD, 0xEF,
    0x01, 0x23, 0x45, 0x67, 0x89, 0xAB, 0xCD, 0xEF,
    // Major (房间ID) - 小端序
    (uint8_t)({major} & 0xFF),
    (uint8_t)({major} >> 8),
    // Minor (区域ID) - 小端序
    (uint8_t)({beacon_config.get('minor', 0)} & 0xFF),
    (uint8_t)({beacon_config.get('minor', 0)} >> 8),
    // Measured Power
    {beacon_config.get('measured_power', -59)}
}};

void app_main(void)
{{
    ESP_LOGI(TAG, "初始化ESP32 BLE Beacon...");
    ESP_LOGI(TAG, "房间ID: %u, Major: %u", {major}, {major});

    // 打印配置
    print_beacon_config();

    // 初始化BLE
    ESP_ERROR_CHECK(esp_nvic_alloc_irq_handler(BLE_DYNAMIC_IRQ, ESP_IRQ_PRIORITY_DEFAULT, NULL, NULL, 0));

    // 初始化GAP
    esp_ble_beacon_config_t ble_beacon_cfg = {{
        .beacon_type = BEACON_TYPE_IBEACON,
    }};

    ESP_ERROR_CHECK(
        esp_ble_beacon_config(&ble_beacon_cfg) == ESP_OK,
        "配置BLE Beacon失败"
    );

    // 设置广播参数
    ESP_ERROR_CHECK(
        esp_ble_beacon_start(&ble_beacon_gap_handle, &beacon_data) == ESP_OK,
        "启动BLE Beacon失败"
    );

    // 设置广播数据
    struct esp_ble_beacon_data  beacon_data_struct = {{
        .flag = 0x4,
        .uuid_size = 16,
        .uuid = beacon_config.uuid,
        .major = beacon_config.major,
        .minor = beacon_config.minor,
        .power = beacon_config.measured_power,
    }};

    ESP_ERROR_CHECK(
        esp_ble_beacon_set_data(&ble_beacon_gap_handle, &beacon_data_struct) == ESP_OK,
        "设置BLE Beacon数据失败"
    );

    ESP_LOGI(TAG, "BLE Beacon启动成功");
    ESP_LOGI(TAG, "正在广播beacon信号...");
    ESP_LOGI(TAG, "房间: %s, Major: %u, Minor: %u",
              "{room_id}", {major}, {beacon_config.get('minor', 0)});

    // 保持运行
    while (1) {{
        vTaskDelay(pdMS_TO_TICKS({beacon_config.get('interval', 1) * 1000));
    }}
}}
"""

    return code


def generate_esp32_sdk_config(room_config_path: str) -> str:
    """生成ESP-IDF SDK配置文件

    Args:
        room_config_path: Room Agent配置文件路径

    Returns:
        str: sdkconfig.defaults内容
    """
    # 加载配置
    config_path = Path(project_root) / room_config_path
    with open(config_path, 'r') as f:
        room_config = yaml.safe_load(f)

    agent_config = room_config.get("agent", {})
    beacon_config = room_config.get("beacon", {})

    room_id = agent_config.get("room_id")
    major = beacon_config.get("major")

    config = f"""# ESP-IDF SDK配置文件
# 对应Room Agent配置: {room_config_path}

# 房间配置
CONFIG_ROOM_ID="{room_id}"
CONFIG_ROOM_MAJOR={major}
CONFIG_ROOM_MINOR={beacon_config.get('minor', 0)}

# BLE Beacon配置
CONFIG_BEACON_ENABLED=y
CONFIG_BEACON_INTERVAL={beacon_config.get('interval', 1)}

# WiFi配置（根据实际网络修改）
CONFIG_ESP_WIFI_SSID="YourWiFiSSID"
CONFIG_ESP_WIFI_PASSWORD="YourWiFiPassword"

# MQTT配置（可选：ESP32作为MQTT客户端）
CONFIG_MQTT_ENABLED=n
# CONFIG_MQTT_BROKER_URI="mqtt://192.168.1.100:1883"

# 日志级别
CONFIG_LOG_DEFAULT_LEVEL_INFO=1
"""

    return config


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(
        description="生成ESP32 BLE Beacon配置代码"
    )
    parser.add_argument(
        "--config",
        default="config/room_agent.yaml",
        help="Room Agent配置文件路径"
    )
    parser.add_argument(
        "--output",
        help="输出目录（默认：esp32_beacon_config/）"
    )
    parser.add_argument(
        "--type",
        choices=["header", "main", "sdkconfig", "all"],
        default="all",
        help="生成的代码类型"
    )

    args = parser.parse_args()

    # 确定输出目录
    if args.output:
        output_dir = Path(args.output)
    else:
        output_dir = Path(project_root) / "esp32_beacon_config"

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"📄 读取配置: {args.config}")
    print(f"📝 输出目录: {output_dir}")

    # 生成代码
    if args.type in ["header", "all"]:
        header_code = generate_esp32_beacon_config(args.config)
        header_path = output_dir / "esp32_beacon_config.h"
        with open(header_path, 'w') as f:
            f.write(header_code)
        print(f"✅ 生成头文件: {header_path}")

    if args.type in ["main", "all"]:
        main_code = generate_esp32_main_snippet(args.config)
        main_path = output_dir / "main_beacon.c"
        with open(main_path, 'w') as f:
            f.write(main_code)
        print(f"✅ 生成主程序: {main_path}")

    if args.type in ["sdkconfig", "all"]:
        sdk_config = generate_esp32_sdk_config(args.config)
        sdk_path = output_dir / "sdkconfig.defaults"
        with open(sdk_path, 'w') as f:
            f.write(sdk_config)
        print(f"✅ 生成SDK配置: {sdk_path}")

    # 生成README
    readme_content = f"""# ESP32 BLE Beacon配置文件

## 生成时间
{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## 对应Room Agent配置
{args.config}

## 文件说明

### esp32_beacon_config.h
Beacon配置头文件，包含：
- 系统UUID（16字节）
- 房间ID（Major值）
- 区域ID（Minor值）
- RSSI校准值
- 广播间隔

使用方法：
1. 将此文件复制到ESP32项目的`include/`目录
2. 在ESP32代码中`#include "esp32_beacon_config.h"`
3. 调用`get_beacon_config()`获取配置

### main_beacon.c
完整的BLE Beacon广播示例代码。
包含：
- BLE初始化
- Beacon参数设置
- 广播数据设置
- 主循环

使用方法：
1. 将此文件添加到ESP32项目的`main/`目录
2. 修改`CMakeLists.txt`添加源文件
3. 编译并烧录

### sdkconfig.defaults
ESP-IDF SDK配置文件。
包含编译时配置选项。

使用方法：
1. 将此文件复制到ESP32项目根目录
2. 重新配置项目：`idf.py reconfigure`
3. 编译项目：`idf.py build`

## 烧录命令示例

```bash
# 配置项目
cd ~/esp/esp32-beacon
idf.py reconfigure

# 编译
idf.py build

# 烧录（根据实际端口修改）
idf.py -p /dev/ttyUSB0 flash

# 监视串口
idf.py -p /dev/ttyUSB0 monitor
```

## 验证Beacon

使用BLE扫描工具验证：

```bash
# Linux
hcitool lescan | grep {room_id}

# macOS
bleutil scan
```

应该看到：
- UUID: 系统UUID
- Major: 房间ID值
- Minor: 0
- RSSI: 信号强度

## 联动Room Agent

1. 确保Room Agent配置文件正确
2. 运行验证脚本：
   ```bash
   python3 scripts/validate_beacon_binding.py --config {args.config}
   ```
3. 启动Room Agent：
   ```bash
   python3 main_room_agent.py
   ```

## 故障排查

### 问题：扫描不到beacon
1. 检查ESP32供电
2. 检查ESP32固件是否正常运行
3. 使用串口监视查看ESP32日志

### 问题：Room ID不匹配
1. 检查ESP32的Major值
2. 检查Room Agent的room_id
3. 运行验证脚本

### 问题：RSSI信号弱
1. 调整ESP32发射功率
2. 调整measured_power校准值
3. 减少beacon与接收器距离
"""

    readme_path = output_dir / "README.md"
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    print(f"✅ 生成README: {readme_path}")

    print(f"\n✅ 配置文件生成完成！")
    print(f"📁 输出目录: {output_dir.absolute()}")
    print(f"\n下一步：")
    print(f"  1. 查看README: {readme_path}")
    print(f"  2. 复制文件到ESP32项目")
    print(f"  3. 编译并烧录ESP32")
    print(f"  4. 验证beacon信号")
    print(f"  5. 运行验证脚本：python3 scripts/validate_beacon_binding.py")


if __name__ == "__main__":
    import datetime
    sys.exit(main())
