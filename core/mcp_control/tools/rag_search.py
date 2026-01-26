import httpx
import asyncio

class RAGSearchTool:
    """
    通过 HTTP 调用外部 RAG 服务
    适配低版本 httpx，解决 502/TypeError 问题
    """

    name = "search_knowledge_base"
    description = (
        "在内部知识库中搜索相关文档，"
        "适用于：背景查询、资料检索、事实核对。"
    )

    async def __call__(self, query: str) -> dict:
        # 适配低版本 httpx：移除 family 参数，改用其他方式避免 IPv6 问题
        try:
            # 方案1：异步调用（适配所有 httpx 版本）
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=10.0),  # 超时配置
                verify=False,  # 跳过 SSL 验证
                headers={"Content-Type": "application/json"}
            ) as client:
                # 关键：明确使用 127.0.0.1（而非 localhost），避免 IPv6 解析
                resp = await client.post(
                    "http://127.0.0.1:9000/rag/search",
                    json={"query": query},
                    http2=False  # 禁用 HTTP/2（低版本 httpx 也支持）
                )
                resp.raise_for_status()
                return resp.json()
                
        except Exception as e:
            # 方案2：异步调用失败 → 降级为同步 requests（和你的 test_rag_http.py 逻辑一致）
            print(f"⚠️  异步调用失败，降级为同步调用：{type(e).__name__} - {str(e)[:50]}")
            import requests
            resp = requests.post(
                "http://127.0.0.1:9000/rag/search",
                json={"query": query},
                timeout=30,
                headers={"Content-Type": "application/json"}
            )
            resp.raise_for_status()
            return resp.json()