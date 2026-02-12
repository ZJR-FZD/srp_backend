# core/room_agent/devices/device_registry.py
"""设备注册表

管理所有设备的注册、查询和状态
"""

import asyncio
from typing import Dict, List, Optional, Any

from core.room_agent.devices.device_base import BaseDevice
from core.room_agent.models import DeviceState, DeviceCapability, DeviceType


class DeviceRegistry:
    """设备注册表

    职责：
    - 管理设备注册
    - 提供设备查询
    - 设备状态变更通知
    """

    def __init__(self):
        """初始化设备注册表"""
        self._devices: Dict[str, BaseDevice] = {}  # device_id -> device
        self._lock = asyncio.Lock()

        print("[DeviceRegistry] Initialized")

    async def register_device(self, device: BaseDevice) -> bool:
        """注册设备

        Args:
            device: 设备实例

        Returns:
            bool: 是否成功注册
        """
        async with self._lock:
            if device.device_id in self._devices:
                print(f"[DeviceRegistry] Device {device.device_id} already registered")
                return False

            self._devices[device.device_id] = device
            print(f"[DeviceRegistry] Device '{device.name}' ({device.device_id}) registered")
            return True

    async def unregister_device(self, device_id: str) -> bool:
        """注销设备

        Args:
            device_id: 设备ID

        Returns:
            bool: 是否成功注销
        """
        async with self._lock:
            if device_id not in self._devices:
                return False

            device = self._devices[device_id]

            # 断开设备连接
            try:
                await device.disconnect()
            except Exception as e:
                print(f"[DeviceRegistry] Error disconnecting device {device_id}: {e}")

            del self._devices[device_id]
            print(f"[DeviceRegistry] Device '{device_id}' unregistered")
            return True

    async def get_device(self, device_id: str) -> Optional[BaseDevice]:
        """获取设备实例

        Args:
            device_id: 设备ID

        Returns:
            Optional[BaseDevice]: 设备实例，不存在返回None
        """
        async with self._lock:
            return self._devices.get(device_id)

    async def list_all_devices(self) -> List[BaseDevice]:
        """列出所有设备

        Returns:
            List[BaseDevice]: 所有设备实例列表
        """
        async with self._lock:
            return list(self._devices.values())

    async def list_device_capabilities(self) -> List[DeviceCapability]:
        """列出所有设备的能力

        Returns:
            List[DeviceCapability]: 所有设备的能力描述列表
        """
        async with self._lock:
            capabilities = []
            for device in self._devices.values():
                try:
                    cap = device.get_capabilities()
                    capabilities.append(cap)
                except Exception as e:
                    print(f"[DeviceRegistry] Error getting capabilities for {device.device_id}: {e}")
            return capabilities

    async def execute_device_action(
        self,
        device_id: str,
        action: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行设备动作

        Args:
            device_id: 设备ID
            action: 动作名称
            parameters: 动作参数

        Returns:
            Dict[str, Any]: 执行结果
        """
        async with self._lock:
            device = self._devices.get(device_id)
            if not device:
                return {
                    "success": False,
                    "error": f"Device '{device_id}' not found"
                }

        # 执行动作（不在锁内，避免阻塞其他操作）
        try:
            result = await device.execute_action(action, parameters)
            return result
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def get_device_state(self, device_id: str) -> Optional[DeviceState]:
        """获取设备状态

        Args:
            device_id: 设备ID

        Returns:
            Optional[DeviceState]: 设备状态，不存在返回None
        """
        async with self._lock:
            device = self._devices.get(device_id)
            if not device:
                return None

        try:
            state = await device.get_state()
            return state
        except Exception as e:
            print(f"[DeviceRegistry] Error getting state for {device_id}: {e}")
            # 返回离线状态
            return DeviceState(
                device_id=device_id,
                device_type=device.device_type,
                state="offline",
                attributes={}
            )

    async def connect_all_devices(self) -> None:
        """连接所有已注册的设备"""
        async with self._lock:
            devices = list(self._devices.values())

        print(f"[DeviceRegistry] Connecting to {len(devices)} devices...")
        for device in devices:
            try:
                success = await device.connect()
                if success:
                    print(f"[DeviceRegistry] Device '{device.name}' connected successfully")
                else:
                    print(f"[DeviceRegistry] WARNING: Device '{device.name}' connection failed")
            except Exception as e:
                print(f"[DeviceRegistry] ERROR: Failed to connect '{device.name}': {e}")

    async def disconnect_all_devices(self) -> None:
        """断开所有设备连接"""
        async with self._lock:
            devices = list(self._devices.values())

        print(f"[DeviceRegistry] Disconnecting {len(devices)} devices...")
        for device in devices:
            try:
                await device.disconnect()
            except Exception as e:
                print(f"[DeviceRegistry] Error disconnecting '{device.name}': {e}")
