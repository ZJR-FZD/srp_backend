# core/mcp_control/tools/web_search.py
"""
DuckDuckGo 网络搜索工具（免费，无需 API Key）
"""

import httpx
import asyncio
from typing import List, Dict, Any
from urllib.parse import quote


class DuckDuckGoSearchTool:
    """DuckDuckGo 搜索工具"""
    
    name = "web_search"
    description = (
        "使用 DuckDuckGo 搜索引擎进行网络搜索，"
        "适用于：实时信息查询、新闻搜索、知识查找。"
        "返回相关网页的标题、摘要和链接。"
    )
    
    async def __call__(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """执行搜索
        
        Args:
            query: 搜索关键词
            max_results: 最大结果数量，默认 5
            
        Returns:
            dict: {
                "query": str,
                "results": [
                    {
                        "title": str,
                        "snippet": str,
                        "link": str
                    }
                ]
            }
        """
        try:
            # 使用 DuckDuckGo Instant Answer API（免费）
            url = f"https://api.duckduckgo.com/?q={quote(query)}&format=json"
            
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
                headers={"User-Agent": "Mozilla/5.0"}
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
            
            # 解析结果
            results = []
            
            # 1. 摘要答案（Abstract）
            if data.get("Abstract"):
                results.append({
                    "title": data.get("Heading", "摘要"),
                    "snippet": data.get("Abstract"),
                    "link": data.get("AbstractURL", "")
                })
            
            # 2. 相关主题（RelatedTopics）
            for topic in data.get("RelatedTopics", [])[:max_results]:
                if isinstance(topic, dict) and "Text" in topic:
                    results.append({
                        "title": topic.get("Text", "").split(" - ")[0][:100],
                        "snippet": topic.get("Text", ""),
                        "link": topic.get("FirstURL", "")
                    })
            
            # 如果没有结果，使用备用搜索方案
            if not results:
                print(f"[DuckDuckGo] No results from API, trying HTML search...")
                results = await self._html_search(query, max_results)
            
            return {
                "query": query,
                "results": results[:max_results],
                "total": len(results)
            }
            
        except Exception as e:
            print(f"[DuckDuckGo] Search error: {e}")
            return {
                "query": query,
                "results": [],
                "error": str(e)
            }
    
    async def _html_search(self, query: str, max_results: int) -> List[Dict[str, str]]:
        """备用方案：解析 HTML 搜索结果"""
        try:
            url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
            
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
                headers={"User-Agent": "Mozilla/5.0"},
                follow_redirects=True
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                html = resp.text
            
            # 简单的正则解析（生产环境建议用 BeautifulSoup）
            import re
            
            results = []
            # 匹配搜索结果块
            pattern = r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>.*?<a[^>]*class="result__snippet"[^>]*>(.*?)</a>'
            matches = re.findall(pattern, html, re.DOTALL)
            
            for link, title, snippet in matches[:max_results]:
                # 清理 HTML 标签
                title = re.sub(r'<[^>]+>', '', title).strip()
                snippet = re.sub(r'<[^>]+>', '', snippet).strip()
                
                results.append({
                    "title": title,
                    "snippet": snippet,
                    "link": link
                })
            
            return results
            
        except Exception as e:
            print(f"[DuckDuckGo] HTML search error: {e}")
            return []


# 如果你想用更强大的库（需要安装 duckduckgo-search）
# pip install duckduckgo-search
class DuckDuckGoSearchToolAdvanced:
    """高级版本（需要安装 duckduckgo-search 库）"""
    
    name = "web_search_advanced"
    description = "使用 DuckDuckGo 进行高级网络搜索"
    
    async def __call__(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        try:
            from duckduckgo_search import DDGS
            
            # 在异步环境中运行同步代码
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                lambda: list(DDGS().text(query, max_results=max_results))
            )
            
            formatted_results = [
                {
                    "title": r.get("title", ""),
                    "snippet": r.get("body", ""),
                    "link": r.get("href", "")
                }
                for r in results
            ]
            
            return {
                "query": query,
                "results": formatted_results,
                "total": len(formatted_results)
            }
            
        except ImportError:
            return {
                "query": query,
                "results": [],
                "error": "请安装 duckduckgo-search: pip install duckduckgo-search"
            }
        except Exception as e:
            return {
                "query": query,
                "results": [],
                "error": str(e)
            }