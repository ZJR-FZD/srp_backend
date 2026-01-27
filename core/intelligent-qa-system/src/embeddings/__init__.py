"""
Embeddings 模块
提供统一的 Embedding 接口
"""
from config.settings import settings
from .local_embeddings import LocalEmbeddings
from .qwen_embeddings import QwenEmbeddings


def get_embeddings(model_type: str = None):
    """
    获取 Embedding 模型实例
    
    Args:
        model_type: 模型类型 ('local' 或 'qwen')
        
    Returns:
        Embedding 模型实例
    """
    model_type = model_type or settings.EMBEDDING_MODEL
    
    if model_type == "local":
        return LocalEmbeddings()
    elif model_type == "qwen":
        return QwenEmbeddings()
    else:
        raise ValueError(f"不支持的 Embedding 模型类型: {model_type}")


__all__ = ['LocalEmbeddings', 'QwenEmbeddings', 'get_embeddings']