"""
Qwen Embedding 模型（通义千问）
使用 DashScope API
"""
from typing import List
import numpy as np
import dashscope
from dashscope import TextEmbedding
from tqdm import tqdm

from config.settings import settings


class QwenEmbeddings:
    """Qwen Embedding 模型"""
    
    def __init__(self, api_key: str = None, model: str = None):
        """
        初始化 Qwen Embedding 模型
        
        Args:
            api_key: API Key，默认从配置读取
            model: 模型名称，默认使用配置中的模型
        """
        self.api_key = api_key or settings.QWEN_API_KEY
        self.model = model or settings.QWEN_EMBEDDING_MODEL
        
        if not self.api_key:
            raise ValueError("未设置 QWEN_API_KEY，请在 .env 文件中配置")
        
        # 设置 API Key
        dashscope.api_key = self.api_key
        
        # Qwen text-embedding-v1 的向量维度是 1536
        self.dimension = 1536
        
        print(f"✅ Qwen Embedding 初始化成功！模型: {self.model}, 维度: {self.dimension}")
    
    def embed_text(self, text: str) -> np.ndarray:
        """
        将单个文本转换为向量
        
        Args:
            text: 输入文本
            
        Returns:
            np.ndarray: 文本向量
        """
        if not text or not text.strip():
            return np.zeros(self.dimension, dtype=np.float32)
        
        try:
            response = TextEmbedding.call(
                model=self.model,
                input=text
            )
            
            if response.status_code == 200:
                embedding = response.output['embeddings'][0]['embedding']
                return np.array(embedding, dtype=np.float32)
            else:
                print(f"⚠️  API 调用失败: {response.message}")
                return np.zeros(self.dimension, dtype=np.float32)
        
        except Exception as e:
            print(f"⚠️  文本向量化失败: {e}")
            return np.zeros(self.dimension, dtype=np.float32)
    
    def embed_texts(self, texts: List[str], batch_size: int = 25, show_progress: bool = True) -> np.ndarray:
        """
        批量将文本转换为向量
        
        Args:
            texts: 文本列表
            batch_size: 批处理大小（Qwen API 最大 25）
            show_progress: 是否显示进度条
            
        Returns:
            np.ndarray: 文本向量矩阵
        """
        if not texts:
            return np.array([]).reshape(0, self.dimension)
        
        all_embeddings = []
        
        # 分批处理
        batches = [texts[i:i + batch_size] for i in range(0, len(texts), batch_size)]
        
        iterator = tqdm(batches, desc="向量化进度") if show_progress else batches
        
        for batch in iterator:
            try:
                # 过滤空文本
                valid_batch = [text if text and text.strip() else " " for text in batch]
                
                response = TextEmbedding.call(
                    model=self.model,
                    input=valid_batch
                )
                
                if response.status_code == 200:
                    batch_embeddings = [
                        emb['embedding'] 
                        for emb in response.output['embeddings']
                    ]
                    all_embeddings.extend(batch_embeddings)
                else:
                    print(f"⚠️  批次处理失败: {response.message}")
                    # 添加零向量
                    all_embeddings.extend([
                        [0.0] * self.dimension for _ in batch
                    ])
            
            except Exception as e:
                print(f"⚠️  批次处理异常: {e}")
                all_embeddings.extend([
                    [0.0] * self.dimension for _ in batch
                ])
        
        return np.array(all_embeddings, dtype=np.float32)
    
    def embed_query(self, query: str) -> np.ndarray:
        """
        将查询文本转换为向量
        
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
            float: 余弦相似度
        """
        # 计算余弦相似度
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(np.dot(vec1, vec2) / (norm1 * norm2))