"""
Markdown 文档加载器
"""
from typing import List
from pathlib import Path
import re

from .base_loader import BaseLoader, Document


class MarkdownLoader(BaseLoader):
    """Markdown 文档加载器"""
    
    def __init__(self):
        super().__init__()
        self.supported_extensions = ['.md', '.markdown']
    
    def load(self, file_path: str) -> List[Document]:
        """
        加载 Markdown 文档
        
        Args:
            file_path: Markdown 文件路径
            
        Returns:
            List[Document]: 文档列表（整个文档作为一个 Document）
        """
        if not self.is_supported(file_path):
            raise ValueError(f"不支持的文件类型: {file_path}")
        
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        try:
            # 读取文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 提取标题（如果有）
            title = self._extract_title(content)
            
            # 创建元数据
            metadata = self._create_metadata(
                file_path,
                title=title if title else file_path.stem
            )
            
            return [Document(content=content, metadata=metadata)]
        
        except Exception as e:
            raise Exception(f"Markdown 文档加载失败: {e}")
    
    def _extract_title(self, content: str) -> str:
        """提取 Markdown 文档标题（第一个 # 标题）"""
        match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        return match.group(1).strip() if match else ""
    
    def load_by_sections(self, file_path: str) -> List[Document]:
        """
        按章节加载 Markdown 文档
        根据标题（#, ##, ### 等）将文档切分为多个部分
        
        Args:
            file_path: Markdown 文件路径
            
        Returns:
            List[Document]: 文档列表（每个章节一个 Document）
        """
        if not self.is_supported(file_path):
            raise ValueError(f"不支持的文件类型: {file_path}")
        
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        documents = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 按标题切分
            sections = self._split_by_headers(content)
            
            for i, section in enumerate(sections):
                if section['content'].strip():
                    metadata = self._create_metadata(
                        file_path,
                        section_index=i + 1,
                        section_title=section['title'],
                        section_level=section['level'],
                        total_sections=len(sections)
                    )
                    
                    documents.append(Document(
                        content=section['content'],
                        metadata=metadata
                    ))
        
        except Exception as e:
            raise Exception(f"Markdown 文档加载失败: {e}")
        
        return documents
    
    def _split_by_headers(self, content: str) -> List[dict]:
        """
        根据 Markdown 标题切分文档
        
        Returns:
            List[dict]: 每个元素包含 title, level, content
        """
        sections = []
        
        # 匹配标题的正则表达式
        header_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
        
        # 找到所有标题的位置
        headers = list(header_pattern.finditer(content))
        
        if not headers:
            # 没有标题，整个文档作为一个 section
            return [{
                'title': 'Content',
                'level': 0,
                'content': content
            }]
        
        # 添加第一个标题之前的内容（如果有）
        if headers[0].start() > 0:
            sections.append({
                'title': 'Introduction',
                'level': 0,
                'content': content[:headers[0].start()].strip()
            })
        
        # 处理每个标题及其内容
        for i, header in enumerate(headers):
            level = len(header.group(1))  # # 的数量
            title = header.group(2).strip()
            
            # 获取该标题下的内容
            start = header.end()
            end = headers[i + 1].start() if i + 1 < len(headers) else len(content)
            section_content = content[start:end].strip()
            
            sections.append({
                'title': title,
                'level': level,
                'content': f"{'#' * level} {title}\n\n{section_content}"
            })
        
        return sections