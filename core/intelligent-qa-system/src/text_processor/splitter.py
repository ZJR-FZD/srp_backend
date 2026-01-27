"""
文本切分模块
"""
from typing import List
import re

from ..document_loader.base_loader import Document
from config.settings import settings


class TextSplitter:
    """文本切分器"""
    
    def __init__(
        self,
        chunk_size: int = None,
        chunk_overlap: int = None,
        separators: List[str] = None
    ):
        """
        初始化文本切分器
        
        Args:
            chunk_size: 每个文本块的字符数
            chunk_overlap: 块之间的重叠字符数
            separators: 切分分隔符列表（按优先级排序）
        """
        self.chunk_size = chunk_size or settings.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP
        
        # 默认分隔符（中文友好）
        self.separators = separators or [
            "\n\n",      # 段落
            "\n",        # 行
            "。",        # 中文句号
            "！",        # 中文感叹号
            "？",        # 中文问号
            "；",        # 中文分号
            ".",         # 英文句号
            "!",         # 英文感叹号
            "?",         # 英文问号
            ";",         # 英文分号
            " ",         # 空格
            "",          # 字符级别（最后手段）
        ]
    
    def split_documents(self, documents: List[Document]) -> List[Document]:
        """
        切分文档列表
        
        Args:
            documents: 文档列表
            
        Returns:
            List[Document]: 切分后的文档列表
        """
        split_docs = []
        
        for doc in documents:
            chunks = self.split_text(doc.content)
            
            for i, chunk in enumerate(chunks):
                # 复制元数据并添加块信息
                metadata = doc.metadata.copy()
                metadata.update({
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "chunk_size": len(chunk)
                })
                
                split_docs.append(Document(
                    content=chunk,
                    metadata=metadata
                ))
        
        return split_docs
    
    def split_text(self, text: str) -> List[str]:
        """
        递归切分文本
        
        Args:
            text: 输入文本
            
        Returns:
            List[str]: 切分后的文本块列表
        """
        if not text:
            return []
        
        # 如果文本小于chunk_size，直接返回
        if len(text) <= self.chunk_size:
            return [text]
        
        # 尝试使用分隔符切分
        return self._split_with_separators(text, self.separators)
    
    def _split_with_separators(
        self,
        text: str,
        separators: List[str]
    ) -> List[str]:
        """
        使用分隔符递归切分文本
        
        Args:
            text: 输入文本
            separators: 分隔符列表
            
        Returns:
            List[str]: 切分后的文本块
        """
        chunks = []
        
        # 选择当前分隔符
        separator = separators[0] if separators else ""
        
        # 如果是最后一个分隔符（空字符串），直接按字符切分
        if separator == "":
            return self._split_by_size(text)
        
        # 使用当前分隔符切分
        splits = text.split(separator)
        
        current_chunk = ""
        for split in splits:
            # 如果单个 split 就超过 chunk_size，需要进一步切分
            if len(split) > self.chunk_size:
                # 先保存当前 chunk
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                
                # 递归使用下一个分隔符
                sub_chunks = self._split_with_separators(
                    split,
                    separators[1:]
                )
                chunks.extend(sub_chunks)
            
            else:
                # 尝试添加到当前 chunk
                test_chunk = current_chunk + separator + split if current_chunk else split
                
                if len(test_chunk) <= self.chunk_size:
                    current_chunk = test_chunk
                else:
                    # 当前 chunk 已满，保存并开始新 chunk
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    
                    # 使用 overlap 开始新 chunk
                    if self.chunk_overlap > 0 and current_chunk:
                        overlap_text = current_chunk[-self.chunk_overlap:]
                        current_chunk = overlap_text + separator + split
                    else:
                        current_chunk = split
        
        # 添加最后一个 chunk
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return [c for c in chunks if c]  # 过滤空字符串
    
    def _split_by_size(self, text: str) -> List[str]:
        """
        按固定大小切分文本（最后手段）
        
        Args:
            text: 输入文本
            
        Returns:
            List[str]: 切分后的文本块
        """
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + self.chunk_size
            chunks.append(text[start:end])
            
            # 应用 overlap
            start = end - self.chunk_overlap if self.chunk_overlap > 0 else end
        
        return chunks


class SemanticSplitter(TextSplitter):
    """语义感知的文本切分器"""
    
    def split_text(self, text: str) -> List[str]:
        """
        基于语义的智能切分
        尽量在句子边界切分，保持语义完整性
        
        Args:
            text: 输入文本
            
        Returns:
            List[str]: 切分后的文本块
        """
        # 首先按段落切分
        paragraphs = re.split(r'\n\n+', text)
        
        chunks = []
        current_chunk = ""
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            # 如果单个段落就超过 chunk_size，需要进一步切分
            if len(para) > self.chunk_size:
                # 先保存当前 chunk
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                
                # 按句子切分段落
                sentences = self._split_into_sentences(para)
                temp_chunk = ""
                
                for sentence in sentences:
                    if len(sentence) > self.chunk_size:
                        # 单个句子太长，使用父类方法处理
                        if temp_chunk:
                            chunks.append(temp_chunk.strip())
                            temp_chunk = ""
                        chunks.extend(super().split_text(sentence))
                    elif len(temp_chunk) + len(sentence) <= self.chunk_size:
                        temp_chunk += sentence
                    else:
                        chunks.append(temp_chunk.strip())
                        temp_chunk = sentence
                
                if temp_chunk:
                    chunks.append(temp_chunk.strip())
            
            # 段落不超过 chunk_size
            elif len(current_chunk) + len(para) + 2 <= self.chunk_size:
                current_chunk += ("\n\n" if current_chunk else "") + para
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para
        
        # 添加最后一个 chunk
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return [c for c in chunks if c]
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """
        将文本切分为句子
        
        Args:
            text: 输入文本
            
        Returns:
            List[str]: 句子列表
        """
        # 中英文句子分隔符
        sentence_endings = r'[。！？\.!?；;]+'
        
        # 切分句子
        sentences = re.split(f'({sentence_endings})', text)
        
        # 合并句子和标点
        result = []
        for i in range(0, len(sentences) - 1, 2):
            sentence = sentences[i]
            punctuation = sentences[i + 1] if i + 1 < len(sentences) else ''
            combined = (sentence + punctuation).strip()
            if combined:
                result.append(combined)
        
        # 处理最后一个元素
        if len(sentences) % 2 == 1 and sentences[-1].strip():
            result.append(sentences[-1].strip())
        
        return result