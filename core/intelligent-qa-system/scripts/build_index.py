"""
构建向量索引脚本
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from src.document_loader.pdf_loader import PDFLoader
from src.document_loader.docx_loader import DOCXLoader
from src.document_loader.markdown_loader import MarkdownLoader
from src.text_processor.splitter import SemanticSplitter, MarkdownStructuredSplitter
from src.text_processor.cleaner import TextCleaner
from src.vector_store.store_manager import VectorStoreManager


def load_all_documents():
    """加载所有文档"""
    print("\n" + "="*60)
    print("📚 加载文档")
    print("="*60)
    
    all_documents = []
    
    # 加载 PDF
    pdf_loader = PDFLoader()
    pdf_dir = settings.PDF_DIR
    if any(pdf_dir.glob("*.pdf")):
        print(f"\n📄 加载 PDF 文件...")
        pdf_docs = pdf_loader.load_directory(str(pdf_dir))
        all_documents.extend(pdf_docs)
        print(f"   ✅ PDF: {len(pdf_docs)} 个页面")
    
    # 加载 Word
    docx_loader = DOCXLoader()
    docx_dir = settings.DOCX_DIR
    if any(docx_dir.glob("*.docx")) or any(docx_dir.glob("*.doc")):
        print(f"\n📄 加载 Word 文件...")
        docx_docs = docx_loader.load_directory(str(docx_dir))
        all_documents.extend(docx_docs)
        print(f"   ✅ Word: {len(docx_docs)} 个文档")
    
    # 加载 Markdown
    md_loader = MarkdownLoader()
    md_dir = settings.MARKDOWN_DIR
    if any(md_dir.glob("*.md")) or any(md_dir.glob("*.markdown")):
        print(f"\n📄 加载 Markdown 文件...")
        md_docs = md_loader.load_directory(str(md_dir))
        all_documents.extend(md_docs)
        print(f"   ✅ Markdown: {len(md_docs)} 个文档")
    
    print(f"\n{'='*60}")
    print(f"📊 总计加载: {len(all_documents)} 个文档")
    print(f"{'='*60}")
    
    return all_documents


def process_documents(documents):
    """处理文档：清洗和切分"""
    print("\n" + "="*60)
    print("🔧 处理文档")
    print("="*60)
    
    # 文本清洗
    print(f"\n🧹 清洗文本...")
    cleaner = TextCleaner(
        remove_urls=True,
        remove_emails=True,
        remove_extra_whitespace=True,
        remove_special_chars=False,
        lowercase=False
    )
    cleaned_docs = cleaner.clean_documents(documents)
    print(f"   ✅ 清洗完成: {len(cleaned_docs)} 个文档")
    
    # 👇 新增：根据文档类型选择分块器
    print(f"\n✂️  切分文本...")
    
    # 检测是否为 Markdown 文档
    md_docs = [doc for doc in cleaned_docs if doc.metadata.get("filename", "").endswith(".md")]
    other_docs = [doc for doc in cleaned_docs if doc not in md_docs]
    
    all_chunks = []
    
    # Markdown 文档使用结构化分块器
    if md_docs:
        print(f"   📝 使用 Markdown 结构化分块器处理 {len(md_docs)} 个 .md 文件")
        md_splitter = MarkdownStructuredSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            keep_heading_hierarchy=True,  # 保留标题层级
            split_list_items=True,         # 列表项独立分块
            max_heading_levels=3           # 最多保留3级标题
        )
        md_chunks = md_splitter.split_documents(md_docs)
        all_chunks.extend(md_chunks)
        print(f"   ✅ Markdown 切分完成: {len(md_chunks)} 个块")
    
    # 其他文档使用语义分块器
    if other_docs:
        print(f"   📄 使用语义分块器处理 {len(other_docs)} 个其他文件")
        semantic_splitter = SemanticSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP
        )
        other_chunks = semantic_splitter.split_documents(other_docs)
        all_chunks.extend(other_chunks)
        print(f"   ✅ 语义切分完成: {len(other_chunks)} 个块")
    
    # 显示示例
    print(f"\n📄 示例块（前3个）:")
    for i, chunk in enumerate(all_chunks[:3], 1):
        print(f"\n   === 块 {i} ===")
        print(f"   标题路径: {chunk.metadata.get('heading_path', [])}")
        print(f"   类型: {chunk.metadata.get('section_type', 'N/A')}")
        print(f"   内容预览:")
        print(f"   {chunk.content[:150]}{'...' if len(chunk.content) > 150 else ''}")
    
    # 统计信息
    avg_length = sum(len(chunk.content) for chunk in all_chunks) / len(all_chunks) if all_chunks else 0
    print(f"\n📊 统计信息:")
    print(f"   - 原始文档: {len(documents)}")
    print(f"   - 清洗后: {len(cleaned_docs)}")
    print(f"   - 切分后: {len(all_chunks)}")
    print(f"   - 平均块大小: {avg_length:.0f} 字符")
    
    return all_chunks

def build_vector_index(documents, embedding_model=None):
    """构建向量索引"""
    # 创建向量存储管理器
    manager = VectorStoreManager(embedding_model=embedding_model)
    
    # 构建索引
    store = manager.build_index(
        documents=documents,
        batch_size=32,
        save=True
    )
    
    return manager

def main():
    """主函数"""
    print("\n" + "🚀 "*30)
    print("向量索引构建工具")
    print("🚀 "*30)
    
    # 显示配置
    settings.display()
    
    # 1. 加载文档
    documents = load_all_documents()
    
    if not documents:
        print("\n⚠️  警告: 没有找到任何文档！")
        print("   请在以下目录添加文档:")
        print(f"   - PDF: {settings.PDF_DIR}")
        print(f"   - Word: {settings.DOCX_DIR}")
        print(f"   - Markdown: {settings.MARKDOWN_DIR}")
        return
    
    # 2. 处理文档
    chunks = process_documents(documents)
    
    # 3. 构建索引
    manager = build_vector_index(
        chunks,
        embedding_model=settings.EMBEDDING_MODEL
    )
    
    # 4. 显示统计
    stats = manager.get_stats()
    print("\n" + "="*60)
    print("📊 索引统计")
    print("="*60)
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    print("\n" + "="*60)
    print("✅ 索引构建完成！")
    print("="*60)
    print(f"\n💾 索引已保存到: {settings.VECTOR_STORE_DIR}")

if __name__ == "__main__":
    main()