# test_mcp_tools.py
"""
测试 MCP 工具（RAG 搜索 + Web 搜索）
"""

import asyncio
import sys
from pathlib import Path
# 将项目根目录加入 sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from core.mcp_control.tools.rag_search import RAGSearchTool

async def test_rag_search():
    """测试 RAG 搜索工具"""
    print("=" * 60)
    print("测试 1: RAG 知识库搜索")
    print("=" * 60)
    
    tool = RAGSearchTool()
    
    test_queries = [
        "海鲜至尊堡价格。",
    ]
    
    for query in test_queries:
        print(f"\n🔍 查询: {query}")
        try:
            result = await tool(query=query)
            
            if "error" in result:
                print(f"❌ 错误: {result['error']}")
            else:
                print(f"✅ 成功!")
                # 👇 修复：RAG 返回的是 'results' 字段，不是 'documents'
                results = result.get('results', [])
                print(f"   文档数: {len(results)}")
                print(f"   总结果数: {result.get('total', 0)}")
                
                if results:
                    print(f"\n   前 3 条结果:")
                    for i, doc in enumerate(results[:3], 1):
                        print(f"\n   [{i}] 来源: {doc.get('source', 'unknown')}")
                        print(f"       相关度: {doc.get('score', 0):.3f}")
                        print(f"       内容: {doc.get('content', '')[:100]}...")
                    
        except Exception as e:
            print(f"❌ 异常: {type(e).__name__} - {e}")
            import traceback
            traceback.print_exc()
        
        await asyncio.sleep(0.5)

async def main():
    """主测试流程"""
    print("\n" + "🚀" * 30)
    print("MCP 工具测试开始")
    print("🚀" * 30 + "\n")
    
    # 测试 1: RAG 搜索
    try:
        await test_rag_search()
    except Exception as e:
        print(f"\n⚠️  RAG 搜索测试失败: {e}")
        print("   可能原因: RAG 服务未启动 (http://127.0.0.1:9000)")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())