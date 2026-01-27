"""
文本清洗模块
"""
import re
from typing import List

from ..document_loader.base_loader import Document

class TextCleaner:
    """文本清洗器"""
    
    def __init__(
        self,
        remove_urls: bool = True,
        remove_emails: bool = True,
        remove_extra_whitespace: bool = True,
        remove_special_chars: bool = False,
        lowercase: bool = False
    ):
        """
        初始化文本清洗器
        
        Args:
            remove_urls: 是否移除 URL
            remove_emails: 是否移除邮箱
            remove_extra_whitespace: 是否移除多余空白
            remove_special_chars: 是否移除特殊字符
            lowercase: 是否转为小写
        """
        self.remove_urls = remove_urls
        self.remove_emails = remove_emails
        self.remove_extra_whitespace = remove_extra_whitespace
        self.remove_special_chars = remove_special_chars
        self.lowercase = lowercase
    
    def clean_documents(self, documents: List[Document]) -> List[Document]:
        """
        清洗文档列表
        
        Args:
            documents: 文档列表
            
        Returns:
            List[Document]: 清洗后的文档列表
        """
        cleaned_docs = []
        
        for doc in documents:
            cleaned_content = self.clean_text(doc.content)
            
            # 只保留非空文档
            if cleaned_content.strip():
                cleaned_docs.append(Document(
                    content=cleaned_content,
                    metadata=doc.metadata
                ))
        
        return cleaned_docs
    
    def clean_text(self, text: str) -> str:
        """
        清洗文本
        
        Args:
            text: 输入文本
            
        Returns:
            str: 清洗后的文本
        """
        if not text:
            return ""
        
        # 移除 URL
        if self.remove_urls:
            text = self._remove_urls(text)
        
        # 移除邮箱
        if self.remove_emails:
            text = self._remove_emails(text)
        
        # 移除特殊字符
        if self.remove_special_chars:
            text = self._remove_special_chars(text)
        
        # 移除多余空白
        if self.remove_extra_whitespace:
            text = self._remove_extra_whitespace(text)
        
        # 转为小写
        if self.lowercase:
            text = text.lower()
        
        return text.strip()
    
    def _remove_urls(self, text: str) -> str:
        """移除 URL"""
        # 匹配 http/https URL
        url_pattern = r'https?://\S+|www\.\S+'
        return re.sub(url_pattern, '', text)
    
    def _remove_emails(self, text: str) -> str:
        """移除邮箱地址"""
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        return re.sub(email_pattern, '', text)
    
    def _remove_special_chars(self, text: str) -> str:
        """
        移除特殊字符（保留中英文、数字、基本标点）
        谨慎使用，可能会影响某些领域的专业内容
        """
        # 保留中文、英文、数字、常用标点
        pattern = r'[^\u4e00-\u9fa5a-zA-Z0-9\s\.,;:!?()[\]{}"\'`\-—]'
        return re.sub(pattern, '', text)
    
    def _remove_extra_whitespace(self, text: str) -> str:
        """移除多余空白"""
        # 移除多余空格
        text = re.sub(r' +', ' ', text)
        
        # 移除多余换行（保留段落分隔）
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        
        # 移除行首行尾空格
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(lines)
        
        return text

def normalize_document_content(documents: List[Document]) -> List[Document]:
    """
    快速标准化文档内容的便捷函数
    
    Args:
        documents: 文档列表
        
    Returns:
        List[Document]: 标准化后的文档列表
    """
    cleaner = TextCleaner(
        remove_urls=True,
        remove_emails=True,
        remove_extra_whitespace=True,
        remove_special_chars=False,  # 不移除特殊字符，避免影响专业内容
        lowercase=False
    )
    
    return cleaner.clean_documents(documents)