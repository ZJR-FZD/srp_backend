import json
import os
import asyncio
from typing import Dict, Any, Optional

from core.mcp_control.protocols import LLMClientProtocol
from core.mcp_control.connection import McpConnection
from core.mcp_control.tool_index import ToolIndex
from core.mcp_control.router import McpRouter


class McpManager:
    """
MCP Manager - MCP Controller 的门面类
    
    协调所有子模块，提供统一的对外接口。
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    async def initialize(self, config_path: str, llm_client: LLMClientProtocol, agent=None) -> None:
        """初始化 MCP Manager
        
        Args:
            config_path: MCP Server 配置文件路径
            llm_client: LLM 客户端实例（符合 LLMClientProtocol 协议）
            agent: RobotAgent 实例（可选，用于访问统一任务队列）
        """
        if self._initialized:
            print("[McpManager] Already initialized, skipping...")
            return
        
        print("[McpManager] Initializing...")
        
        # 1. 加载配置
        print(f"[McpManager] Loading config from {config_path}")
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        
        # 2. 初始化 Connection Manager
        print("[McpManager] Initializing connections...")
        self.connections: Dict[str, McpConnection] = {}
        connection_failures = []
        
        for s in cfg.get("mcp_servers", []):
            server_id = s["id"]
            url = s["url"]
            timeout = s.get("timeout", 60)
            headers = s.get("headers", {})  # 从配置中读取自定义 headers
            
            conn = McpConnection(server_id, url, timeout, headers=headers)
            success = await conn.connect()
            
            if success:
                self.connections[server_id] = conn
                print(f"[McpManager] Connected to {server_id}")
            else:
                connection_failures.append(server_id)
                print(f"[McpManager] Failed to connect to {server_id}")
        
        # 检查是否有成功的连接
        if not self.connections:
            print(f"[McpManager] WARNING: No MCP servers connected successfully")
            print(f"[McpManager] Failed servers: {', '.join(connection_failures)}")
            print(f"[McpManager] Tool Index will be empty, Router will not be able to select tools")
        else:
            print(f"[McpManager] Successfully connected to {len(self.connections)} server(s)")
        
        # 3. 初始化 Tool Index
        print("[McpManager] Initializing Tool Index...")
        self.tool_index = ToolIndex()
        
        # 读取缓存配置
        cache_ttl_seconds = cfg.get("cache_ttl_seconds", 3600)  # 默认1小时
        force_refresh_on_init = cfg.get("force_refresh_on_init", False)
        
        # 生成缓存文件路径
        config_dir = os.path.dirname(os.path.abspath(config_path))
        index_path = os.path.join(config_dir, "mcp_tool_index.json")
        
        # 尝试从缓存加载
        await self.tool_index.load_from_file(index_path)
        
        # 判断是否需要同步
        need_sync = await self.tool_index.should_sync(index_path, cache_ttl_seconds, force_refresh_on_init)
        
        if need_sync:
            print("[McpManager] Syncing tools from MCP servers...")
            print(f"[McpManager] Connected servers: {len(self.connections)}/{len(cfg.get('mcp_servers', []))}")
            
            # 记录同步前的工具数量
            tools_before_sync = len(self.tool_index.tools)
            
            # 从连接同步工具
            await self.tool_index.sync_from_servers(self.connections)
            
            # 判断同步是否成功：至少有一个Server连接成功
            tools_after_sync = len(self.tool_index.tools)
            has_connected_servers = len(self.connections) > 0
            
            if has_connected_servers:
                # 至少有一个Server连接成功，保存缓存（即使工具数为0）
                await self.tool_index.save_to_file(index_path)
                print(f"[McpManager] Sync complete: {tools_after_sync} tools indexed, cache saved")
                if tools_after_sync == 0:
                    print(f"[McpManager] WARNING: No tools retrieved from connected servers")
            else:
                # 所有Server连接失败
                if tools_before_sync > 0:
                    # 有缓存数据可用，使用过期缓存
                    print(f"[McpManager] WARNING: All servers failed, using stale cache ({tools_before_sync} tools)")
                    if self.tool_index.last_sync:
                        print(f"[McpManager] Stale cache last_sync: {self.tool_index.last_sync}")
                else:
                    # 无缓存数据
                    print(f"[McpManager] ERROR: No cache available and all servers failed, tool index is empty")
        else:
            print(f"[McpManager] Using cached tools ({len(self.tool_index.tools)} tools)")
        
        # 4. 初始化 Router
        print("[McpManager] Initializing Router...")
        self.router = McpRouter(llm_client, self.tool_index)
        
        # 注意：多轮任务执行已迁移到统一任务队列架构（McpExecutor）
        
        # 5. 启动后台任务（简化版，暂不实现定时同步）
        # TODO: 启动 Tool Index 定时同步任务
        # TODO: 启动 Connection 健康检查任务
        
        self._initialized = True
        print("[McpManager] Initialization complete")

    async def submit_task(self, goal: str, context: Dict[str, Any] = None) -> str:
        """提交任务（已废弃）
        
        **此方法已废弃**：多轮任务执行已迁移到统一任务队列架构，请使用 McpExecutor。
        
        Args:
            goal: 任务目标描述
            context: 可选上下文信息
            
        Returns:
            str: 任务 ID
            
        Raises:
            NotImplementedError: 此方法已废弃，不应再使用
        """
        raise NotImplementedError(
            "McpManager.submit_task() has been deprecated. "
            "Please use unified task queue to submit MCP_CALL tasks instead."
        )

    def get_task_status(self, task_id: str):
        """查询任务状态（已废弃）
        
        **此方法已废弃**：多轮任务执行已迁移到统一任务队列架构，请使用 McpExecutor。
        
        Args:
            task_id: 任务 ID
            
        Raises:
            NotImplementedError: 此方法已废弃，不应再使用
        """
        raise NotImplementedError(
            "McpManager.get_task_status() has been deprecated. "
            "Please use unified task queue (agent.task_queue.get_by_id()) instead."
        )

    def get_task_detail(self, task_id: str):
        """获取任务详情（已废弃）
        
        **此方法已废弃**：多轮任务执行已迁移到统一任务队列架构，请使用 McpExecutor。
        
        Args:
            task_id: 任务 ID
            
        Raises:
            NotImplementedError: 此方法已废弃，不应再使用
        """
        raise NotImplementedError(
            "McpManager.get_task_detail() has been deprecated. "
            "Please use unified task queue (agent.task_queue.get_by_id()) instead."
        )

    def cancel_task(self, task_id: str) -> bool:
        """取消任务（已废弃）
        
        **此方法已废弃**：多轮任务执行已迁移到统一任务队列架构，请使用 McpExecutor。
        
        Args:
            task_id: 任务 ID
            
        Raises:
            NotImplementedError: 此方法已废弃，不应再使用
        """
        raise NotImplementedError(
            "McpManager.cancel_task() has been deprecated. "
            "Please use unified task queue to cancel tasks instead."
        )

    def list_all_tasks(self) -> list:
        """列出所有任务（已废弃）
        
        **此方法已废弃**：多轮任务执行已迁移到统一任务队列架构，请使用 McpExecutor。
        
        Raises:
            NotImplementedError: 此方法已废弃，不应再使用
        """
        raise NotImplementedError(
            "McpManager.list_all_tasks() has been deprecated. "
            "Please use unified task queue (agent.task_queue.list_all()) instead."
        )
    
    async def close(self) -> None:
        """关闭所有连接"""
        print("[McpManager] Closing all connections...")
        
        for server_id, conn in self.connections.items():
            await conn.close()
        
        self._initialized = False
        print("[McpManager] All connections closed")
