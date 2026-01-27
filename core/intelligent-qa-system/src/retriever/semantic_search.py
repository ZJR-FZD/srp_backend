"""
语义检索模块
"""
from typing import List, Dict, Any
from dataclasses import dataclass

from config.settings import settings
from ..vector_store.store_manager import VectorStoreManager
from ..document_loader.base_loader import Document


@dataclass
class SearchResult:
    """搜索结果"""
    document: Document
    score: float
    rank: int
    
    def __repr__(self):
        preview = self.document.content[:100] + "..." if len(self.document.content) > 100 else self.document.content
        return f"SearchResult(rank={self.rank}, score={self.score:.3f}, content='{preview}')"


class SemanticRetriever:
    """语义检索器"""
    
    def __init__(self, store_manager: VectorStoreManager):
        """
        初始化检索器
        
        Args:
            store_manager: 向量存储管理器
        """
        self.store_manager = store_manager
    
    def retrieve(
        self,
        query: str,
        top_k: int = None,
        threshold: float = None,
        return_scores: bool = True
    ) -> List[SearchResult]:
        """
        检索相关文档
        
        Args:
            query: 查询文本
            top_k: 返回文档数量
            threshold: 相似度阈值
            return_scores: 是否返回分数
            
        Returns:
            List[SearchResult]: 搜索结果列表
        """
        top_k = settings.TOP_K
        threshold = settings.SIMILARITY_THRESHOLD
        print(f"🔍 进行语义检索: top_k={top_k}, threshold={threshold}")
        # 搜索
        results = self.store_manager.search(
            query=query,
            k=top_k,
            threshold=threshold
        )
        
        # 转换为 SearchResult
        search_results = []
        for rank, (doc, score) in enumerate(results, 1):
            search_results.append(SearchResult(
                document=doc,
                score=score,
                rank=rank
            ))
        
        return search_results
    
    def retrieve_with_context(
        self,
        query: str,
        top_k: int = None,
        context_window: int = 2
    ) -> List[SearchResult]:
        """
        检索文档并包含上下文
        对于切分的文档，尝试获取前后文
        
        Args:
            query: 查询文本
            top_k: 返回文档数量
            context_window: 上下文窗口大小（前后各取几个块）
            
        Returns:
            List[SearchResult]: 搜索结果列表
        """
        # 先进行基本检索
        results = self.retrieve(query, top_k)
        
        # TODO: 实现上下文扩展逻辑
        # 如果文档有 chunk_index 信息，可以找到相邻的块
        
        return results
    
    def format_context(
        self,
        results: List[SearchResult],
        max_length: int = 2000,
        include_metadata: bool = True
    ) -> str:
        """
        格式化检索结果为上下文字符串
        
        Args:
            results: 搜索结果列表
            max_length: 最大长度
            include_metadata: 是否包含元数据
            
        Returns:
            str: 格式化的上下文
        """
        context_parts = []
        current_length = 0
        
        for result in results:
            # 格式化单个结果
            if include_metadata:
                source = result.document.metadata.get('source', 'Unknown')
                header = f"\n[来源: {source}]\n"
            else:
                header = f"\n[文档 {result.rank}]\n"
            
            content = result.document.content
            
            # 检查长度
            part = header + content
            if current_length + len(part) > max_length:
                # 截断最后一个文档
                remaining = max_length - current_length
                if remaining > 100:  # 至少保留100字符
                    content = content[:remaining - len(header) - 10] + "..."
                    part = header + content
                    context_parts.append(part)
                break
            
            context_parts.append(part)
            current_length += len(part)
        
        return "\n".join(context_parts)
    
    def display_results(self, results: List[SearchResult], max_display: int = 3):
        """
        显示搜索结果（用于调试）
        
        Args:
            results: 搜索结果列表
            max_display: 最多显示的结果数
        """
        print(f"\n{'='*60}")
        print(f"检索结果 (共 {len(results)} 条)")
        print(f"{'='*60}\n")
        
        for result in results[:max_display]:
            print(f"排名 {result.rank} | 相似度: {result.score:.3f}")
            print(f"来源: {result.document.metadata.get('source', 'Unknown')}")
            
            # 显示内容预览
            content = result.document.content
            preview = content[:200] + "..." if len(content) > 200 else content
            print(f"内容: {preview}")
            print(f"{'-'*60}\n")


class HybridRetriever(SemanticRetriever):
    """混合检索器（可扩展支持关键词检索等）"""
    
    def __init__(self, store_manager: VectorStoreManager):
        super().__init__(store_manager)
    
    def retrieve(
        self,
        query: str,
        top_k: int = None,
        use_rerank: bool = False
    ) -> List[SearchResult]:
        """
        混合检索
        
        Args:
            query: 查询文本
            top_k: 返回文档数量
            use_rerank: 是否使用重排序
            
        Returns:
            List[SearchResult]: 搜索结果
        """
        # 先进行语义检索
        results = super().retrieve(query, top_k=top_k * 2 if use_rerank else top_k)
        
        # TODO: 添加其他检索方式（BM25、关键词匹配等）
        
        # TODO: 重排序
        if use_rerank:
            results = self._rerank(query, results)
            results = results[:top_k]
        
        return results
    
    def _rerank(self, query: str, results: List[SearchResult]) -> List[SearchResult]:
        """
        重排序（简单实现）
        
        Args:
            query: 查询文本
            results: 搜索结果
            
        Returns:
            List[SearchResult]: 重排序后的结果
        """
        # TODO: 实现更复杂的重排序逻辑
        # 可以使用交叉编码器模型或其他方法
        
        return results