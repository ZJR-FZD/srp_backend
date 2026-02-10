"""
FAISS 向量存储
"""
import os
import json
from typing import List, Tuple, Dict, Any
from pathlib import Path
import numpy as np
import faiss
from tqdm import tqdm

from config.settings import settings
from ..document_loader.base_loader import Document


class FAISSStore:
    """FAISS 向量存储"""
    
    def __init__(self, dimension: int, index_type: str = None):
        """
        初始化 FAISS 存储
        
        Args:
            dimension: 向量维度
            index_type: 索引类型 ('Flat', 'IVFFlat', 'HNSW')
        """
        self.dimension = dimension
        self.index_type = index_type or settings.FAISS_INDEX_TYPE
        
        # 创建索引
        self.index = self._create_index()
        
        # 存储文档元数据
        self.documents: List[Document] = []
        self.id_to_index: Dict[int, int] = {}  # 文档ID到索引的映射
        
        print(f"✅ FAISS 索引初始化成功！类型: {self.index_type}, 维度: {dimension}")
    
    def _create_index(self) -> faiss.Index:
        """创建 FAISS 索引"""
        if self.index_type == "Flat":
            # 暴力搜索，最精确但速度慢
            index = faiss.IndexFlatL2(self.dimension)
        
        elif self.index_type == "IVFFlat":
            # 倒排文件索引，适合大数据集
            # nlist: 聚类中心数量，建议为 sqrt(n_vectors)
            nlist = 100
            quantizer = faiss.IndexFlatL2(self.dimension)
            index = faiss.IndexIVFFlat(quantizer, self.dimension, nlist)
            # 注意：IVF 需要先训练才能添加向量
            self.needs_training = True
        
        elif self.index_type == "HNSW":
            # 分层导航小世界图，速度快但占用内存多
            M = 32  # 每层的邻居数
            index = faiss.IndexHNSWFlat(self.dimension, M)
            index.hnsw.efConstruction = 40  # 构建时的搜索深度
        
        else:
            raise ValueError(f"不支持的索引类型: {self.index_type}")
        
        return index
    
    def add_documents(self, documents: List[Document], embeddings: np.ndarray):
        """
        添加文档和向量
        
        Args:
            documents: 文档列表
            embeddings: 对应的向量矩阵 (n_docs, dimension)
        """
        if len(documents) != len(embeddings):
            raise ValueError("文档数量和向量数量不匹配")
        
        # 对向量做 L2 归一化
        faiss.normalize_L2(embeddings)

        # 如果是 IVF 索引且未训练，先训练
        if self.index_type == "IVFFlat" and not self.index.is_trained:
            print("🔄 正在训练 IVF 索引...")
            self.index.train(embeddings)
            print("✅ 索引训练完成")
        
        # 添加向量到索引
        start_id = len(self.documents)
        self.index.add(embeddings)
        
        # 保存文档和映射
        for i, doc in enumerate(documents):
            doc_id = start_id + i
            self.documents.append(doc)
            self.id_to_index[doc_id] = len(self.documents) - 1
        
        print(f"✅ 已添加 {len(documents)} 个文档，当前总数: {len(self.documents)}")
    
    def search(
        self,
        query_vector: np.ndarray,
        k: int = None,
        threshold: float = None
    ) -> List[Tuple[Document, float]]:
        """
        搜索相似文档
        
        注意：
        - 文档向量和查询向量都会做 L2 归一化
        - FAISS 返回的是 L2 距离（范围 [0, 2]）
        - 转换为余弦相似度：cosine = 1 - (distance^2 / 2)
        
        Args:
            query_vector: 查询向量
            k: 返回文档数量（默认使用 settings.TOP_K）
            threshold: 余弦相似度阈值（建议 0.3-0.7）
            
        Returns:
            List[Tuple[Document, float]]: (文档, 相似度) 列表
        """
        if len(self.documents) == 0:
            return []
        
        k = k or settings.TOP_K
        threshold = threshold if threshold is not None else settings.SIMILARITY_THRESHOLD
        
        # 确保查询向量是 2D
        if query_vector.ndim == 1:
            query_vector = query_vector.reshape(1, -1)
        
        # L2 归一化查询向量
        faiss.normalize_L2(query_vector)
        
        # FAISS 搜索
        distances, indices = self.index.search(query_vector, k)
        
        results = []
        for rank, (dist, idx) in enumerate(zip(distances[0], indices[0]), start=1):
            if idx == -1:  # 无效结果
                continue
            
            # 👇 修复：正确的余弦相似度转换公式
            # 对于归一化向量：L2(a,b)^2 = 2 - 2*cos(a,b)
            # => cos(a,b) = 1 - L2(a,b)^2 / 2
            cosine_sim = 1.0 - float(dist * dist) / 2.0
            
            # 相似度阈值过滤
            if cosine_sim < threshold:
                continue
            
            doc = self.documents[idx]
            results.append((doc, cosine_sim))
        
        return results
    
    def get_document_count(self) -> int:
        """获取文档数量"""
        return len(self.documents)
    
    def save(self, save_dir: str = None):
        """
        保存索引和元数据
        
        Args:
            save_dir: 保存目录，默认使用配置中的目录
        """
        save_dir = Path(save_dir) if save_dir else settings.VECTOR_STORE_DIR
        save_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存 FAISS 索引
        index_path = save_dir / settings.FAISS_INDEX_FILE
        faiss.write_index(self.index, str(index_path))
        
        # 保存元数据
        metadata = {
            "dimension": self.dimension,
            "index_type": self.index_type,
            "document_count": len(self.documents),
            "documents": [
                {
                    "content": doc.content,
                    "metadata": doc.metadata
                }
                for doc in self.documents
            ]
        }
        
        metadata_path = save_dir / settings.FAISS_METADATA_FILE
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 索引已保存到: {save_dir}")
        print(f"   - 索引文件: {index_path}")
        print(f"   - 元数据文件: {metadata_path}")
    
    @classmethod
    def load(cls, load_dir: str = None) -> 'FAISSStore':
        """
        加载索引和元数据
        
        Args:
            load_dir: 加载目录
            
        Returns:
            FAISSStore: 加载的存储实例
        """
        load_dir = Path(load_dir) if load_dir else settings.VECTOR_STORE_DIR
        
        index_path = load_dir / settings.FAISS_INDEX_FILE
        metadata_path = load_dir / settings.FAISS_METADATA_FILE
        
        if not index_path.exists() or not metadata_path.exists():
            raise FileNotFoundError(f"索引文件不存在: {load_dir}")
        
        # 加载元数据
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # 创建实例
        store = cls(
            dimension=metadata['dimension'],
            index_type=metadata['index_type']
        )
        
        # 加载 FAISS 索引
        store.index = faiss.read_index(str(index_path))
        
        # 恢复文档
        store.documents = [
            Document(
                content=doc_data['content'],
                metadata=doc_data['metadata']
            )
            for doc_data in metadata['documents']
        ]
        
        # 重建 ID 映射
        store.id_to_index = {i: i for i in range(len(store.documents))}
        
        print(f"✅ 索引已加载: {load_dir}")
        print(f"   - 文档数量: {len(store.documents)}")
        print(f"   - 索引类型: {store.index_type}")
        
        return store
    
    def clear(self):
        """清空索引"""
        self.index.reset()
        self.documents.clear()
        self.id_to_index.clear()
        print("✅ 索引已清空")