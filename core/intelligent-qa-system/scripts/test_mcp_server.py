"""
测试 MCP 服务器功能
"""
import json
import subprocess
import sys
from pathlib import Path


def test_mcp_tools():
    """测试 MCP 工具"""
    
    print("="*60)
    print("测试 MCP 服务器")
    print("="*60)
    
    # 测试用例
    test_cases = [
        {
            "name": "获取知识库统计",
            "tool": "get_knowledge_base_stats",
            "arguments": {}
        },
        {
            "name": "列出所有文档",
            "tool": "list_documents",
            "arguments": {}
        },
        {
            "name": "搜索知识库",
            "tool": "search_knowledge_base",
            "arguments": {
                "query": "处女座的性格",
                "top_k": 3,
                "min_score": 0.3
            }
        },
        {
            "name": "问答测试",
            "tool": "ask_question",
            "arguments": {
                "question": "白羊座有什么性格特点？",
                "top_k": 3,
                "include_sources": True
            }
        }
    ]
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n{'='*60}")
        print(f"测试 {i}: {test['name']}")
        print(f"{'='*60}")
        
        # 构建 MCP 请求
        request = {
            "jsonrpc": "2.0",
            "id": i,
            "method": "tools/call",
            "params": {
                "name": test['tool'],
                "arguments": test['arguments']
            }
        }
        
        print(f"\n📤 请求:")
        print(json.dumps(request, indent=2, ensure_ascii=False))
        
        try:
            # 调用 MCP 服务器
            result = subprocess.run(
                [sys.executable, "mcp_server.py"],
                input=json.dumps(request) + "\n",
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent
            )
            
            if result.stdout:
                print(f"\n📥 响应:")
                response = json.loads(result.stdout.strip())
                print(json.dumps(response, indent=2, ensure_ascii=False))
            
            if result.stderr:
                print(f"\n⚠️  错误:")
                print(result.stderr)
        
        except Exception as e:
            print(f"\n❌ 测试失败: {e}")


def show_mcp_config():
    """显示 MCP 配置说明"""
    print("\n" + "="*60)
    print("MCP 配置说明")
    print("="*60)
    
    print("""
1. 将 mcp_config.json 的内容添加到 Claude Desktop 的配置文件中：

   macOS: ~/Library/Application Support/Claude/claude_desktop_config.json
   Windows: %APPDATA%\\Claude\\claude_desktop_config.json

2. 修改配置中的路径为你的实际路径

3. 填入你的 API Keys

4. 重启 Claude Desktop

5. 在 Claude 中可以使用以下工具：
   - search_knowledge_base: 搜索知识库
   - ask_question: 基于知识库回答问题
   - get_knowledge_base_stats: 获取统计信息
   - list_documents: 列出所有文档
   - search_by_source: 在指定文档中搜索
""")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="测试 MCP 服务器")
    parser.add_argument(
        "--config",
        action="store_true",
        help="显示配置说明"
    )
    
    args = parser.parse_args()
    
    if args.config:
        show_mcp_config()
    else:
        test_mcp_tools()