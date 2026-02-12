# tests/room_agent/test_room_agent_integration.py
"""Room Agent集成测试"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
import asyncio

from core.agent import RobotAgent
from core.room_agent.room_agent import RoomAgent


class TestRoomAgentIntegration:
    """Room Agent集成测试"""

    @pytest.mark.asyncio
    async def test_room_agent_init(self, mock_agent_config):
        """测试Room Agent初始化"""
        agent = RoomAgent(
            room_id="test-room",
            agent_config=mock_agent_config
        )

        assert agent.room_id == "test-room"
        assert agent.agent_id == "test-room-agent-1"
        assert isinstance(agent.device_registry, object)
        assert isinstance(agent.device_controller, object)
        assert isinstance(agent.mqtt_client, object)
        assert isinstance(agent.mdns_advertiser, object)

    @pytest.mark.asyncio
    async def test_register_mqtt_handlers(self, mock_agent_config):
        """测试MQTT处理器注册"""
        agent = RoomAgent(
            room_id="test-room",
            agent_config=mock_agent_config
        )

        # 注册处理器
        agent._register_mqtt_handlers()

        # 验证处理器已注册
        assert "control" in agent.mqtt_client.message_handlers
        assert "describe" in agent.mqtt_client.message_handlers

    @pytest.mark.asyncio
    async def test_mqtt_control_handler(self, mock_agent_config, event_loop):
        """测试MQTT控制消息处理"""
        from core.room_agent.models import ControlMessage

        agent = RoomAgent(
            room_id="test-room",
            agent_config=mock_agent_config
        )

        # 注册处理器
        agent._register_mqtt_handlers()

        # Mock device controller
        agent.device_controller.control_device = AsyncMock(
            return_value={"success": True, "result": "OK"}
        )

        # 创建控制消息
        control_msg = ControlMessage(
            message_id="test-001",
            timestamp="2024-01-01T12:00:00Z",
            source_agent="personal-agent-1",
            target_device="light_1",
            action="on",
            parameters={"brightness": 80}
        )

        # 获取处理器
        handler = agent.mqtt_client.message_handlers.get("control")

        # 执行处理器
        await handler(control_msg)

        # 验证设备控制器被调用
        agent.device_controller.control_device.assert_called_once_with(
            device_id="light_1",
            action="on",
            parameters={"brightness": 80}
        )

    @pytest.mark.asyncio
    async def test_publish_description(self, mock_agent_config):
        """测试发布能力描述"""
        agent = RoomAgent(
            room_id="test-room",
            agent_config=mock_agent_config
        )

        # Mock device controller
        agent.device_controller.list_device_capabilities = AsyncMock(
            return_value=[]
        )

        # Mock MQTT client
        agent.mqtt_client.publish_description = AsyncMock()

        # 测试发布
        await agent._publish_description()

        # 验证MQTT发布被调用
        agent.mqtt_client.publish_description.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_mcp_tool_as_device(self, mock_agent_config):
        """测试注册MCP工具为设备"""
        from core.room_agent.models import DeviceType

        agent = RoomAgent(
            room_id="test-room",
            agent_config=mock_agent_config
        )

        # Mock device controller
        agent.device_controller.register_mcp_tool = AsyncMock(
            return_value=True
        )

        # Mock MCP manager
        mock_mcp_manager = Mock()

        # 测试注册
        success = await agent.register_mcp_tool_as_device(
            device_id="light_1",
            device_type=DeviceType.LIGHT,
            tool_name="philips_hue.light",
            mcp_manager=mock_mcp_manager,
            device_config={"name": "Living Room Light"}
        )

        assert success is True
        # 验证device_controller被调用
        agent.device_controller.register_mcp_tool.assert_called_once()
