# core/room_agent/models/device_state.py
"""设备状态和能力模型

定义设备状态、能力描述的数据结构
"""

from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from enum import Enum


class DeviceType(str, Enum):
    """设备类型枚举"""
    LIGHT = "light"
    CURTAIN = "curtain"
    CLIMATE = "climate"
    SWITCH = "switch"
    SENSOR = "sensor"
    LOCK = "lock"
    CAMERA = "camera"
    ROBOT = "robot"
    UNKNOWN = "unknown"


class DeviceState(BaseModel):
    """设备状态

    表示设备的当前状态和属性值
    """
    device_id: str = Field(..., description="设备唯一标识符")
    device_type: DeviceType = Field(..., description="设备类型")
    state: str = Field(..., description="设备状态（on/off/online/offline等）")
    attributes: Dict[str, Any] = Field(default_factory=dict, description="设备属性值")
    last_updated: float = Field(default_factory=lambda: __import__('time').time(), description="最后更新时间戳")


class DeviceCapability(BaseModel):
    """设备能力描述

    描述设备支持的动作和状态属性
    """
    id: str = Field(..., description="设备ID")
    name: str = Field(..., description="设备名称")
    type: DeviceType = Field(..., description="设备类型")
    protocol: str = Field(..., description="通信协议（mcp/http/mqtt/zigbee）")
    address: str = Field(..., description="设备地址")
    actions: List[str] = Field(..., description="支持的动作列表")
    state_attributes: List[str] = Field(default_factory=list, description="可查询的状态属性")


class DeviceAction(BaseModel):
    """设备动作定义

    表示设备支持的具体动作
    """
    name: str = Field(..., description="动作名称")
    description: str = Field(..., description="动作描述")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="动作参数定义")
