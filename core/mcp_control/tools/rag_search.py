# core/mcp_control/tools/rag_search.py
import requests 
class RAGSearchTool:
    """RAG 知识库搜索工具（同步版本）"""

    name = "search_knowledge_base"
    description = (
        "在内部知识库中搜索相关文档，"
        "适用于：背景查询、资料检索、事实核对。"
    )

    async def __call__(self, query: str) -> dict:
        """使用 requests 进行同步调用"""
        try:
            print(f"🔍 [RAG] 开始搜索: {query}")
            
            resp = requests.post(
                "http://127.0.0.1:9000/rag/search",
                json={"query": query},
                timeout=30,
                headers={"Content-Type": "application/json"}
            )
            resp.raise_for_status()
            raw_result = resp.json()
            
            # 提取结果
            results = raw_result.get('results', [])
            
            print(f"✅ [RAG] 搜索成功，返回 {len(results)} 条结果")
            
            # 格式化输出
            formatted_output = self._format_results(results)
            
            print(f"📝 [RAG] 格式化输出: {formatted_output[:200]}")
            
            # 👇 统一返回格式（关键！）
            return {
                "success": True,
                "result": raw_result,  # 原始结果
                "formatted_output": formatted_output,  # 格式化文本（用于对话）
                "query": query,
                "total": len(results)
            }
        
        except requests.exceptions.RequestException as e:
            print(f"❌ [RAG] 搜索失败: {type(e).__name__} - {e}")
            return {
                "success": False,
                "error": str(e),
                "query": query,
                "result": None,
                "formatted_output": "搜索失败"
            }
    
    def _format_results(self, results: list) -> str:
        """格式化搜索结果为可读文本"""
        if not results:
            return "未找到相关信息"
        
        formatted = []
        for i, doc in enumerate(results[:3], 1):  # 只取前3条
            source = doc.get('source', '未知来源')
            content = doc.get('content', '')
            score = doc.get('score', 0)
            
            # 👇 提取价格信息（如果有）
            formatted.append(
                f"{i}. {content[:200]}\n"
                f"   来源: {source} (相关度: {score:.2f})"
            )
        
        return "\n\n".join(formatted)