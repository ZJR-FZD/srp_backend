"""
测试文档加载和处理流程
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from src.document_loader.pdf_loader import PDFLoader
from src.document_loader.docx_loader import DOCXLoader
from src.document_loader.markdown_loader import MarkdownLoader
from src.text_processor.splitter import TextSplitter, SemanticSplitter
from src.text_processor.cleaner import TextCleaner


def test_pdf_loader():
    """测试 PDF 加载"""
    print("\n" + "="*60)
    print("测试 PDF 加载")
    print("="*60)
    
    loader = PDFLoader()
    pdf_dir = settings.PDF_DIR
    
    if not any(pdf_dir.glob("*.pdf")):
        print("⚠️  没有找到 PDF 文件，请在 data/documents/pdfs/ 目录下放置 PDF 文件")
        return
    
    documents = loader.load_directory(str(pdf_dir))
    
    print(f"\n✅ 共加载 {len(documents)} 个文档片段")
    
    if documents:
        print(f"\n示例文档:")
        doc = documents[0]
        print(f"  来源: {doc.metadata['source']}")
        print(f"  页码: {doc.metadata.get('page_number', 'N/A')}")
        print(f"  内容预览: {doc.content[:200]}...")


def test_docx_loader():
    """测试 Word 加载"""
    print("\n" + "="*60)
    print("测试 Word 文档加载")
    print("="*60)
    
    loader = DOCXLoader()
    docx_dir = settings.DOCX_DIR
    
    if not any(docx_dir.glob("*.docx")) and not any(docx_dir.glob("*.doc")):
        print("⚠️  没有找到 Word 文件，请在 data/documents/docx/ 目录下放置 Word 文件")
        return
    
    documents = loader.load_directory(str(docx_dir))
    
    print(f"\n✅ 共加载 {len(documents)} 个文档")
    
    if documents:
        print(f"\n示例文档:")
        doc = documents[0]
        print(f"  来源: {doc.metadata['source']}")
        print(f"  段落数: {doc.metadata.get('paragraphs_count', 'N/A')}")
        print(f"  内容预览: {doc.content[:200]}...")


def test_markdown_loader():
    """测试 Markdown 加载"""
    print("\n" + "="*60)
    print("测试 Markdown 文档加载")
    print("="*60)
    
    loader = MarkdownLoader()
    md_dir = settings.MARKDOWN_DIR
    
    if not any(md_dir.glob("*.md")) and not any(md_dir.glob("*.markdown")):
        print("⚠️  没有找到 Markdown 文件，请在 data/documents/markdown/ 目录下放置 Markdown 文件")
        return
    
    documents = loader.load_directory(str(md_dir))
    
    print(f"\n✅ 共加载 {len(documents)} 个文档")
    
    if documents:
        print(f"\n示例文档:")
        doc = documents[0]
        print(f"  来源: {doc.metadata['source']}")
        print(f"  标题: {doc.metadata.get('title', 'N/A')}")
        print(f"  内容预览: {doc.content[:200]}...")


def test_text_splitter():
    """测试文本切分"""
    print("\n" + "="*60)
    print("测试文本切分")
    print("="*60)
    
    # 创建测试文本
    test_text = """
    这是第一段文字。这段文字包含了一些内容，用来测试文本切分功能。
    我们需要确保切分后的文本块大小合适，并且保持语义完整性。
    
    这是第二段文字。它继续讨论文本切分的重要性。
    好的文本切分可以提高检索质量和生成答案的准确性。
    每个文本块应该包含完整的语义单元。
    
    这是第三段文字。它总结了前面的内容。
    """
    
    from src.document_loader.base_loader import Document
    
    doc = Document(
        content=test_text,
        metadata={"source": "test", "filename": "test.txt"}
    )
    
    # 测试标准切分
    splitter = TextSplitter(chunk_size=100, chunk_overlap=20)
    chunks = splitter.split_documents([doc])
    
    print(f"\n标准切分:")
    print(f"  原始文档: 1 个")
    print(f"  切分后: {len(chunks)} 个文本块")
    print(f"\n前3个文本块:")
    for i, chunk in enumerate(chunks[:3]):
        print(f"\n  块 {i+1} (长度: {len(chunk.content)}):")
        print(f"  {chunk.content[:80]}...")
    
    # 测试语义切分
    semantic_splitter = SemanticSplitter(chunk_size=150, chunk_overlap=30)
    semantic_chunks = semantic_splitter.split_documents([doc])
    
    print(f"\n\n语义切分:")
    print(f"  切分后: {len(semantic_chunks)} 个文本块")


def test_text_cleaner():
    """测试文本清洗"""
    print("\n" + "="*60)
    print("测试文本清洗")
    print("="*60)
    
    test_text = """
    这是一段测试文本  ，包含多余的   空格。
    
    
    还有多余的换行。
    
    包含 URL: https://example.com 和邮箱: test@example.com
    """
    
    from src.document_loader.base_loader import Document
    
    doc = Document(
        content=test_text,
        metadata={"source": "test"}
    )
    
    cleaner = TextCleaner(
        remove_urls=True,
        remove_emails=True,
        remove_extra_whitespace=True
    )
    
    cleaned_docs = cleaner.clean_documents([doc])
    
    print(f"\n原始文本:")
    print(repr(test_text))
    print(f"\n清洗后:")
    print(repr(cleaned_docs[0].content))


def main():
    """主测试函数"""
    print("\n" + "🚀 "*30)
    print("文档加载与处理测试")
    print("🚀 "*30)
    
    # 创建必要的目录
    settings.create_directories()
    
    # 显示配置
    settings.display()
    
    # 运行测试
    test_pdf_loader()
    test_docx_loader()
    test_markdown_loader()
    test_text_splitter()
    test_text_cleaner()
    
    print("\n" + "="*60)
    print("✅ 所有测试完成！")
    print("="*60)
    print("\n💡 下一步:")
    print("  1. 在 data/documents/ 目录下添加你的文档")
    print("  2. 运行 build_index.py 构建向量索引")
    print("  3. 开始使用问答系统\n")


if __name__ == "__main__":
    main()