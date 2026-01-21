# core/server/communication_server.py
"""通信服务器

提供 HTTP/WebSocket 服务，负责网络层功能
"""

import asyncio
import time
import uuid
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect, Query, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from core.server.connection_manager import ConnectionManager
from core.server.message_router import MessageRouter, TaskRequest, UserInputRequest


class TaskResponse(BaseModel):
    """任务响应数据模型"""
    task_id: str = Field(..., description="任务唯一标识符")
    status: str = Field(..., description="任务状态")
    created_at: float = Field(..., description="创建时间戳")
    message: str = Field(..., description="状态说明")


class TaskStatusResponse(BaseModel):
    """任务状态查询响应"""
    task_id: str
    status: str
    created_at: float
    updated_at: float
    message: str
    result: Optional[dict] = None


class CommunicationServer:
    """通信服务器
    
    管理 HTTP/WebSocket 服务，协调消息路由和连接管理
    """
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8080, api_key: str = "default-key", 
                 agent_id: str = "robot-agent", enable_cors: bool = True, max_connections: int = 100):
        """初始化通信服务器
        
        Args:
            host: 监听地址
            port: 监听端口
            api_key: API 认证密钥
            agent_id: 智能体标识
            enable_cors: 是否启用 CORS
            max_connections: 最大 WebSocket 连接数
        """
        self.host = host
        self.port = port
        self.api_key = api_key
        self.agent_id = agent_id
        self.enable_cors = enable_cors
        
        # 创建组件
        self.connection_manager = ConnectionManager(max_connections=max_connections)
        self.message_router = MessageRouter()
        self.task_dispatcher = None  # 将由外部注入
        
        # FastAPI 应用
        self.app: Optional[FastAPI] = None
        self.server_task: Optional[asyncio.Task] = None
        
        # 创建 FastAPI 应用
        self._create_app()
        
        print(f"[CommunicationServer] Initialized (agent_id: {agent_id})")
    
    def set_task_dispatcher(self, task_dispatcher):
        """设置任务调度器引用（用于双向注入）
        
        Args:
            task_dispatcher: TaskDispatcher 实例
        """
        self.task_dispatcher = task_dispatcher
        print("[CommunicationServer] TaskDispatcher reference set")
    
    def _create_app(self) -> None:
        """创建 FastAPI 应用"""
        self.app = FastAPI(
            title="Robot Agent Communication API",
            description="任务接收与智能体间通信接口",
            version="1.0.0"
        )
        
        # 配置 CORS
        if self.enable_cors:
            self.app.add_middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )
        
        # 配置路由
        self._setup_routes()
    
    def _verify_api_key(self, x_api_key: Optional[str] = Header(None), api_key: Optional[str] = Query(None)) -> bool:
        """验证 API Key
        
        Args:
            x_api_key: Header 中的 API Key
            api_key: 查询参数中的 API Key
            
        Returns:
            bool: 验证是否通过
            
        Raises:
            HTTPException: 验证失败时抛出 401 错误
        """
        provided_key = x_api_key or api_key
        if provided_key != self.api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return True
    
    def _setup_routes(self) -> None:
        """设置 API 路由"""
        
        @self.app.get("/health")
        async def health_check():
            """健康检查端点"""
            return {
                "status": "healthy",
                "agent_id": self.agent_id,
                "timestamp": time.time(),
                "connections": self.connection_manager.get_connection_count()
            }
        
        @self.app.post("/api/tasks", response_model=TaskResponse)
        async def create_task(
            task_data: dict,
            authorized: bool = Depends(self._verify_api_key)
        ):
            """创建新任务"""
            # 验证任务请求
            task_request = self.message_router.validate_task_request(task_data)
            if not task_request:
                raise HTTPException(status_code=400, detail="Invalid task request format")
            
            # 分发任务
            if not self.task_dispatcher:
                raise HTTPException(status_code=500, detail="TaskDispatcher not available")
            
            task_id = await self.task_dispatcher.dispatch_task(task_request)
            
            return TaskResponse(
                task_id=task_id,
                status="pending",
                created_at=time.time(),
                message="Task created successfully"
            )
        
        @self.app.get("/api/tasks/{task_id}", response_model=TaskStatusResponse)
        async def get_task_status(
            task_id: str,
            authorized: bool = Depends(self._verify_api_key)
        ):
            """查询任务状态"""
            if not self.task_dispatcher:
                raise HTTPException(status_code=500, detail="TaskDispatcher not available")
            
            task_info = self.task_dispatcher.get_task_status(task_id)
            if not task_info:
                raise HTTPException(status_code=404, detail="Task not found")
            
            return TaskStatusResponse(
                task_id=task_info.task_id,
                status=task_info.status,
                created_at=task_info.created_at,
                updated_at=task_info.updated_at,
                message=task_info.message,
                result=task_info.result
            )
        
        @self.app.get("/api/tasks")
        async def list_tasks(
            authorized: bool = Depends(self._verify_api_key),
            limit: int = Query(default=50, ge=1, le=200)
        ):
            """获取任务列表"""
            if not self.task_dispatcher:
                raise HTTPException(status_code=500, detail="TaskDispatcher not available")
            
            tasks = self.task_dispatcher.list_tasks(limit)
            return [
                {
                    "task_id": t.task_id,
                    "status": t.status,
                    "created_at": t.created_at,
                    "updated_at": t.updated_at,
                    "message": t.message,
                    "result": t.result
                }
                for t in tasks
            ]
        
        @self.app.post("/api/input")
        async def receive_user_input(
            input_data: dict,
            authorized: bool = Depends(self._verify_api_key)
        ):
            """接收用户输入"""
            # 验证用户输入
            user_input = self.message_router.validate_user_input(input_data)
            if not user_input:
                raise HTTPException(status_code=400, detail="Invalid user input format")
            
            # 转换为任务请求并分发
            if not self.task_dispatcher:
                raise HTTPException(status_code=500, detail="TaskDispatcher not available")
            
            task_request = self.message_router.convert_user_input_to_task(user_input)
            task_id = await self.task_dispatcher.dispatch_task(task_request)
            
            return {
                "task_id": task_id,
                "status": "pending",
                "message": "User input received and queued"
            }
        
        @self.app.websocket("/ws/agent")
        async def websocket_endpoint(
            websocket: WebSocket,
            api_key: Optional[str] = Query(None),
            agent_id: Optional[str] = Query(None)
        ):
            """WebSocket 智能体通信端点"""
            await self._handle_websocket(websocket, api_key, agent_id)
    
    async def _handle_websocket(self, websocket: WebSocket, api_key: Optional[str], agent_id: Optional[str]) -> None:
        """处理 WebSocket 连接
        
        Args:
            websocket: WebSocket 连接
            api_key: API 密钥
            agent_id: 智能体标识
        """
        # 验证 API Key
        if api_key != self.api_key:
            await websocket.close(code=4001, reason="Invalid API key")
            return
        
        # 使用提供的 agent_id 或生成默认 ID
        if not agent_id:
            agent_id = f"agent-{uuid.uuid4().hex[:8]}"
        
        # 接受连接
        await websocket.accept()
        
        # 注册连接
        if not await self.connection_manager.register(agent_id, websocket):
            await websocket.close(code=4003, reason="Maximum connections reached")
            return
        
        try:
            # 发送连接确认消息
            await websocket.send_json({
                "message_type": "notification",
                "from_agent": self.agent_id,
                "to_agent": agent_id,
                "message_id": str(uuid.uuid4()),
                "timestamp": time.time(),
                "payload": {
                    "event": "connected",
                    "message": f"Connected to {self.agent_id}",
                    "online_agents": self.connection_manager.get_online_agents()
                }
            })
            
            # 接收和处理消息
            while True:
                data = await websocket.receive_json()
                await self._route_websocket_message(agent_id, data)
                
        except WebSocketDisconnect:
            print(f"[CommunicationServer] WebSocket disconnected: {agent_id}")
        except Exception as e:
            print(f"[CommunicationServer] WebSocket error for {agent_id}: {e}")
        finally:
            # 注销连接
            self.connection_manager.unregister(agent_id)
    
    async def _route_websocket_message(self, from_agent_id: str, message_data: dict) -> None:
        """路由 WebSocket 消息
        
        Args:
            from_agent_id: 发送方智能体 ID
            message_data: 消息数据
        """
        try:
            # 验证消息格式
            message = self.message_router.validate_websocket_message(message_data)
            if not message:
                print(f"[CommunicationServer] Invalid WebSocket message from {from_agent_id}")
                return
            
            # 更新发送方 ID（防止伪造）
            message.from_agent = from_agent_id
            
            # 路由消息
            if message.to_agent:
                # 点对点消息
                success = await self.connection_manager.send_to_agent(message.to_agent, message.dict())
                if not success:
                    print(f"[CommunicationServer] Failed to route message to {message.to_agent}")
            else:
                # 广播消息
                await self.connection_manager.broadcast(message.dict(), exclude={from_agent_id})
            
        except Exception as e:
            print(f"[CommunicationServer] Failed to route message: {e}")
    
    async def broadcast_message(self, message: dict) -> None:
        """广播消息到所有连接
        
        Args:
            message: 消息数据
        """
        sent_count = await self.connection_manager.broadcast(message)
        if sent_count > 0:
            print(f"[CommunicationServer] Message broadcast to {sent_count} agents")
    
    async def start(self) -> None:
        """启动通信服务器"""
        print(f"[CommunicationServer] Starting server at {self.host}:{self.port}")
        
        config = uvicorn.Config(
            app=self.app,
            host=self.host,
            port=self.port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        
        # 在后台运行服务器
        self.server_task = asyncio.create_task(server.serve())
        
        print(f"[CommunicationServer] Server started")
        print(f"[CommunicationServer] HTTP endpoint: http://{self.host}:{self.port}")
        print(f"[CommunicationServer] WebSocket endpoint: ws://{self.host}:{self.port}/ws/agent")
    
    def stop(self) -> None:
        """停止通信服务器"""
        print("[CommunicationServer] Stopping server...")
        
        # 停止服务器
        if self.server_task and not self.server_task.done():
            self.server_task.cancel()
            print("[CommunicationServer] Server task cancelled")
        
        # 关闭所有 WebSocket 连接
        for agent_id in list(self.connection_manager.active_connections.keys()):
            self.connection_manager.unregister(agent_id)
        
        print("[CommunicationServer] Server stopped")
