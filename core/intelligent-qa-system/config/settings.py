"""
配置文件 - 管理所有系统参数和API密钥
"""
import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class Settings:
    """系统配置类"""
    
    # ==================== 路径配置 ====================
    BASE_DIR = Path(__file__).resolve().parent.parent
    DATA_DIR = BASE_DIR / "data"
    DOCUMENTS_DIR = DATA_DIR / "documents"
    VECTOR_STORE_DIR = DATA_DIR / "vector_store"
    
    # 文档类型目录
    PDF_DIR = DOCUMENTS_DIR / "pdfs"
    DOCX_DIR = DOCUMENTS_DIR / "docx"
    MARKDOWN_DIR = DOCUMENTS_DIR / "markdown"
    
    # ==================== API 配置 ====================
    # Qwen API
    QWEN_API_KEY: Optional[str] = os.getenv("QWEN_API_KEY")
    QWEN_API_BASE: str = "https://dashscope.aliyuncs.com/api/v1"
    
    # DeepSeek API
    DEEPSEEK_API_KEY: Optional[str] = os.getenv("DEEPSEEK_API_KEY")
    DEEPSEEK_API_BASE: str = "https://api.deepseek.com/v1"
    
    # ==================== 文本处理配置 ====================
    # 文本切分参数
    CHUNK_SIZE: int = 500  # 每个文本块的字符数
    CHUNK_OVERLAP: int = 50  # 块之间的重叠字符数
    
    # 支持的文件扩展名
    SUPPORTED_EXTENSIONS = {
        'pdf': ['.pdf'],
        'docx': ['.docx', '.doc'],
        'markdown': ['.md', '.markdown']
    }
    
    # ==================== Embedding 配置 ====================
    # 向量化模型选择: 'qwen' 或 'local'
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "qwen")
    
    # 本地 Embedding 模型
    LOCAL_EMBEDDING_MODEL: str = "BAAI/bge-small-zh-v1.5"  # 中文模型
    
    # Qwen Embedding 模型
    QWEN_EMBEDDING_MODEL: str = "text-embedding-v1"
    
    # Embedding 向量维度
    EMBEDDING_DIMENSION: int = 512  # bge-small-zh-v1.5 的维度
    
    # ==================== 向量数据库配置 ====================
    # FAISS 索引类型: 'Flat', 'IVFFlat', 'HNSW'
    FAISS_INDEX_TYPE: str = "Flat"  # 小数据集用 Flat，大数据集用 IVFFlat
    
    # FAISS 索引文件名
    FAISS_INDEX_FILE: str = "faiss_index.bin"
    FAISS_METADATA_FILE: str = "metadata.json"
    
    # ==================== 检索配置 ====================
    # 检索返回的文档数量
    TOP_K: int = 5
    
    # 相似度下限 (0-1) 
    SIMILARITY_THRESHOLD: float = 0.35

    # ==================== LLM 配置 ====================
    # 默认使用的 LLM: 'qwen', 'deepseek', 'openai'
    DEFAULT_LLM: str = os.getenv("DEFAULT_LLM", "qwen")
    
    # Qwen 模型
    QWEN_MODEL: str = "qwen-plus"  # qwen-turbo, qwen-plus, qwen-max
    
    # DeepSeek 模型
    DEEPSEEK_MODEL: str = "deepseek-chat"
    
    # LLM 生成参数
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 2000
    
    # ==================== 日志配置 ====================
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = "logs/qa_system.log"
    
    @classmethod
    def display(cls):
        """显示当前配置"""
        print("\n" + "="*50)
        print("智能问答系统配置")
        print("="*50)
        print(f"📁 基础目录: {cls.BASE_DIR}")
        print(f"📁 文档目录: {cls.DOCUMENTS_DIR}")
        print(f"📁 向量库目录: {cls.VECTOR_STORE_DIR}")
        print(f"\n🤖 Embedding 模型: {cls.EMBEDDING_MODEL}")
        if cls.EMBEDDING_MODEL == "local":
            print(f"   本地模型: {cls.LOCAL_EMBEDDING_MODEL}")
        print(f"\n🧠 LLM 模型: {cls.DEFAULT_LLM}")
        print(f"\n📊 文本切分: chunk_size={cls.CHUNK_SIZE}, overlap={cls.CHUNK_OVERLAP}")
        print(f"🔍 检索参数: top_k={cls.TOP_K}, threshold={cls.SIMILARITY_THRESHOLD}")
        print("="*50 + "\n")


# 创建全局配置实例
settings = Settings()

if __name__ == "__main__":
    settings.display()