"""
测试查询脚本
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from src.vector_store.store_manager import VectorStoreManager
from src.retriever.semantic_search import SemanticRetriever


def test_search(manager: VectorStoreManager):
    """测试搜索功能"""
    print("\n" + "="*60)
    print("🔍 测试语义搜索")
    print("="*60)
    
    # 创建检索器
    retriever = SemanticRetriever(manager)
    
    # 测试查询列表
    test_queries = [
        "处女座的性格特点是什么？",
    ]
    
    for query in test_queries:
        print(f"\n查询: {query}")
        print("-"*60)
        
        # 检索
        results = retriever.retrieve(
            query=query
        )
        
        if not results:
            print("⚠️  未找到相关文档")
            continue
        
        # 显示结果
        for result in results:
            print(f"\n排名: {result.rank} | 相似度: {result.score:.3f}")
            
            # 显示来源
            source = result.document.metadata.get('source', 'Unknown')
            filename = Path(source).name if source != 'Unknown' else 'Unknown'
            print(f"来源: {filename}")
            
            # 显示页码或块信息
            if 'page_number' in result.document.metadata:
                print(f"页码: {result.document.metadata['page_number']}")
            elif 'chunk_index' in result.document.metadata:
                chunk_idx = result.document.metadata['chunk_index']
                total_chunks = result.document.metadata.get('total_chunks', '?')
                print(f"文本块: {chunk_idx + 1}/{total_chunks}")
            
            # 显示内容预览
            content = result.document.content
            preview = content[:300] + "..." if len(content) > 300 else content
            print(f"\n内容:\n{preview}")
            print("-"*60)


def interactive_search(manager: VectorStoreManager):
    """交互式搜索"""
    print("\n" + "="*60)
    print("💬 交互式搜索模式")
    print("="*60)
    print("输入查询问题（输入 'quit' 或 'exit' 退出）")
    print("="*60)
    
    retriever = SemanticRetriever(manager)
    
    while True:
        try:
            # 获取用户输入
            query = input("\n🔍 查询: ").strip()
            
            if not query:
                continue
            
            if query.lower() in ['quit', 'exit', 'q']:
                print("\n👋 再见！")
                break
            
            # 检索
            results = retriever.retrieve(
                query=query
            )
            
            if not results:
                print("⚠️  未找到相关文档，请尝试其他查询")
                continue
            
            # 显示结果
            print(f"\n找到 {len(results)} 个相关文档:\n")
            
            for result in results:
                source = result.document.metadata.get('source', 'Unknown')
                filename = Path(source).name if source != 'Unknown' else 'Unknown'
                
                print(f"{result.rank}. [{filename}] 相似度: {result.score:.3f}")
                
                # 内容预览
                content = result.document.content
                preview = content[:150] + "..." if len(content) > 150 else content
                print(f"   {preview}\n")
        
        except KeyboardInterrupt:
            print("\n\n👋 再见！")
            break
        except Exception as e:
            print(f"\n❌ 错误: {e}")


def display_stats(manager: VectorStoreManager):
    """显示索引统计"""
    print("\n" + "="*60)
    print("📊 索引统计信息")
    print("="*60)
    
    stats = manager.get_stats()
    
    for key, value in stats.items():
        print(f"{key}: {value}")
    
    print("="*60)


def main():
    """主函数"""
    print("\n" + "🔍 "*30)
    print("查询测试工具")
    print("🔍 "*30)
    
    # 加载索引
    try:
        print(f"\n🔄 正在加载索引...")
        manager = VectorStoreManager(embedding_model=settings.EMBEDDING_MODEL)
        manager.load_index()
        
        # 显示统计
        display_stats(manager)
        
        # 测试搜索
        test_search(manager)
        
        # 交互式搜索
        interactive_search(manager)
    
    except FileNotFoundError:
        print("\n❌ 错误: 未找到索引文件")
        print("   请先运行: python scripts/build_index.py")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()