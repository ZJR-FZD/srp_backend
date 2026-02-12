# tests/room_agent/test_device_controller.py
"""设备控制器测试"""
import pytest
from unittest.mock import Mock, AsyncMock

from core.room_agent.devices.device_controller import DeviceController
from core.room_agent.devices.device_registry import DeviceRegistry
from core.room_agent.devices.mcp_device_wrapper import McpDeviceWrapper
from core.room_agent.models import DeviceType


class TestDeviceController:
    """设备控制器测试"""

    @pytest.mark.asyncio
    async def test_init(self):
        """测试初始化"""
        registry = DeviceRegistry()
        controller = DeviceController(registry)

        assert controller.registry == registry

    @pytest.mark.asyncio
    async def test_register_mcp_tool(self):
        """测试注册MCP工具为设备"""
        registry = DeviceRegistry()
        controller = DeviceController(registry)

        # Mock MCP Manager
        mock_mcp_manager = Mock()
        mock_mcp_manager._initialized = True
        mock_mcp_manager.router = Mock()

        # 测试注册
        success = await controller.register_mcp_tool(
            device_id="light_1",
            device_type=DeviceType.LIGHT,
            tool_name="philips_hue.light",
            mcp_manager=mock_mcp_manager,
            device_config={"name": "Living Room Light"}
        )

        assert success is True

        # 验证设备已注册
        device = await registry.get_device("light_1")
        assert device is not None
        assert isinstance(device, McpDeviceWrapper)

    @pytest.mark.asyncio
    async def test_control_device(self, mock_device):
        """测试控制设备"""
        registry = DeviceRegistry()
        controller = DeviceController(registry)

        # 注册mock设备
        await registry.register_device(mock_device)

        # Mock设备方法
        mock_device.execute_action = AsyncMock(
            return_value={"success": True, "result": "OK"}
        )

        # 测试控制
        result = await controller.control_device(
            device_id="mock_device",
            action="on",
            parameters={"brightness": 80}
        )

        assert result["success"] is True
        assert result["result"] == "OK"
        mock_device.execute_action.assert_called_once_with(
            "on",
            {"brightness": 80}
        )

    @pytest.mark.asyncio
    async def test_get_device_state(self, mock_device):
        """测试获取设备状态"""
        registry = DeviceRegistry()
        controller = DeviceController(registry)

        # 注册mock设备
        await registry.register_device(mock_device)

        # Mock get_state方法
        mock_device.get_state = AsyncMock(
            return_value=mock_device.state
        )

        # 测试获取状态
        state = await controller.get_device_state("mock_device")

        assert state is not None
        assert state.device_id == "mock_device"

    @pytest.mark.asyncio
    async def test_list_all_devices(self, mock_device):
        """测试列出所有设备"""
        registry = DeviceRegistry()
        controller = DeviceController(registry)

        # 注册mock设备
        await registry.register_device(mock_device)

        # 测试列出
        devices = await controller.list_all_devices()

        assert len(devices) == 1
        assert devices[0] == mock_device
