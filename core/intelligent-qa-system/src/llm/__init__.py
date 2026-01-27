"""
LLM 模块
提供统一的 LLM 接口
"""
from config.settings import settings
from .base_llm import BaseLLM, ChatMessage, LLMResponse
from .qwen_llm import QwenLLM
from .deepseek_llm import DeepSeekLLM


def get_llm(llm_type: str = None, **kwargs) -> BaseLLM:
    """
    获取 LLM 实例
    
    Args:
        llm_type: LLM 类型 ('qwen', 'deepseek', 'openai')
        **kwargs: 其他参数
        
    Returns:
        BaseLLM: LLM 实例
    """
    llm_type = llm_type or settings.DEFAULT_LLM
    
    if llm_type == "qwen":
        return QwenLLM(**kwargs)
    elif llm_type == "deepseek":
        return DeepSeekLLM(**kwargs)
    else:
        raise ValueError(f"不支持的 LLM 类型: {llm_type}")


__all__ = [
    'BaseLLM',
    'ChatMessage',
    'LLMResponse',
    'QwenLLM',
    'DeepSeekLLM',
    'get_llm'
]