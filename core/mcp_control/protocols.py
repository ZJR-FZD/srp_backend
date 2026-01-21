# core/mcp_control/protocols.py
"""协议接口定义

定义 mcp_control 模块依赖的外部接口协议，实现依赖解耦。
"""

from typing import Protocol, List, Dict, Any


class LLMClientProtocol(Protocol):
    """LLM Client 协议接口
    
    定义 Router 所需的 LLM 调用能力，实现与具体 LLM Client 实现的解耦。
    主项目可以传入任何符合此协议的 LLM Client 实例。
    """
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ) -> str:
        """文本对话/推理
        
        Args:
            messages: 消息列表，格式为 [{"role": "user", "content": "..."}, ...]
            temperature: 生成温度
            max_tokens: 最大生成 token 数
            **kwargs: 其他可选参数
            
        Returns:
            str: 模型生成的文本
        """
        ...
    
    async def function_call_completion(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]],
        **kwargs
    ) -> Any:
        """函数调用/工具选择
        
        Args:
            messages: 消息列表
            tools: 工具定义列表
            **kwargs: 其他可选参数
            
        Returns:
            Any: 响应对象的 message 部分，包含以下属性：
                - tool_calls: Optional[List] - 工具调用列表，每个元素包含：
                    - function.name: str - 工具名称
                    - function.arguments: str - JSON 格式的参数
                - content: Optional[str] - 文本内容（当没有工具调用时）
        """
        ...
