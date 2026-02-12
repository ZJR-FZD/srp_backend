# core/server/connection_manager.py
"""WebSocket 连接管理器

负责管理智能体间的 WebSocket 连接，提供点对点和广播消息能力
"""

import asyncio
import time
from typing import Dict, Any, Optional, List, Set
from fastapi import WebSocket


class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self, max_connections: int = 100):
        """初始化连接管理器

        Args:
            max_connections: 最大连接数
        """
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_metadata: Dict[str, Dict[str, Any]] = {}
        self.max_connections = max_connections
        self._lock = asyncio.Lock()  # 添加异步锁保护
    
    async def register(self, agent_id: str, websocket: WebSocket) -> bool:
        """注册新连接

        Args:
            agent_id: 智能体标识
            websocket: WebSocket 连接

        Returns:
            bool: 是否成功注册
        """
        async with self._lock:
            if len(self.active_connections) >= self.max_connections:
                print(f"[ConnectionManager] Max connections ({self.max_connections}) reached")
                return False

            self.active_connections[agent_id] = websocket
            self.connection_metadata[agent_id] = {
                "connected_at": time.time(),
                "last_activity": time.time()
            }
            print(f"[ConnectionManager] Agent '{agent_id}' registered. Total connections: {len(self.active_connections)}")
            return True
    
    def unregister(self, agent_id: str) -> None:
        """注销连接

        Args:
            agent_id: 智能体标识
        """
        # 同步删除，使用 try-except 避免 KeyError
        try:
            if agent_id in self.active_connections:
                del self.active_connections[agent_id]
            if agent_id in self.connection_metadata:
                del self.connection_metadata[agent_id]
            print(f"[ConnectionManager] Agent '{agent_id}' unregistered. Total connections: {len(self.active_connections)}")
        except Exception as e:
            print(f"[ConnectionManager] Error unregistering '{agent_id}': {e}")
    
    async def send_to_agent(self, agent_id: str, message: Dict[str, Any]) -> bool:
        """发送消息到指定智能体

        Args:
            agent_id: 目标智能体标识
            message: 消息数据

        Returns:
            bool: 是否成功发送
        """
        async with self._lock:
            if agent_id not in self.active_connections:
                return False

            try:
                websocket = self.active_connections[agent_id]
                await websocket.send_json(message)
                self.connection_metadata[agent_id]["last_activity"] = time.time()
                return True
            except Exception as e:
                print(f"[ConnectionManager] Failed to send to '{agent_id}': {e}")
                # 连接失败时注销
                self.unregister(agent_id)
                return False
    
    async def broadcast(self, message: Dict[str, Any], exclude: Optional[Set[str]] = None) -> int:
        """广播消息到所有连接

        Args:
            message: 消息数据
            exclude: 排除的智能体集合

        Returns:
            int: 成功发送的数量
        """
        exclude = exclude or set()
        sent_count = 0

        # 获取连接列表快照，避免并发修改
        async with self._lock:
            agent_ids = list(self.active_connections.keys())

        for agent_id in agent_ids:
            if agent_id not in exclude:
                if await self.send_to_agent(agent_id, message):
                    sent_count += 1

        return sent_count
    
    def get_online_agents(self) -> List[str]:
        """获取当前在线智能体列表

        Returns:
            List[str]: 在线智能体 ID 列表
        """
        # 返回快照，避免并发修改
        return list(self.active_connections.keys())

    def get_connection_count(self) -> int:
        """获取当前连接数

        Returns:
            int: 连接数
        """
        return len(self.active_connections)
