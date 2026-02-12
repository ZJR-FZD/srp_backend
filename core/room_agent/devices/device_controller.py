# core/room_agent/devices/device_controller.py
"""设备控制器

统一设备控制逻辑，处理设备状态管理和控制命令
"""

import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime

from core.room_agent.devices.device_registry import DeviceRegistry
from core.room_agent.devices.mcp_device_wrapper import McpDeviceWrapper
from core.room_agent.models import DeviceState, DeviceType


class DeviceController:
    """设备控制器

    负责：
    - 设备注册和注销
    - 统一设备控制接口
    - 设备状态查询
    """

    def __init__(self, device_registry: DeviceRegistry):
        """初始化设备控制器

        Args:
            device_registry: 设备注册表实例
        """
        self.registry = device_registry

        print("[DeviceController] Initialized")

    async def register_mcp_tool(
        self,
        device_id: str,
        device_type: DeviceType,
        device_config: Dict[str, Any],
        mcp_manager,
        tool_name: str
    ) -> bool:
        """注册MCP工具为设备

        Args:
            device_id: 设备ID
            device_type: 设备类型
            device_config: 设备配置
            mcp_manager: MCP Manager实例
            tool_name: MCP工具名称

        Returns:
            bool: 是否成功注册
        """
        try:
            # 创建MCP设备包装器
            device = McpDeviceWrapper(
                device_id=device_id,
                device_type=device_type,
                config=device_config,
                mcp_manager=mcp_manager,
                tool_name=tool_name
            )

            # 注册到设备表
            success = await self.registry.register_device(device)

            if success:
                # 连接设备
                await device.connect()

            return success

        except Exception as e:
            print(f"[DeviceController] Failed to register MCP device {device_id}: {e}")
            return False

    async def unregister_device(self, device_id: str) -> bool:
        """注销设备

        Args:
            device_id: 设备ID

        Returns:
            bool: 是否成功注销
        """
        return await self.registry.unregister_device(device_id)

    async def control_device(
        self,
        device_id: str,
        action: str,
        parameters: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """控制设备

        Args:
            device_id: 设备ID
            action: 动作名称
            parameters: 动作参数

        Returns:
            Dict[str, Any]: 执行结果
        """
        if parameters is None:
            parameters = {}

        print(f"[DeviceController] Controlling device {device_id}: {action}")

        # 执行设备动作
        result = await self.registry.execute_device_action(
            device_id=device_id,
            action=action,
            parameters=parameters
        )

        # 检查结果并更新状态
        if result.get("success"):
            print(f"[DeviceController] Device {device_id} action successful")
            # TODO: 根据动作类型更新设备状态
        else:
            print(f"[DeviceController] Device {device_id} action failed: {result.get('error')}")

        return result

    async def get_device_state(self, device_id: str) -> Optional[DeviceState]:
        """获取设备状态

        Args:
            device_id: 设备ID

        Returns:
            Optional[DeviceState]: 设备状态
        """
        return await self.registry.get_device_state(device_id)

    async def list_all_devices(self) -> List[Any]:
        """列出所有设备

        Returns:
            List[Any]: 所有设备实例
        """
        return await self.registry.list_all_devices()

    async def list_device_capabilities(self) -> List[Any]:
        """列出所有设备能力

        Returns:
            List[Any]: 所有设备的能力描述
        """
        return await self.registry.list_device_capabilities()

    async def connect_all_devices(self) -> None:
        """连接所有设备"""
        await self.registry.connect_all_devices()

    async def disconnect_all_devices(self) -> None:
        """断开所有设备连接"""
        await self.registry.disconnect_all_devices()
