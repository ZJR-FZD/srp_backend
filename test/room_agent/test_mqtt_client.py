# tests/room_agent/test_mqtt_client.py
"""MQTT客户端管理器测试"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
import asyncio

from core.room_agent.mqtt.client_manager import MqttClientManager


class TestMqttClientManager:
    """MQTT客户端管理器测试"""

    @pytest.mark.asyncio
    async def test_init(self, mock_mqtt_config):
        """测试初始化"""
        manager = MqttClientManager(
            room_id="test-room",
            agent_id="test-agent",
            broker_config=mock_mqtt_config
        )

        assert manager.room_id == "test-room"
        assert manager.agent_id == "test-agent"
        assert manager.broker_host == "localhost"
        assert manager.broker_port == 1883
        assert not manager._connected

    @pytest.mark.asyncio
    async def test_connect_success(self, mock_mqtt_config):
        """测试成功连接"""
        manager = MqttClientManager(
            room_id="test-room",
            agent_id="test-agent",
            broker_config=mock_mqtt_config
        )

        # Mock paho.mqtt.client
        with patch('core.room_agent.mqtt.client_manager.mqtt.Client') as mock_client:
            mock_client.return_value = Mock()
            manager.client = mock_client.return_value

            # 模拟连接成功
            manager._connected = True

            # 测试连接
            result = await manager.connect()

            assert result is True
            assert manager._connected is True

    @pytest.mark.asyncio
    async def test_register_handler(self, mock_mqtt_config):
        """测试注册消息处理器"""
        manager = MqttClientManager(
            room_id="test-room",
            agent_id="test-agent",
            broker_config=mock_mqtt_config
        )

        # 创建mock处理器
        async def mock_handler(msg):
            pass

        # 注册处理器
        manager.register_handler("control", mock_handler)

        assert "control" in manager.message_handlers
        assert manager.message_handlers["control"] == mock_handler

    @pytest.mark.asyncio
    async def test_publish_state(self, mock_mqtt_config):
        """测试发布状态消息"""
        from core.room_agent.models import StateMessage

        manager = MqttClientManager(
            room_id="test-room",
            agent_id="test-agent",
            broker_config=mock_mqtt_config
        )

        # Mock client
        with patch('core.room_agent.mqtt.client_manager.mqtt.Client') as mock_client:
            mock_client.return_value = Mock()
            manager.client = mock_client.return_value
            manager._connected = True

            # 创建状态消息
            state_msg = StateMessage(
                message_id="test-001",
                timestamp="2024-01-01T12:00:00Z",
                agent_id="test-agent",
                devices=[],
                agent_status="operational"
            )

            # 测试发布（不会抛出异常）
            await manager.publish_state(state_msg)
