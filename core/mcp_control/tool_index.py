# core/mcp_control/tool_index.py
"""Tool Index 模块

维护所有 MCP Server 提供的工具能力快照，为 Router 提供稳定的工具视图。
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict


@dataclass
class ToolIndexEntry:
    """工具索引条目"""
    server_id: str
    tool_name: str
    description: str
    input_schema: Dict
    tags: List[str]
    blocking: bool = False
    cost_estimate: str = "medium"
    last_updated: str = ""
    
    def __post_init__(self):
        if not self.last_updated:
            self.last_updated = datetime.now().isoformat()


class ToolIndex:
    """Tool Index 管理器
    
    负责维护工具能力索引，提供查询接口。
    """
    
    def __init__(self):
        """初始化 Tool Index"""
        self.version = "1.0.0"
        self.tools: Dict[str, ToolIndexEntry] = {}  # tool_name -> ToolIndexEntry
        self.last_sync: Optional[str] = None
        print("[ToolIndex] Initialized")
    
    async def sync_from_servers(self, connections: Dict) -> None:
        """从所有连接的 MCP Server 同步工具列表
        
        Args:
            connections: server_id -> McpConnection 的字典
        """
        print(f"[ToolIndex] Starting sync from {len(connections)} server(s)...")
        synced_count = 0
        server_stats = []  # 记录每个Server的统计信息
        
        for server_id, connection in connections.items():
            server_tool_count = 0
            try:
                # 检查连接状态
                if not connection.session:
                    print(f"[ToolIndex] Syncing from {server_id}: SKIPPED (not connected)")
                    server_stats.append({"server_id": server_id, "status": "not_connected", "tools": 0})
                    continue
                
                print(f"[ToolIndex] Syncing from {server_id}...")
                
                # 调用 list_tools 获取工具列表
                tools_response = await connection.session.list_tools()
                
                # 解析工具元数据
                if hasattr(tools_response, 'tools'):
                    for tool in tools_response.tools:
                        tool_name = tool.name
                        
                        # 构建 ToolIndexEntry
                        entry = ToolIndexEntry(
                            server_id=server_id,
                            tool_name=tool_name,
                            description=tool.description or "",
                            input_schema=tool.inputSchema if hasattr(tool, 'inputSchema') else {},
                            tags=self._extract_tags(tool.description or ""),
                            blocking=False,  # 默认值，后续可通过配置覆盖
                            cost_estimate="medium"
                        )
                        
                        self.tools[tool_name] = entry
                        synced_count += 1
                        server_tool_count += 1
                    
                    print(f"[ToolIndex] Syncing from {server_id}: SUCCESS (retrieved {server_tool_count} tools)")
                    server_stats.append({"server_id": server_id, "status": "success", "tools": server_tool_count})
                else:
                    print(f"[ToolIndex] Syncing from {server_id}: WARNING (no 'tools' attribute in response)")
                    server_stats.append({"server_id": server_id, "status": "invalid_response", "tools": 0})
                
            except Exception as e:
                print(f"[ToolIndex] Syncing from {server_id}: FAILED ({type(e).__name__}: {e})")
                server_stats.append({"server_id": server_id, "status": "error", "tools": 0, "error": str(e)})
        
        self.last_sync = datetime.now().isoformat()
        
        # 输出汇总信息
        successful_servers = sum(1 for s in server_stats if s["status"] == "success")
        print(f"[ToolIndex] Sync complete: {successful_servers}/{len(connections)} servers successful, {synced_count} tools indexed")
        
        # 如果有Server但没有工具，输出警告
        if len(connections) > 0 and synced_count == 0:
            print(f"[ToolIndex] WARNING: No tools retrieved from any connected server")
            print(f"[ToolIndex] Server summary:")
            for stat in server_stats:
                status_msg = stat["status"]
                if "error" in stat:
                    status_msg += f" - {stat['error']}"
                print(f"  - {stat['server_id']}: {status_msg}")
    
    def _extract_tags(self, description: str) -> List[str]:
        """从描述中提取标签
        
        Args:
            description: 工具描述
            
        Returns:
            List[str]: 标签列表
        """
        tags = []
        desc_lower = description.lower()
        
        # 简单的关键词匹配
        if "email" in desc_lower or "邮件" in desc_lower:
            tags.append("notification")
        if "emergency" in desc_lower or "紧急" in desc_lower:
            tags.append("emergency")
        if "navigate" in desc_lower or "导航" in desc_lower:
            tags.append("navigation")
        if "camera" in desc_lower or "摄像头" in desc_lower or "拍照" in desc_lower:
            tags.append("perception")
        
        return tags
    
    async def save_to_file(self, path: str) -> None:
        """将索引保存到 JSON 文件
        
        Args:
            path: 文件路径
        """
        try:
            # 按 server_id 分组
            servers_data = {}
            for tool_name, entry in self.tools.items():
                server_id = entry.server_id
                if server_id not in servers_data:
                    servers_data[server_id] = {"server_id": server_id, "tools": []}
                
                servers_data[server_id]["tools"].append({
                    "tool_name": entry.tool_name,
                    "description": entry.description,
                    "input_schema": entry.input_schema,
                    "tags": entry.tags,
                    "blocking": entry.blocking,
                    "cost_estimate": entry.cost_estimate
                })
            
            data = {
                "version": self.version,
                "last_sync": self.last_sync,
                "servers": list(servers_data.values())
            }
            
            # 确保目录存在
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            print(f"[ToolIndex] Saved to {path}")
            
        except Exception as e:
            print(f"[ToolIndex] Error saving to file: {e}")
    
    async def load_from_file(self, path: str) -> None:
        """从 JSON 文件加载索引
        
        Args:
            path: 文件路径
        """
        try:
            if not os.path.exists(path):
                print(f"[ToolIndex] File not found: {path}")
                return
            
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            self.version = data.get("version", "1.0.0")
            self.last_sync = data.get("last_sync")
            self.tools.clear()
            
            for server in data.get("servers", []):
                server_id = server["server_id"]
                for tool_data in server.get("tools", []):
                    entry = ToolIndexEntry(
                        server_id=server_id,
                        tool_name=tool_data["tool_name"],
                        description=tool_data["description"],
                        input_schema=tool_data["input_schema"],
                        tags=tool_data.get("tags", []),
                        blocking=tool_data.get("blocking", False),
                        cost_estimate=tool_data.get("cost_estimate", "medium")
                    )
                    self.tools[entry.tool_name] = entry
            
            print(f"[ToolIndex] Loaded {len(self.tools)} tools from {path}")
            if self.last_sync:
                print(f"[ToolIndex] Cache last_sync: {self.last_sync}")
            
        except Exception as e:
            print(f"[ToolIndex] Error loading from file: {e}")
    
    def is_cache_valid(self, ttl_seconds: int) -> bool:
        """检查缓存是否有效
        
        Args:
            ttl_seconds: 缓存有效期（秒），0表示永久有效
            
        Returns:
            bool: 缓存是否有效
        """
        # 如果没有 last_sync，缓存无效
        if not self.last_sync:
            print("[ToolIndex] Cache invalid: no last_sync timestamp")
            return False
        
        # 检查工具数量：如果缓存为空，视为无效
        if len(self.tools) == 0:
            print("[ToolIndex] Cache invalid: no tools in cache")
            return False
        
        # TTL为0表示缓存永久有效（用于测试）
        if ttl_seconds == 0:
            print("[ToolIndex] Cache valid: TTL=0 (永久有效)")
            return True
        
        # TTL为负数，视为无效配置
        if ttl_seconds < 0:
            print(f"[ToolIndex] Invalid TTL value: {ttl_seconds}, using default 3600s")
            ttl_seconds = 3600
        
        try:
            # 解析 last_sync 时间戳（ISO格式）
            from dateutil import parser as date_parser
            last_sync_time = date_parser.isoparse(self.last_sync)
            
            # 计算缓存年龄
            current_time = datetime.now(last_sync_time.tzinfo) if last_sync_time.tzinfo else datetime.now()
            cache_age_seconds = (current_time - last_sync_time).total_seconds()
            
            is_valid = cache_age_seconds < ttl_seconds
            
            if is_valid:
                print(f"[ToolIndex] Cache is valid (age: {cache_age_seconds:.0f}s, TTL: {ttl_seconds}s, tools: {len(self.tools)})")
            else:
                print(f"[ToolIndex] Cache is expired (age: {cache_age_seconds:.0f}s, TTL: {ttl_seconds}s)")
            
            return is_valid
            
        except Exception as e:
            print(f"[ToolIndex] Error parsing last_sync timestamp: {e}")
            return False
    
    async def should_sync(self, cache_path: str, ttl_seconds: int, force_refresh: bool) -> bool:
        """判断是否需要同步工具列表
        
        Args:
            cache_path: 缓存文件路径
            ttl_seconds: 缓存有效期（秒）
            force_refresh: 是否强制刷新
            
        Returns:
            bool: 是否需要同步
        """
        # 强制刷新
        if force_refresh:
            print(f"[ToolIndex] Force refresh enabled, will sync")
            return True
        
        # 缓存文件不存在
        if not os.path.exists(cache_path):
            print(f"[ToolIndex] Cache file not found, will sync")
            return True
        
        # 检查缓存有效性
        if not self.is_cache_valid(ttl_seconds):
            print(f"[ToolIndex] Cache invalid or expired, will sync")
            return True
        
        print(f"[ToolIndex] Cache is valid, skip sync")
        return False
    
    def get_all_tools(self) -> List[ToolIndexEntry]:
        """获取所有工具列表
        
        Returns:
            List[ToolIndexEntry]: 工具列表
        """
        return list(self.tools.values())
    
    def get_tools_by_tag(self, tag: str) -> List[ToolIndexEntry]:
        """按标签筛选工具
        
        Args:
            tag: 标签名
            
        Returns:
            List[ToolIndexEntry]: 匹配的工具列表
        """
        return [entry for entry in self.tools.values() if tag in entry.tags]
    
    def get_server_by_tool(self, tool_name: str) -> Optional[str]:
        """根据工具名查找所属 Server ID
        
        Args:
            tool_name: 工具名称
            
        Returns:
            Optional[str]: Server ID，如果找不到返回 None
        """
        entry = self.tools.get(tool_name)
        return entry.server_id if entry else None
    
    def get_tool_entry(self, tool_name: str) -> Optional[ToolIndexEntry]:
        """获取工具条目
        
        Args:
            tool_name: 工具名称
            
        Returns:
            Optional[ToolIndexEntry]: 工具条目，如果找不到返回 None
        """
        return self.tools.get(tool_name)
