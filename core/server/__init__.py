# core/server/__init__.py
"""通信服务模块

提供 HTTP/WebSocket 通信服务，负责任务接收和智能体间通信（A2A）
"""

from core.server.connection_manager import ConnectionManager
from core.server.message_router import MessageRouter
from core.server.task_dispatcher import TaskDispatcher
from core.server.communication_server import CommunicationServer

__all__ = [
    "ConnectionManager",
    "MessageRouter", 
    "TaskDispatcher",
    "CommunicationServer",
]
