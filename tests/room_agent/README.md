# tests/room_agent/README.md
# Room Agent测试说明

本目录包含Room Agent模块的所有测试。

## 测试结构

```
tests/room_agent/
├── __init__.py
├── test_mqtt_client.py           # MQTT客户端管理器测试
├── test_mdns_advertiser.py       # mDNS广播器测试
├── test_device_registry.py       # 设备注册表测试
├── test_device_controller.py      # 设备控制器测试
├── test_room_agent_integration.py # Room Agent集成测试
├── test_beacon_config.py        # BLE Beacon配置测试
├── test_beacon_advertiser.py      # BLE Beacon广播器测试
├── test_room_agent_beacon_integration.py # Room Agent BLE Beacon集成测试
└── README.md                      # 本文件
```

## 运行测试

### 运行所有Room Agent测试
```bash
# 从项目根目录运行
pytest tests/room_agent/ -v

# 运行特定测试文件
pytest tests/room_agent/test_mqtt_client.py -v

# 查看测试覆盖率
pytest tests/room_agent/ --cov=core/room_agent --cov-report=html
```

## 测试覆盖范围

### MQTT客户端管理器
- ✅ 初始化测试
- ✅ 连接测试（成功/失败）
- ✅ 消息处理器注册测试
- ✅ 状态发布测试

### mDNS广播器
- ✅ 初始化测试
- ✅ 本地IP获取测试
- ✅ 启动/停止测试
- ✅ 运行状态测试

### 设备注册表
- ✅ 初始化测试
- ✅ 注册/注销设备测试
- ✅ 重复注册测试
- ✅ 设备查询测试

### 设备控制器
- ✅ 初始化测试
- ✅ MCP工具注册测试
- ✅ 设备控制测试
- ✅ 状态查询测试
- ✅ 设备列表测试

### Room Agent集成
- ✅ 初始化测试
- ✅ MQTT处理器注册测试
- ✅ MQTT控制消息处理测试
- ✅ 能力描述发布测试
- ✅ MCP工具注册测试

### BLE Beacon配置（Phase 3新增）
- ✅ BeaconConfig初始化测试
- ✅ UUID格式验证测试
- ✅ Major/Minor/Measured Power/Interval范围验证
- ✅ 字典转换测试

### BLE Beacon广播器（Phase 3新增）
- ✅ 初始化测试
- ✅ 启动测试（成功/禁用）
- ✅ 停止测试
- ✅ 运行状态测试
- ✅ 配置更新测试
- ✅ Beacon信息获取测试

### Room Agent BLE Beacon集成（Phase 3新增）
- ✅ RoomAgent包含BeaconAdvertiser测试
- ✅ 启动时Beacon启动测试
- ✅ 停止时Beacon停止测试
- ✅ Beacon禁用时不启动测试

## Mock策略

所有外部依赖都使用Mock：
- `paho.mqtt.client` - MQTT客户端
- `zeroconf.Zeroconf` - mDNS服务
- `bluepy.peripheral.Peripheral` - BLE外设
- MCP Manager - MCP管理器
- 设备实例 - MockDevice

## 持续添加

- [ ] MQTT连接重连测试
- [ ] MQTT消息路由错误处理测试
- [ ] 设备并发操作测试
- [ ] RoomAgent完整生命周期测试
