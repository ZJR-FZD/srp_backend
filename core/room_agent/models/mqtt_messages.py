# core/room_agent/models/mqtt_messages.py
"""MQTT消息格式定义

符合HomeSystemAgent.md规范的消息格式
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime


class ControlMessage(BaseModel):
    """控制消息格式

    Topic: room/{room_id}/agent/{agent_id}/control
    QoS: 1
    """
    message_id: str = Field(..., description="消息唯一标识符")
    timestamp: str = Field(..., description="ISO 8601格式时间戳")
    source_agent: str = Field(..., description="发送方Agent ID")
    target_device: str = Field(..., description="目标设备ID")
    action: str = Field(..., description="要执行的动作")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="动作参数")
    correlation_id: Optional[str] = Field(None, description="关联ID（用于请求追踪）")


class DeviceState(BaseModel):
    """设备状态"""
    device_id: str
    state: str
    attributes: Dict[str, Any] = Field(default_factory=dict)


class StateMessage(BaseModel):
    """状态消息格式

    Topic: room/{room_id}/agent/{agent_id}/state
    QoS: 0
    """
    message_id: str = Field(..., description="消息唯一标识符")
    timestamp: str = Field(..., description="ISO 8601格式时间戳")
    agent_id: str = Field(..., description="Agent ID")
    devices: List[DeviceState] = Field(default_factory=list, description="设备状态列表")
    agent_status: str = Field(default="operational", description="Agent状态")


class DescribeMessage(BaseModel):
    """能力查询消息

    Topic: room/{room_id}/agent/{agent_id}/describe
    QoS: 1
    """
    message_id: str = Field(..., description="消息唯一标识符")
    timestamp: str = Field(..., description="ISO 8601格式时间戳")
    source_agent: str = Field(..., description="查询方Agent ID")
    query_type: str = Field(default="capabilities", description="查询类型")


class DeviceCapability(BaseModel):
    """设备能力描述"""
    id: str
    name: str
    type: str
    actions: List[str]
    state_attributes: List[str] = Field(default_factory=list)


class DescriptionMessage(BaseModel):
    """能力描述响应

    Topic: room/{room_id}/agent/{agent_id}/description
    QoS: 1
    """
    message_id: str = Field(..., description="消息唯一标识符")
    timestamp: str = Field(..., description="ISO 8601格式时间戳")
    agent_id: str = Field(..., description="Agent ID")
    agent_type: str = Field(default="room", description="Agent类型")
    version: str = Field(..., description="Agent版本")
    devices: List[DeviceCapability] = Field(default_factory=list, description="设备能力列表")
    capabilities: List[str] = Field(default_factory=list, description="Agent能力列表")


class SystemMetrics(BaseModel):
    """系统指标"""
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    active_connections: int = 0


class HeartbeatMessage(BaseModel):
    """心跳消息

    Topic: room/{room_id}/agent/{agent_id}/heartbeat
    QoS: 0
    """
    message_id: str = Field(..., description="消息唯一标识符")
    timestamp: str = Field(..., description="ISO 8601格式时间戳")
    agent_id: str = Field(..., description="Agent ID")
    status: str = Field(default="operational", description="Agent状态")
    uptime_seconds: int = Field(..., description="运行时间（秒）")
    metrics: SystemMetrics = Field(default_factory=SystemMetrics, description="系统指标")
