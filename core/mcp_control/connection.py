from contextlib import AsyncExitStack
from enum import Enum
import asyncio
from typing import Dict, Any, Optional
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


class ConnectionState(Enum):
    """连接状态枚举"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    READY = "ready"
    ERROR = "error"


class McpConnection:
    """MCP Connection 封装类
    
    封装单个 MCP Server 的连接，提供状态管理、健康检查和工具调用接口。
    """
    
    def __init__(self, server_id: str, url: str, timeout: int = 60, headers: Optional[Dict[str, str]] = None):
        self.server_id = server_id
        self.url = url
        self.timeout = timeout
        self.headers = headers or {}  # 保存自定义 headers
        self.session: Optional[ClientSession] = None
        self.exit_stack: Optional[AsyncExitStack] = None
        self.state = ConnectionState.DISCONNECTED
        self.health_check_failures = 0
        self.max_health_failures = 3
        print(f"[McpConnection:{server_id}] Initialized, url={url}, headers={bool(headers)}")

    async def connect(self) -> bool:
        """建立连接
        
        Returns:
            bool: 连接是否成功
        """
        try:
            print(f"[McpConnection:{self.server_id}] Connecting to {self.url}...")
            self.state = ConnectionState.CONNECTING
            
            # 验证 URL 格式
            if not self.url.startswith(('http://', 'https://')):
                raise ValueError(f"Invalid URL format: {self.url}. Must start with http:// or https://")
            
            self.exit_stack = AsyncExitStack()
            
            # 创建预配置的 httpx.AsyncClient 并设置 headers
            # 新版 streamable_http_client 需要在 httpx.AsyncClient 上配置 headers
            http_client = httpx.AsyncClient(
                headers=self.headers,
                timeout=httpx.Timeout(30.0, read=300.0)  # 30s 常规操作, 300s SSE 读取
            )
            
            # 进入异步上下文管理
            await self.exit_stack.enter_async_context(http_client)
            
            # 使用 streamable_http_client 建立 HTTP Stream 连接
            read, write, _ = await asyncio.wait_for(
                self.exit_stack.enter_async_context(
                    streamable_http_client(self.url, http_client=http_client)
                ),
                timeout=10.0  # 连接超时 10 秒
            )
            
            self.session = await self.exit_stack.enter_async_context(
                ClientSession(read, write)
            )
            
            # 初始化 MCP Session
            await asyncio.wait_for(
                self.session.initialize(),
                timeout=10.0
            )
            
            self.state = ConnectionState.READY
            self.health_check_failures = 0
            print(f"[McpConnection:{self.server_id}] Connected successfully")
            return True
            
        except asyncio.TimeoutError as e:
            print(f"[McpConnection:{self.server_id}] ERROR: Connection timeout after 10s")
            print(f"[McpConnection:{self.server_id}] Possible causes:")
            print(f"  - MCP server not running at {self.url}")
            print(f"  - Server is overloaded or not responding")
            print(f"  - Network latency is too high")
            self.state = ConnectionState.ERROR
            return False
        except ValueError as e:
            print(f"[McpConnection:{self.server_id}] ERROR: Invalid configuration - {e}")
            self.state = ConnectionState.ERROR
            return False
        except ConnectionError as e:
            print(f"[McpConnection:{self.server_id}] ERROR: Network connection failed - {e}")
            print(f"[McpConnection:{self.server_id}] Possible causes:")
            print(f"  - Network is unreachable to {self.url.split('/')[2] if '/' in self.url else self.url}")
            print(f"  - DNS resolution failed")
            print(f"  - Port is blocked by firewall")
            self.state = ConnectionState.ERROR
            return False
        except Exception as e:
            error_type = type(e).__name__
            print(f"[McpConnection:{self.server_id}] ERROR: Connection failed ({error_type}): {e}")
            print(f"[McpConnection:{self.server_id}] Please verify:")
            print(f"  1. MCP Server is running at {self.url}")
            print(f"  2. Network connectivity to {self.url.split('/')[2] if '/' in self.url else self.url}")
            print(f"  3. Authentication headers are correct (if required)")
            print(f"  4. Firewall rules allow connection")
            self.state = ConnectionState.ERROR
            return False

    async def close(self) -> None:
        """关闭连接"""
        print(f"[McpConnection:{self.server_id}] Closing connection...")
        
        if self.exit_stack:
            try:
                await self.exit_stack.aclose()
            except Exception as e:
                print(f"[McpConnection:{self.server_id}] Error closing: {e}")
        
        self.session = None
        self.exit_stack = None
        self.state = ConnectionState.DISCONNECTED
        print(f"[McpConnection:{self.server_id}] Connection closed")

    async def reconnect(self) -> bool:
        """重新连接
        
        Returns:
            bool: 重连是否成功
        """
        print(f"[McpConnection:{self.server_id}] Attempting reconnect...")
        await self.close()
        return await self.connect()

    async def health_check(self) -> bool:
        """健康检查
        
        Returns:
            bool: 连接是否健康
        """
        if self.state != ConnectionState.READY:
            return False
        
        try:
            if not self.session:
                return False
            
            # 使用 list_tools 作为健康检查
            await asyncio.wait_for(
                self.session.list_tools(),
                timeout=5.0
            )
            
            self.health_check_failures = 0
            return True
            
        except Exception as e:
            self.health_check_failures += 1
            print(f"[McpConnection:{self.server_id}] Health check failed ({self.health_check_failures}/{self.max_health_failures}): {e}")
            
            if self.health_check_failures >= self.max_health_failures:
                print(f"[McpConnection:{self.server_id}] Max health check failures reached, marking as ERROR")
                self.state = ConnectionState.ERROR
            
            return False

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """调用工具
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
            
        Returns:
            Dict[str, Any]: 调用结果，格式为 {"success": bool, "result": Any} 或 {"success": bool, "error": str}
        """
        if self.state != ConnectionState.READY:
            return {
                "success": False,
                "error": f"Connection not ready (state: {self.state.value})"
            }
        
        if not self.session:
            return {"success": False, "error": "Session not initialized"}
        
        try:
            print(f"[McpConnection:{self.server_id}] Calling tool {tool_name} with args: {arguments}")
            
            result = await asyncio.wait_for(
                self.session.call_tool(tool_name, arguments=arguments),
                timeout=self.timeout
            )
            
            print(f"[McpConnection:{self.server_id}] Tool call successful")
            
            # 将 CallToolResult 对象转换为可序列化的字典
            result_dict = self._serialize_call_tool_result(result)
            
            return {"success": True, "result": result_dict}
            
        except asyncio.TimeoutError:
            error_msg = f"Tool call timeout after {self.timeout}s"
            print(f"[McpConnection:{self.server_id}] {error_msg}")
            return {"success": False, "error": error_msg}
            
        except Exception as e:
            error_msg = str(e)
            print(f"[McpConnection:{self.server_id}] Tool call failed: {error_msg}")
            return {"success": False, "error": error_msg}
    
    def _serialize_call_tool_result(self, result: Any) -> Dict[str, Any]:
        """将 CallToolResult 对象序列化为字典
        
        Args:
            result: MCP SDK 返回的 CallToolResult 对象
            
        Returns:
            Dict[str, Any]: 可序列化的字典
        """
        # 如果 result 已经是字典，直接返回
        if isinstance(result, dict):
            return result
        
        # 如果是 CallToolResult 对象，提取其属性
        if hasattr(result, 'content'):
            serialized = {
                'content': result.content if hasattr(result, 'content') else None,
                'isError': result.isError if hasattr(result, 'isError') else False,
            }
            # 添加其他可能的属性
            if hasattr(result, 'meta'):
                serialized['meta'] = result.meta
            return serialized
        
        # 其他类型，尝试转换为字符串
        return {'content': str(result), 'isError': False}
