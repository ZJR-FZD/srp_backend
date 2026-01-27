"""
RAG 问答链
"""
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from config.settings import settings
from ..vector_store.store_manager import VectorStoreManager
from ..retriever.semantic_search import SemanticRetriever, SearchResult
from ..llm import get_llm, BaseLLM

@dataclass
class QAResult:
    """问答结果"""
    question: str
    answer: str
    sources: List[SearchResult]
    model: str
    usage: Optional[Dict[str, int]] = None
    
    def format_answer_with_sources(self, max_sources: int = 3) -> str:
        """格式化答案和来源"""
        result = f"**问题:** {self.question}\n\n"
        result += f"**回答:** {self.answer}\n\n"
        
        if self.sources:
            result += f"**参考来源:**\n"
            for i, source in enumerate(self.sources[:max_sources], 1):
                filename = source.document.metadata.get('filename', 'Unknown')
                score = source.score
                result += f"{i}. {filename} (相似度: {score:.2f})\n"
        
        return result
    
    def __str__(self):
        return self.answer


class RAGChain:
    """RAG 问答链"""
    
    def __init__(
        self,
        store_manager: VectorStoreManager,
        llm: Optional[BaseLLM] = None,
        llm_type: str = None
    ):
        """
        初始化 RAG 链
        
        Args:
            store_manager: 向量存储管理器
            llm: LLM 实例
            llm_type: LLM 类型（如果未提供 llm 实例）
        """
        self.store_manager = store_manager
        self.retriever = SemanticRetriever(store_manager)
        
        # 初始化 LLM
        if llm:
            self.llm = llm
        else:
            self.llm = get_llm(llm_type)
        
        # 系统提示
        self.system_prompt = """你是一个专业的智能问答助手。请基于提供的上下文信息准确、详细地回答用户的问题。

要求：
1. 如果上下文中有相关信息，请基于这些信息详细回答
2. 如果上下文中没有相关信息，请明确说明"根据提供的信息无法回答这个问题"
3. 不要编造信息，只基于提供的上下文回答
4. 回答要清晰、有条理
5. 如果可能，可以引用上下文中的具体内容"""
        
        print(f"✅ RAG 链初始化成功！LLM: {self.llm.model}")
    
    def query(
        self,
        question: str,
        top_k: int = None,
        threshold: float = None,
        return_sources: bool = True,
        stream: bool = False
    ) -> QAResult:
        """
        查询并生成答案
        
        Args:
            question: 用户问题
            top_k: 检索文档数量
            threshold: 相似度阈值
            return_sources: 是否返回来源
            stream: 是否流式生成
            
        Returns:
            QAResult: 问答结果
        """
        # 1. 检索相关文档
        search_results = self.retriever.retrieve(
            query=question,
            top_k=top_k or settings.TOP_K,
            threshold=threshold or settings.SIMILARITY_THRESHOLD
        )
        
        if not search_results:
            # 没有找到相关文档
            return QAResult(
                question=question,
                answer="抱歉，我在知识库中没有找到与您的问题相关的信息。请尝试重新表述您的问题，或者询问其他内容。",
                sources=[],
                model=self.llm.model
            )
        
        # 2. 格式化上下文
        context = self.retriever.format_context(
            search_results,
            max_length=3000,
            include_metadata=True
        )
        
        # 3. 生成答案
        if stream:
            # 流式生成（用于实时显示）
            return self._stream_answer(question, context, search_results)
        else:
            # 一次性生成
            response = self.llm.generate(
                prompt=self._create_prompt(question, context),
                system_prompt=self.system_prompt
            )
            
            return QAResult(
                question=question,
                answer=response.content,
                sources=search_results if return_sources else [],
                model=self.llm.model,
                usage=response.usage
            )
    
    def chat(
        self,
        question: str,
        history: List[tuple] = None,
        top_k: int = None,
        return_sources: bool = True
    ) -> QAResult:
        """
        多轮对话
        
        Args:
            question: 当前问题
            history: 历史对话 [(question, answer), ...]
            top_k: 检索文档数量
            return_sources: 是否返回来源
            
        Returns:
            QAResult: 问答结果
        """
        history = history or []
        
        # 1. 检索相关文档
        search_results = self.retriever.retrieve(
            query=question,
            top_k=top_k or settings.TOP_K
        )
        
        if not search_results:
            return QAResult(
                question=question,
                answer="抱歉，我在知识库中没有找到与您的问题相关的信息。",
                sources=[],
                model=self.llm.model
            )
        
        # 2. 格式化上下文
        context = self.retriever.format_context(search_results, max_length=3000)
        
        # 3. 构建消息列表
        messages = self.llm.format_chat_history(history, question, context)
        
        # 4. 生成答案
        response = self.llm.chat(messages)
        
        return QAResult(
            question=question,
            answer=response.content,
            sources=search_results if return_sources else [],
            model=self.llm.model,
            usage=response.usage
        )
    
    def _create_prompt(self, question: str, context: str) -> str:
        """创建提示"""
        return f"""基于以下上下文信息回答问题：

上下文信息：
{context}

问题：{question}

请提供详细、准确的回答："""
    
    def _stream_answer(
        self,
        question: str,
        context: str,
        search_results: List[SearchResult]
    ):
        """
        流式生成答案（生成器）
        
        Args:
            question: 问题
            context: 上下文
            search_results: 搜索结果
            
        Yields:
            str: 答案片段
        """
        prompt = self._create_prompt(question, context)
        
        full_answer = ""
        for chunk in self.llm.stream_generate(prompt, self.system_prompt):
            full_answer += chunk
            yield chunk
        
        # 返回完整结果（可选）
        return QAResult(
            question=question,
            answer=full_answer,
            sources=search_results,
            model=self.llm.model
        )
    
    def batch_query(
        self,
        questions: List[str],
        show_progress: bool = True
    ) -> List[QAResult]:
        """
        批量查询
        
        Args:
            questions: 问题列表
            show_progress: 是否显示进度
            
        Returns:
            List[QAResult]: 结果列表
        """
        results = []
        
        iterator = questions
        if show_progress:
            from tqdm import tqdm
            iterator = tqdm(questions, desc="批量查询")
        
        for question in iterator:
            try:
                result = self.query(question)
                results.append(result)
            except Exception as e:
                print(f"\n⚠️  问题查询失败: {question}")
                print(f"   错误: {e}")
                results.append(QAResult(
                    question=question,
                    answer=f"查询出错: {e}",
                    sources=[],
                    model=self.llm.model
                ))
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        store_stats = self.store_manager.get_stats()
        
        return {
            **store_stats,
            "llm_model": self.llm.model,
            "llm_temperature": self.llm.temperature,
            "llm_max_tokens": self.llm.max_tokens
        }