"""
向量存储管理器
统一管理向量化和存储流程
"""
from typing import List
from pathlib import Path
from tqdm import tqdm

from config.settings import settings
from ..document_loader.base_loader import Document
from ..embeddings import get_embeddings
from .faiss_store import FAISSStore


class VectorStoreManager:
    """向量存储管理器"""
    
    def __init__(self, embedding_model: str = None):
        """
        初始化管理器
        
        Args:
            embedding_model: Embedding 模型类型 ('local' 或 'qwen')
        """
        # 初始化 Embedding 模型
        self.embeddings = get_embeddings(embedding_model)
        
        # FAISS 存储（延迟初始化）
        self.store: FAISSStore = None
    
    def build_index(
        self,
        documents: List[Document],
        batch_size: int = 25,
        save: bool = True
    ) -> FAISSStore:
        """
        构建向量索引
        
        Args:
            documents: 文档列表
            batch_size: 批处理大小
            save: 是否保存索引
            
        Returns:
            FAISSStore: 构建的向量存储
        """
        if not documents:
            raise ValueError("文档列表为空")
        
        print(f"\n{'='*60}")
        print(f"开始构建向量索引")
        print(f"{'='*60}")
        print(f"📄 文档数量: {len(documents)}")
        print(f"🤖 Embedding 模型: {self.embeddings.model_name if hasattr(self.embeddings, 'model_name') else 'Qwen'}")
        print(f"📊 向量维度: {self.embeddings.get_dimension()}")
        
        # 提取文档内容
        texts = [doc.content for doc in documents]
        
        # 向量化
        print(f"\n🔄 正在向量化 {len(texts)} 个文档...")
        embeddings = self.embeddings.embed_texts(
            texts,
            batch_size=batch_size,
            show_progress=True
        )
        
        # 创建 FAISS 存储
        print(f"\n🔄 正在创建 FAISS 索引...")
        self.store = FAISSStore(
            dimension=self.embeddings.get_dimension(),
            index_type=settings.FAISS_INDEX_TYPE
        )
        
        # 添加文档
        self.store.add_documents(documents, embeddings)
        
        # 保存索引
        if save:
            print(f"\n💾 正在保存索引...")
            self.store.save()
        
        print(f"\n{'='*60}")
        print(f"✅ 向量索引构建完成！")
        print(f"{'='*60}\n")
        
        return self.store
    
    def load_index(self, load_dir: str = None) -> FAISSStore:
        """
        加载已有的向量索引
        
        Args:
            load_dir: 索引目录
            
        Returns:
            FAISSStore: 加载的向量存储
        """
        print(f"\n🔄 正在加载向量索引...")
        self.store = FAISSStore.load(load_dir)
        return self.store
    
    def add_documents(
        self,
        documents: List[Document],
        batch_size: int = 32,
        save: bool = True
    ):
        """
        向现有索引添加文档
        
        Args:
            documents: 文档列表
            batch_size: 批处理大小
            save: 是否保存索引
        """
        if not self.store:
            raise ValueError("请先构建或加载索引")
        
        print(f"\n🔄 正在添加 {len(documents)} 个文档到索引...")
        
        # 向量化
        texts = [doc.content for doc in documents]
        embeddings = self.embeddings.embed_texts(
            texts,
            batch_size=batch_size,
            show_progress=True
        )
        
        # 添加到索引
        self.store.add_documents(documents, embeddings)
        
        # 保存
        if save:
            print(f"\n💾 正在保存索引...")
            self.store.save()
        
        print(f"✅ 文档添加完成！")
    
    def search(
        self,
        query: str,
        k: int = None,
        threshold: float = None
    ) -> List[tuple]:
        """
        搜索相似文档
        
        Args:
            query: 查询文本
            k: 返回文档数量
            threshold: 相似度阈值
            
        Returns:
            List[tuple]: (Document, score) 列表
        """
        if not self.store:
            raise ValueError("请先构建或加载索引")
        
        # 向量化查询
        query_vector = self.embeddings.embed_query(query)
        
        # 搜索
        results = self.store.search(
            query_vector,
            k=k,
            threshold=threshold
        )
        
        return results
    
    def get_stats(self) -> dict:
        """获取索引统计信息"""
        if not self.store:
            return {"status": "未初始化"}
        
        return {
            "document_count": self.store.get_document_count(),
            "index_type": self.store.index_type,
            "dimension": self.store.dimension,
            "embedding_model": getattr(self.embeddings, 'model_name', 'Qwen')
        }