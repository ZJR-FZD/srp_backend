#!/usr/bin/env python3
"""
ESP32 Beacon与Room Agent配置绑定验证脚本

验证ESP32 beacon配置与Room Agent配置是否匹配
"""

import sys
import yaml
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.room_mapping import ROOM_ID_MAPPING, ROOM_NAMES


def load_room_agent_config(config_path: str) -> dict:
    """加载Room Agent配置"""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def validate_beacon_binding(room_config: dict) -> tuple[bool, list[str]]:
    """验证beacon绑定配置

    Args:
        room_config: Room Agent配置字典

    Returns:
        tuple[bool, list[str]]: (是否有效, 错误列表）
    """
    errors = []

    # 提取配置
    agent_config = room_config.get("agent", {})
    beacon_config = room_config.get("beacon", {})

    room_id = agent_config.get("room_id")
    beacon_uuid = beacon_config.get("uuid")
    beacon_major = beacon_config.get("major")
    beacon_minor = beacon_config.get("minor")
    measured_power = beacon_config.get("measured_power")
    interval = beacon_config.get("interval")

    # 验证1: room_id必须存在
    if not room_id:
        errors.append("❌ 缺少room_id配置")
    elif room_id not in ROOM_ID_MAPPING:
        errors.append(f"❌ 未知的room_id: {room_id}")

    # 验证2: beacon.major必须与room_id对应
    if room_id and beacon_major is not None:
        expected_major = ROOM_ID_MAPPING.get(room_id)
        if beacon_major != expected_major:
            errors.append(
                f"❌ beacon.major配置错误: 期望{expected_major} (对应{room_id}), 实际{beacon_major}"
            )

    # 验证3: UUID格式
    if beacon_uuid:
        try:
            import uuid as uuid_lib
            uuid_obj = uuid_lib.UUID(beacon_uuid)
            print(f"✅ UUID格式正确: {beacon_uuid}")
        except ValueError:
            errors.append(f"❌ UUID格式错误: {beacon_uuid}")

    # 验证4: Major范围
    if beacon_major is not None:
        if not (0 <= beacon_major <= 65535):
            errors.append(f"❌ beacon.major超出范围(0-65535): {beacon_major}")
        else:
            print(f"✅ beacon.major有效: {beacon_major}")

    # 验证5: Minor范围
    if beacon_minor is not None:
        if not (0 <= beacon_minor <= 65535):
            errors.append(f"❌ beacon.minor超出范围(0-65535): {beacon_minor}")
        else:
            print(f"✅ beacon.minor有效: {beacon_minor}")

    # 验证6: Measured Power范围
    if measured_power is not None:
        if not (-100 <= measured_power <= 0):
            errors.append(f"❌ measured_power超出范围(-100到0): {measured_power}")
        else:
            print(f"✅ measured_power有效: {measured_power} dBm")

    # 验证7: Interval范围
    if interval is not None:
        if interval < 1:
            errors.append(f"❌ interval必须>=1秒: {interval}")
        else:
            print(f"✅ interval有效: {interval}秒")

    # 验证8: ESP32设备标识（如果有）
    esp32_device_id = beacon_config.get("esp32_device_id")
    if esp32_device_id:
        print(f"✅ ESP32设备ID: {esp32_device_id}")

    return (len(errors) == 0, errors)


def print_binding_summary(room_config: dict):
    """打印绑定摘要"""
    agent_config = room_config.get("agent", {})
    beacon_config = room_config.get("beacon", {})

    room_id = agent_config.get("room_id")
    agent_id = agent_config.get("id")
    beacon_uuid = beacon_config.get("uuid")
    beacon_major = beacon_config.get("major")

    print("\n" + "="*60)
    print("📱 ESP32 Beacon 与 Room Agent 绑定摘要")
    print("="*60)

    print(f"\n房间信息:")
    print(f"  Room ID:      {room_id}")
    print(f"  Room Name:    {ROOM_NAMES.get(room_id, 'Unknown')}")
    print(f"  Agent ID:     {agent_id}")

    print(f"\nBeacon配置:")
    print(f"  UUID:         {beacon_uuid}")
    print(f"  Major (房间): {beacon_major} → {room_id}")
    print(f"  Minor (区域): {beacon_config.get('minor')}")
    print(f"  Measured Power: {beacon_config.get('measured_power')} dBm")
    print(f"  Interval:      {beacon_config.get('interval')}秒")

    print(f"\nESP32配置提示:")
    print(f"  #define ROOM_ID {beacon_major}")
    print(f"  // 或在NVS存储中设置: room_id = {beacon_major}")

    print("\n" + "="*60)


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(
        description="验证ESP32 Beacon与Room Agent配置绑定"
    )
    parser.add_argument(
        "--config",
        default="config/room_agent.yaml",
        help="Room Agent配置文件路径"
    )

    args = parser.parse_args()

    # 加载配置
    config_path = Path(project_root) / args.config
    if not config_path.exists():
        print(f"❌ 配置文件不存在: {config_path}")
        return 1

    print(f"📄 读取配置文件: {config_path}")

    try:
        room_config = load_room_agent_config(str(config_path))
    except Exception as e:
        print(f"❌ 加载配置文件失败: {e}")
        return 1

    # 验证配置
    is_valid, errors = validate_beacon_binding(room_config)

    # 打印摘要
    print_binding_summary(room_config)

    # 打印错误
    if errors:
        print("\n❌ 发现配置错误:")
        for error in errors:
            print(f"  {error}")
        print("\n请修复配置后重新运行验证")
        return 1
    else:
        print("\n✅ 配置验证通过！ESP32 Beacon与Room Agent配置匹配。")
        return 0


if __name__ == "__main__":
    sys.exit(main())
