"""
测试 RAG 问答系统
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from src.vector_store.store_manager import VectorStoreManager
from src.qa_chain.rag_chain import RAGChain


def test_single_query(rag_chain: RAGChain):
    """测试单个查询"""
    print("\n" + "="*60)
    print("🧪 测试单个查询")
    print("="*60)
    
    test_questions = [
        "处女座的性格特点是什么？",
    ]
    
    for i, question in enumerate(test_questions, 1):
        print(f"\n{'='*60}")
        print(f"问题 {i}: {question}")
        print(f"{'='*60}")
        
        try:
            # 查询
            result = rag_chain.query(
                question=question,
                top_k=3,
                return_sources=True
            )
            
            # 显示答案
            print(f"\n💡 回答:\n{result.answer}")
            
            # 显示来源
            if result.sources:
                print(f"\n📚 参考来源:")
                for j, source in enumerate(result.sources, 1):
                    filename = source.document.metadata.get('filename', 'Unknown')
                    score = source.score
                    print(f"  {j}. {filename} (相似度: {score:.3f})")
            
            # 显示使用信息
            if result.usage:
                print(f"\n📊 Token 使用:")
                print(f"  输入: {result.usage.get('prompt_tokens', 'N/A')}")
                print(f"  输出: {result.usage.get('completion_tokens', 'N/A')}")
                print(f"  总计: {result.usage.get('total_tokens', 'N/A')}")
        
        except Exception as e:
            print(f"\n❌ 查询失败: {e}")
            import traceback
            traceback.print_exc()


def test_chat(rag_chain: RAGChain):
    """测试多轮对话"""
    print("\n" + "="*60)
    print("🧪 测试多轮对话")
    print("="*60)
    
    # 模拟对话历史
    history = []
    
    questions = [
        "什么是注意力机制？",
        "它有什么优点？",
        "在实际应用中如何使用？"
    ]
    
    for i, question in enumerate(questions, 1):
        print(f"\n{'='*60}")
        print(f"第 {i} 轮")
        print(f"{'='*60}")
        print(f"问题: {question}")
        
        try:
            # 查询
            result = rag_chain.chat(
                question=question,
                history=history,
                top_k=3
            )
            
            print(f"\n回答: {result.answer}")
            
            # 添加到历史
            history.append((question, result.answer))
        
        except Exception as e:
            print(f"\n❌ 查询失败: {e}")


def interactive_qa(rag_chain: RAGChain):
    """交互式问答"""
    print("\n" + "="*60)
    print("💬 交互式问答模式")
    print("="*60)
    print("输入问题获取答案（输入 'quit' 或 'exit' 退出）")
    print("输入 'clear' 清除对话历史")
    print("="*60)
    
    history = []
    
    while True:
        try:
            # 获取用户输入
            question = input("\n🤔 您的问题: ").strip()
            
            if not question:
                continue
            
            if question.lower() in ['quit', 'exit', 'q']:
                print("\n👋 再见！")
                break
            
            if question.lower() == 'clear':
                history.clear()
                print("✅ 对话历史已清除")
                continue
            
            # 查询
            print("\n🤖 正在思考...")
            result = rag_chain.chat(
                question=question,
                history=history,
                top_k=5
            )
            
            # 显示答案
            print(f"\n💡 {result.answer}")
            
            # 显示来源
            if result.sources:
                print(f"\n📚 参考来源:")
                for i, source in enumerate(result.sources[:3], 1):
                    filename = source.document.metadata.get('filename', 'Unknown')
                    score = source.score
                    print(f"  {i}. {filename} (相似度: {score:.3f})")
            
            # 添加到历史
            history.append((question, result.answer))
            
            # 限制历史长度
            if len(history) > 5:
                history = history[-5:]
        
        except KeyboardInterrupt:
            print("\n\n👋 再见！")
            break
        except Exception as e:
            print(f"\n❌ 错误: {e}")
            import traceback
            traceback.print_exc()


def display_stats(rag_chain: RAGChain):
    """显示系统统计"""
    print("\n" + "="*60)
    print("📊 系统统计信息")
    print("="*60)
    
    stats = rag_chain.get_stats()
    
    for key, value in stats.items():
        print(f"{key}: {value}")
    
    print("="*60)


def main():
    """主函数"""
    print("\n" + "🤖 "*30)
    print("RAG 问答系统测试")
    print("🤖 "*30)
    
    try:
        # 1. 加载索引
        print(f"\n🔄 正在加载索引...")
        store_manager = VectorStoreManager(
            embedding_model=settings.EMBEDDING_MODEL
        )
        store_manager.load_index()
        
        # 2. 创建 RAG 链
        print(f"\n🔄 正在初始化 RAG 链...")
        rag_chain = RAGChain(
            store_manager=store_manager,
            llm_type=settings.DEFAULT_LLM
        )
        
        # 3. 显示统计
        display_stats(rag_chain)
        
        # 4. 运行测试
        print("\n" + "="*60)
        print("选择测试模式:")
        print("  1. 测试预设问题")
        print("  2. 测试多轮对话")
        print("  3. 交互式问答")
        print("  4. 全部测试")
        print("="*60)
        
        choice = input("\n请选择 (1-4, 默认3): ").strip() or "3"
        
        if choice == "1":
            test_single_query(rag_chain)
        elif choice == "2":
            test_chat(rag_chain)
        elif choice == "3":
            interactive_qa(rag_chain)
        elif choice == "4":
            test_single_query(rag_chain)
            test_chat(rag_chain)
            interactive_qa(rag_chain)
        else:
            print("❌ 无效选择")
    
    except FileNotFoundError:
        print("\n❌ 错误: 未找到索引文件")
        print("   请先运行: python scripts/build_index.py")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()