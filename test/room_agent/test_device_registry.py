# tests/room_agent/test_device_registry.py
"""设备注册表测试"""
import pytest
from core.room_agent.devices.device_registry import DeviceRegistry
from core.room_agent.devices.device_base import BaseDevice
from core.room_agent.models import DeviceType, DeviceState
from unittest.mock import Mock


class MockDevice(BaseDevice):
    """Mock设备用于测试"""

    def __init__(self, device_id: str):
        super().__init__(
            device_id=device_id,
            device_type=DeviceType.LIGHT,
            config={"name": f"Mock-{device_id}"}
        )
        self._connected = False

    async def connect(self) -> bool:
        self._connected = True
        return True

    async def disconnect(self):
        self._connected = False

    async def execute_action(self, action: str, parameters):
        return {"success": True, "result": f"Executed {action}"}

    async def get_state(self) -> DeviceState:
        return self.state

    def get_capabilities(self):
        return {
            "id": self.device_id,
            "name": self.name,
            "type": self.device_type,
            "protocol": "mock",
            "address": "mock://test",
            "actions": ["on", "off"],
            "state_attributes": ["power"]
        }


class TestDeviceRegistry:
    """设备注册表测试"""

    @pytest.mark.asyncio
    async def test_init(self):
        """测试初始化"""
        registry = DeviceRegistry()

        assert len(registry._devices) == 0

    @pytest.mark.asyncio
    async def test_register_device(self):
        """测试注册设备"""
        registry = DeviceRegistry()
        device = MockDevice("light_1")

        # 测试注册
        success = await registry.register_device(device)

        assert success is True
        assert "light_1" in registry._devices
        assert registry._devices["light_1"] == device

    @pytest.mark.asyncio
    async def test_register_duplicate(self):
        """测试注册重复设备"""
        registry = DeviceRegistry()
        device1 = MockDevice("light_1")
        device2 = MockDevice("light_1")

        # 注册第一个
        success1 = await registry.register_device(device1)
        assert success1 is True

        # 尝试注册重复ID
        success2 = await registry.register_device(device2)
        assert success2 is False

    @pytest.mark.asyncio
    async def test_unregister_device(self):
        """测试注销设备"""
        registry = DeviceRegistry()
        device = MockDevice("light_1")

        # 先注册
        await registry.register_device(device)
        assert "light_1" in registry._devices

        # 注销
        success = await registry.unregister_device("light_1")

        assert success is True
        assert "light_1" not in registry._devices

    @pytest.mark.asyncio
    async def test_get_device(self):
        """测试获取设备"""
        registry = DeviceRegistry()
        device = MockDevice("light_1")

        # 未注册时
        result = await registry.get_device("light_1")
        assert result is None

        # 注册后
        await registry.register_device(device)
        result = await registry.get_device("light_1")

        assert result is not None
        assert result.device_id == "light_1"

    @pytest.mark.asyncio
    async def test_list_all_devices(self):
        """测试列出所有设备"""
        registry = DeviceRegistry()

        # 空列表
        devices = await registry.list_all_devices()
        assert len(devices) == 0

        # 注册多个设备
        device1 = MockDevice("light_1")
        device2 = MockDevice("light_2")

        await registry.register_device(device1)
        await registry.register_device(device2)

        # 列出
        devices = await registry.list_all_devices()
        assert len(devices) == 2
