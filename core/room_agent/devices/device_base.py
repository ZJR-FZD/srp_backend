# core/room_agent/devices/device_base.py
"""设备抽象基类

定义所有设备必须实现的统一接口
"""

import time
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod

from core.room_agent.models import DeviceState, DeviceType, DeviceCapability


class BaseDevice(ABC):
    """设备抽象基类

    所有设备必须继承此类并实现抽象方法
    """

    def __init__(self, device_id: str, device_type: DeviceType, config: Dict[str, Any]):
        """初始化设备

        Args:
            device_id: 设备唯一标识符
            device_type: 设备类型
            config: 设备配置字典
                - name: 设备名称
                - protocol: 通信协议
                - address: 设备地址
                - 其他协议特定参数
        """
        self.device_id = device_id
        self.device_type = device_type
        self.config = config
        self.name = config.get("name", device_id)
        self.protocol = config.get("protocol", "unknown")
        self.address = config.get("address", "")

        # 设备状态
        self._state = DeviceState(
            device_id=device_id,
            device_type=device_type,
            state="unknown",
            attributes={},
            last_updated=time.time()
        )

        print(f"[{self.__class__.__name__}] Device initialized: {self.name} ({device_id})")

    @abstractmethod
    async def connect(self) -> bool:
        """连接到设备

        Returns:
            bool: 是否成功连接
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """断开设备连接"""
        pass

    @abstractmethod
    async def execute_action(self, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """执行设备动作

        Args:
            action: 动作名称
            parameters: 动作参数

        Returns:
            Dict[str, Any]: 执行结果
            {
                "success": bool,
                "result": Any,
                "error": str (如果失败）
            }
        """
        pass

    @abstractmethod
    async def get_state(self) -> DeviceState:
        """获取设备当前状态

        Returns:
            DeviceState: 设备状态对象
        """
        pass

    @abstractmethod
    def get_capabilities(self) -> DeviceCapability:
        """获取设备能力描述

        Returns:
            DeviceCapability: 设备能力对象
        """
        pass

    async def update_state(self, state: str, attributes: Dict[str, Any] = None) -> None:
        """更新设备状态

        Args:
            state: 新状态值
            attributes: 状态属性字典
        """
        self._state.state = state
        if attributes:
            self._state.attributes.update(attributes)
        self._state.last_updated = time.time()

    @property
    def state(self) -> DeviceState:
        """获取设备状态（只读）"""
        return self._state

    @property
    def is_connected(self) -> bool:
        """检查设备是否已连接"""
        return self._state.state != "disconnected"
