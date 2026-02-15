#!/usr/bin/env python3
"""测试MQTT连接脚本"""
import asyncio
import yaml
from core.room_agent.mqtt import MqttClientManager


async def test_mqtt_connection():
    """测试MQTT broker连接"""

    # 加载配置
    with open("config/room_agent_livingroom.yaml", "r") as f:
        config_data = yaml.safe_load(f)

    mqtt_config = config_data["mqtt"]["broker"]

    print("=" * 60)
    print("MQTT连接测试")
    print("=" * 60)
    print(f"Broker地址: {mqtt_config['host']}:{mqtt_config['port']}")
    print(f"用户名: {mqtt_config.get('username', 'None')}")
    print(f"密码: {'***' if mqtt_config.get('password') else 'None'}")
    print("=" * 60)

    # 创建MQTT客户端
    client = MqttClientManager(
        room_id="test-livingroom",
        agent_id="test-agent",
        broker_config=mqtt_config
    )

    # 测试连接
    print("\n[1/3] 正在连接到MQTT Broker...")
    connected = await client.connect()

    if connected:
        print("✓ MQTT连接成功!")

        # 测试发布
        print("\n[2/3] 测试发布消息...")
        try:
            client.client.publish(
                f"room-agent/test-livingroom/test",
                payload="Test message from connection test",
                qos=1
            )
            print("✓ 消息发布成功!")
        except Exception as e:
            print(f"✗ 消息发布失败: {e}")

        # 测试订阅
        print("\n[3/3] 测试订阅消息...")
        try:
            client.client.subscribe(f"room-agent/test-livingroom/#", qos=1)
            print("✓ 订阅成功!")
        except Exception as e:
            print(f"✗ 订阅失败: {e}")

        # 断开连接
        print("\n正在断开连接...")
        await client.disconnect()
        print("✓ 连接已断开")

        print("\n" + "=" * 60)
        print("所有测试通过! ✓")
        print("=" * 60)
        return True

    else:
        print("✗ MQTT连接失败!")
        print("\n可能的原因:")
        print("1. Broker地址或端口不正确")
        print("2. 网络连接问题")
        print("3. Broker需要认证但未配置")
        print("4. Broker服务未启动")
        print("\n请检查配置并重试")
        print("=" * 60)
        return False


if __name__ == "__main__":
    success = asyncio.run(test_mqtt_connection())
    exit(0 if success else 1)
