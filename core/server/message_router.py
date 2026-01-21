# core/server/message_router.py
"""消息路由器

负责消息验证、解析和路由
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, ValidationError


class TaskRequest(BaseModel):
    """任务请求数据模型"""
    task_type: str = Field(..., description="任务类型")
    task_name: str = Field(..., description="任务名称")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="任务参数")
    priority: int = Field(default=5, ge=1, le=10, description="任务优先级")
    timeout: float = Field(default=60.0, gt=0, description="任务超时时间（秒）")
    callback_url: Optional[str] = Field(default=None, description="任务完成后的回调地址")


class UserInputRequest(BaseModel):
    """用户输入请求数据模型"""
    input_type: str = Field(..., description="输入类型（voice/text/gesture）")
    content: str = Field(..., description="输入内容")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="附加元数据")
    session_id: Optional[str] = Field(default=None, description="会话标识")


class WebSocketMessage(BaseModel):
    """WebSocket 消息数据模型"""
    message_type: str = Field(..., description="消息类型")
    from_agent: str = Field(..., description="发送方智能体标识")
    to_agent: Optional[str] = Field(default=None, description="接收方智能体标识")
    message_id: str = Field(..., description="消息唯一标识")
    timestamp: float = Field(..., description="消息时间戳")
    payload: Dict[str, Any] = Field(..., description="消息负载数据")


class MessageRouter:
    """消息路由器"""
    
    def __init__(self):
        """初始化消息路由器"""
        self.message_count = 0
        print("[MessageRouter] Initialized")
    
    def validate_task_request(self, data: Dict[str, Any]) -> Optional[TaskRequest]:
        """验证任务请求数据
        
        Args:
            data: 原始请求数据
            
        Returns:
            TaskRequest: 验证通过的任务请求对象，失败返回 None
        """
        try:
            task_request = TaskRequest(**data)
            self.message_count += 1
            return task_request
        except ValidationError as e:
            print(f"[MessageRouter] Task request validation failed: {e}")
            return None
    
    def validate_user_input(self, data: Dict[str, Any]) -> Optional[UserInputRequest]:
        """验证用户输入数据
        
        Args:
            data: 原始输入数据
            
        Returns:
            UserInputRequest: 验证通过的用户输入对象，失败返回 None
        """
        try:
            user_input = UserInputRequest(**data)
            self.message_count += 1
            return user_input
        except ValidationError as e:
            print(f"[MessageRouter] User input validation failed: {e}")
            return None
    
    def validate_websocket_message(self, data: Dict[str, Any]) -> Optional[WebSocketMessage]:
        """验证 WebSocket 消息数据
        
        Args:
            data: 原始消息数据
            
        Returns:
            WebSocketMessage: 验证通过的消息对象，失败返回 None
        """
        try:
            message = WebSocketMessage(**data)
            self.message_count += 1
            return message
        except ValidationError as e:
            print(f"[MessageRouter] WebSocket message validation failed: {e}")
            return None
    
    def convert_user_input_to_task(self, user_input: UserInputRequest) -> TaskRequest:
        """将用户输入转换为任务请求
        
        Args:
            user_input: 用户输入对象
            
        Returns:
            TaskRequest: 转换后的任务请求
        """
        return TaskRequest(
            task_type="user_input",
            task_name=f"user_input_{user_input.input_type}",
            parameters={
                "input_type": user_input.input_type,
                "content": user_input.content,
                "metadata": user_input.metadata,
                "session_id": user_input.session_id
            }
        )
