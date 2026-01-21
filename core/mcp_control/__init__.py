# core/mcp_control/__init__.py
"""Mcp_control 模块

历史说明：本模块曾包含 McpTaskManager 用于多轮任务执行，
现已废弃并删除。多轮任务执行已迁移到 McpExecutor + 统一任务队列架构。
所有任务相关类型请使用 core.task.models 中的统一模型。
"""

from core.mcp_control.connection import McpConnection, ConnectionState
from core.mcp_control.manager import McpManager
from core.mcp_control.router import McpRouter, RouterDecision, RouterContext
from core.mcp_control.tool_index import ToolIndex, ToolIndexEntry
from core.mcp_control.protocols import LLMClientProtocol

__all__ = [
    # Connection
    "McpConnection",
    "ConnectionState",
    # Manager
    "McpManager",
    # Router
    "McpRouter",
    "RouterDecision",
    "RouterContext",
    # Tool Index
    "ToolIndex",
    "ToolIndexEntry",
    # Protocols
    "LLMClientProtocol",
]
