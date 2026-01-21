# core/client/__init__.py
"""客户端模块

导出所有 API 客户端
"""

from core.client.openai_client import OpenAIClient

__all__ = [
    "OpenAIClient",
]
