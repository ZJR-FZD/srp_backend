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
from core.mcp_control.tools.web_search import DuckDuckGoSearchTool


async def test_rag_search():
    """测试 RAG 搜索工具"""
    print("=" * 60)
    print("测试 1: RAG 知识库搜索")
    print("=" * 60)
    
    tool = RAGSearchTool()
    
    test_queries = [
        "处女座性格",
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


async def test_web_search():
    """测试 Web 搜索工具"""
    print("\n" + "=" * 60)
    print("测试 2: DuckDuckGo 网络搜索")
    print("=" * 60)
    
    tool = DuckDuckGoSearchTool()
    
    test_queries = [
        "人工智能的最新进展",
    ]
    
    for query in test_queries:
        print(f"\n🔍 查询: {query}")
        try:
            result = await tool(query=query, max_results=3)
            
            if "error" in result:
                print(f"❌ 错误: {result['error']}")
            else:
                print(f"✅ 成功!")
                print(f"   结果数: {result.get('total', 0)}")
                
                for i, item in enumerate(result.get('results', []), 1):
                    print(f"\n   [{i}] {item['title'][:80]}")
                    print(f"       摘要: {item['snippet'][:100]}...")
                    # 👇 清理 DuckDuckGo 的相对链接
                    link = item['link']
                    if link.startswith('//'):
                        link = 'https:' + link
                    print(f"       链接: {link}")
                    
        except Exception as e:
            print(f"❌ 异常: {type(e).__name__} - {e}")
            import traceback
            traceback.print_exc()
        
        await asyncio.sleep(1)


async def test_tool_index():
    """测试 ToolIndex 工具注册"""
    print("\n" + "=" * 60)
    print("测试 3: ToolIndex 工具注册")
    print("=" * 60)
    
    from core.mcp_control.tool_index import ToolIndex
    
    tool_index = ToolIndex()
    
    print(f"\n📋 已注册工具数: {len(tool_index.tools)}")
    
    for tool_name, entry in tool_index.tools.items():
        print(f"\n   ✓ {tool_name}")
        print(f"     Server: {entry.server_id}")
        print(f"     描述: {entry.description[:60]}...")
        print(f"     标签: {', '.join(entry.tags)}")


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
    
    # 测试 2: Web 搜索
    try:
        await test_web_search()
    except Exception as e:
        print(f"\n⚠️  Web 搜索测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 测试 3: ToolIndex
    try:
        await test_tool_index()
    except Exception as e:
        print(f"\n⚠️  ToolIndex 测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "✨" * 30)
    print("测试完成!")
    print("✨" * 30 + "\n")


if __name__ == "__main__":
    asyncio.run(main())