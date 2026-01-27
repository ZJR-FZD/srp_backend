"""
PDF 文档加载器
"""
from typing import List
import PyPDF2
from pathlib import Path

from .base_loader import BaseLoader, Document


class PDFLoader(BaseLoader):
    """PDF 文档加载器"""
    
    def __init__(self):
        super().__init__()
        self.supported_extensions = ['.pdf']
    
    def load(self, file_path: str) -> List[Document]:
        """
        加载 PDF 文档
        
        Args:
            file_path: PDF 文件路径
            
        Returns:
            List[Document]: 文档列表（每页一个文档）
        """
        if not self.is_supported(file_path):
            raise ValueError(f"不支持的文件类型: {file_path}")
        
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        documents = []
        
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                total_pages = len(pdf_reader.pages)
                
                for page_num in range(total_pages):
                    page = pdf_reader.pages[page_num]
                    text = page.extract_text()
                    
                    # 清理文本
                    text = self._clean_text(text)
                    
                    if text.strip():  # 只添加非空页面
                        metadata = self._create_metadata(
                            file_path,
                            page_number=page_num + 1,
                            total_pages=total_pages
                        )
                        
                        documents.append(Document(
                            content=text,
                            metadata=metadata
                        ))
        
        except Exception as e:
            raise Exception(f"PDF 加载失败: {e}")
        
        return documents
    
    def _clean_text(self, text: str) -> str:
        """清理提取的文本"""
        if not text:
            return ""
        
        # 移除多余的空行
        lines = [line.strip() for line in text.split('\n')]
        lines = [line for line in lines if line]
        
        # 合并行
        text = '\n'.join(lines)
        
        return text
    
    def load_merged(self, file_path: str) -> Document:
        """
        加载 PDF 并合并所有页面为一个文档
        
        Args:
            file_path: PDF 文件路径
            
        Returns:
            Document: 合并后的文档
        """
        documents = self.load(file_path)
        
        # 合并所有页面内容
        merged_content = "\n\n".join([doc.content for doc in documents])
        
        # 使用第一页的元数据，但移除页码信息
        metadata = documents[0].metadata.copy()
        metadata.pop('page_number', None)
        
        return Document(
            content=merged_content,
            metadata=metadata
        )