"""
本地 Embedding 模型
使用 sentence-transformers 本地模型
"""
from typing import List
import numpy as np
from sentence_transformers import SentenceTransformer

from config.settings import settings

class LocalEmbeddings:
    """本地 Embedding 模型"""
    
    def __init__(self, model_name: str = None):
        """
        初始化本地 Embedding 模型
        
        Args:
            model_name: 模型名称，默认使用配置中的模型
        """
        self.model_name = model_name or settings.LOCAL_EMBEDDING_MODEL
        print(f"🔄 正在加载本地 Embedding 模型: {self.model_name}")
        
        try:
            # 加载模型（首次会自动下载）
            self.model = SentenceTransformer(self.model_name)
            self.dimension = self.model.get_sentence_embedding_dimension()
            print(f"✅ 模型加载成功！向量维度: {self.dimension}")
        except Exception as e:
            raise Exception(f"模型加载失败: {e}")
    
    def embed_text(self, text: str) -> np.ndarray:
        """
        将单个文本转换为向量
        
        Args:
            text: 输入文本
            
        Returns:
            np.ndarray: 文本向量
        """
        if not text or not text.strip():
            # 返回零向量
            return np.zeros(self.dimension, dtype=np.float32)
        
        try:
            embedding = self.model.encode(
                text,
                convert_to_numpy=True,
                normalize_embeddings=True  # L2 归一化
            )
            return embedding.astype(np.float32)
        except Exception as e:
            print(f"⚠️  文本向量化失败: {e}")
            return np.zeros(self.dimension, dtype=np.float32)
    
    def embed_texts(self, texts: List[str], batch_size: int = 32, show_progress: bool = True) -> np.ndarray:
        """
        批量将文本转换为向量
        
        Args:
            texts: 文本列表
            batch_size: 批处理大小
            show_progress: 是否显示进度条
            
        Returns:
            np.ndarray: 文本向量矩阵 (n_texts, dimension)
        """
        if not texts:
            return np.array([]).reshape(0, self.dimension)
        
        # 过滤空文本
        valid_texts = [text if text and text.strip() else " " for text in texts]
        
        try:
            embeddings = self.model.encode(
                valid_texts,
                batch_size=batch_size,
                show_progress_bar=show_progress,
                convert_to_numpy=True,
                normalize_embeddings=True
            )
            return embeddings.astype(np.float32)
        except Exception as e:
            print(f"⚠️  批量向量化失败: {e}")
            # 返回零向量矩阵
            return np.zeros((len(texts), self.dimension), dtype=np.float32)
    
    def embed_query(self, query: str) -> np.ndarray:
        """
        将查询文本转换为向量（与 embed_text 相同，但语义更清晰）
        
        Args:
            query: 查询文本
            
        Returns:
            np.ndarray: 查询向量
        """
        return self.embed_text(query)
    
    def get_dimension(self) -> int:
        """获取向量维度"""
        return self.dimension
    
    def similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        计算两个向量的余弦相似度
        
        Args:
            vec1: 向量1
            vec2: 向量2
            
        Returns:
            float: 余弦相似度 (0-1)
        """
        # 因为已经做了 L2 归一化，直接点积即可
        return float(np.dot(vec1, vec2))