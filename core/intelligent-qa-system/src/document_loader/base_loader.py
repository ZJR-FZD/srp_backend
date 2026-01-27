"""
文档加载器基类
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass


@dataclass
class Document:
    """文档数据结构"""
    content: str                    # 文档内容
    metadata: Dict[str, Any]        # 元数据
    
    def __repr__(self):
        preview = self.content[:100] + "..." if len(self.content) > 100 else self.content
        return f"Document(content='{preview}', metadata={self.metadata})"


class BaseLoader(ABC):
    """文档加载器基类"""
    
    def __init__(self):
        self.supported_extensions = []
    
    @abstractmethod
    def load(self, file_path: str) -> List[Document]:
        """
        加载文档
        
        Args:
            file_path: 文件路径
            
        Returns:
            List[Document]: 文档列表
        """
        pass
    
    def is_supported(self, file_path: str) -> bool:
        """检查文件是否支持"""
        file_ext = Path(file_path).suffix.lower()
        return file_ext in self.supported_extensions
    
    def _create_metadata(self, file_path: str, **kwargs) -> Dict[str, Any]:
        """创建元数据"""
        file_path = Path(file_path)
        metadata = {
            "source": str(file_path),
            "filename": file_path.name,
            "file_type": file_path.suffix.lower(),
            "file_size": file_path.stat().st_size if file_path.exists() else 0,
        }
        metadata.update(kwargs)
        return metadata
    
    def load_directory(self, directory_path: str) -> List[Document]:
        """
        加载目录下所有支持的文档
        
        Args:
            directory_path: 目录路径
            
        Returns:
            List[Document]: 文档列表
        """
        directory = Path(directory_path)
        if not directory.exists():
            raise FileNotFoundError(f"目录不存在: {directory_path}")
        
        documents = []
        for file_path in directory.rglob("*"):
            if file_path.is_file() and self.is_supported(str(file_path)):
                try:
                    docs = self.load(str(file_path))
                    documents.extend(docs)
                    print(f"✅ 加载成功: {file_path.name}")
                except Exception as e:
                    print(f"❌ 加载失败: {file_path.name} - {e}")
        
        return documents