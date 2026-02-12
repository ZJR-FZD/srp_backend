# core/room_agent/devices/mcp_device_wrapper.py
"""MCP设备包装器

将MCP工具包装为统一设备接口
"""

import asyncio
from typing import Dict, Any, List
from datetime import datetime

from core.room_agent.devices.device_base import BaseDevice
from core.room_agent.models import DeviceState, DeviceType, DeviceCapability, DeviceAction


class McpDeviceWrapper(BaseDevice):
    """MCP工具设备包装器

    将MCP工具包装为统一的BaseDevice接口
    """

    def __init__(
        self,
        device_id: str,
        device_type: DeviceType,
        config: Dict[str, Any],
        mcp_manager,
        tool_name: str
    ):
        """初始化MCP设备包装器

        Args:
            device_id: 设备ID（MCP工具名称）
            device_type: 设备类型
            config: 设备配置
            mcp_manager: McpManager实例
            tool_name: MCP工具名称
        """
        super().__init__(device_id, device_type, config)

        self.mcp_manager = mcp_manager
        self.tool_name = tool_name
        self._connected = False

        print(f"[McpDeviceWrapper] Initialized for tool: {tool_name}")

    async def connect(self) -> bool:
        """连接到MCP服务"""
        if self._connected:
            return True

        # MCP Manager已经建立了连接，这里只是检查
        try:
            if self.mcp_manager and self.mcp_manager._initialized:
                self._connected = True
                await self.update_state("online", {
                    "mcp_tool": self.tool_name,
                    "connection_type": "mcp"
                })
                return True
            else:
                return False
        except Exception as e:
            print(f"[McpDeviceWrapper] Connection error: {e}")
            return False

    async def disconnect(self) -> None:
        """断开MCP连接"""
        # MCP连接由Manager管理，这里只更新状态
        self._connected = False
        await self.update_state("offline")

    async def execute_action(self, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """执行MCP工具调用

        Args:
            action: 动作名称（应该与MCP工具名称一致）
            parameters: 工具参数

        Returns:
            Dict[str, Any]: 执行结果
        """
        if not self._connected:
            return {
                "success": False,
                "error": "Device not connected"
            }

        try:
            # 获取MCP Router
            if not hasattr(self.mcp_manager, 'router'):
                return {
                    "success": False,
                    "error": "MCP Router not available"
                }

            router = self.mcp_manager.router

            # 构建工具调用参数
            tool_parameters = parameters.get("tool_parameters", {})

            print(f"[McpDeviceWrapper] Calling MCP tool: {self.tool_name}")
            print(f"  Parameters: {tool_parameters}")

            # 调用MCP工具
            result = await router.call_tool(
                server_name=None,  # 自动查找
                tool_name=self.tool_name,
                arguments=tool_parameters
            )

            if result.get("success"):
                print(f"[McpDeviceWrapper] Tool call successful")
                return {
                    "success": True,
                    "result": result.get("content")
                }
            else:
                error_msg = result.get("error", "Unknown error")
                print(f"[McpDeviceWrapper] Tool call failed: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg
                }

        except Exception as e:
            print(f"[McpDeviceWrapper] Error executing action: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def get_state(self) -> DeviceState:
        """获取设备状态"""
        return self.state

    def get_capabilities(self) -> DeviceCapability:
        """获取设备能力描述"""
        # 从MCP工具索引中获取工具信息
        actions = []
        state_attributes = []

        try:
            if self.mcp_manager and hasattr(self.mcp_manager, 'tool_index'):
                tool_index = self.mcp_manager.tool_index
                tool = tool_index.get_tool(self.tool_name)

                if tool:
                    # 工具名称就是动作
                    actions.append(self.tool_name)

                    # 从schema中提取状态属性
                    if hasattr(tool, 'input_schema'):
                        schema = tool.input_schema
                        if schema and 'properties' in schema:
                            state_attributes.extend(schema['properties'].keys())

        except Exception as e:
            print(f"[McpDeviceWrapper] Error getting capabilities: {e}")

        return DeviceCapability(
            id=self.device_id,
            name=self.name,
            type=self.device_type,
            protocol="mcp",
            address=f"mcp:{self.tool_name}",
            actions=actions,
            state_attributes=state_attributes
        )
