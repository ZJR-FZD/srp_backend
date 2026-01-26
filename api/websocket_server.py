# api/websocket_server.py
"""WebSocket 服务器 - 数字人前端接口"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
from typing import Dict, Set
from pathlib import Path
import sys

# 添加项目根目录
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.agent import RobotAgent
from core.action import SpeakAction
from core.task.models import UnifiedTask, TaskType
from core.task.executors.conversation_with_wake import ConversationExecutorWithWake
from core.client.openai_client import OpenAIClient
from config import OPENAI_API_KEY, OPENAI_BASE_URL, MCP_CONFIG_PATH

# ==================== FastAPI 应用 ====================
app = FastAPI(title="数字人对话 WebSocket API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== 全局变量 ====================
agent: RobotAgent = None
conversation_executor: ConversationExecutorWithWake = None
active_connections: Set[WebSocket] = set()

# ==================== 状态回调 ====================
def state_callback(state: str, data: Dict):
    """状态变化时推送给所有前端"""
    message = {
        "type": "state_change",
        "state": state,
        "data": data,
        "timestamp": asyncio.get_event_loop().time()
    }
    
    asyncio.create_task(broadcast(message))

async def broadcast(message: Dict):
    """广播消息给所有连接"""
    if not active_connections:
        return
    
    disconnected = set()
    
    for ws in active_connections:
        try:
            await ws.send_json(message)
        except:
            disconnected.add(ws)
    
    # 移除断开的连接
    for ws in disconnected:
        active_connections.discard(ws)

# ==================== 初始化 ====================
@app.on_event("startup")
async def startup():
    """启动时初始化"""
    global agent, conversation_executor
    
    print("\n🚀 初始化数字人对话系统...")
    
    # 1. 初始化 Agent
    agent = RobotAgent()
    agent.register_action("speak", SpeakAction())
    
    # 2. 初始化 MCP
    from core.mcp_control import McpManager
    llm_client = OpenAIClient(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
    mcp_manager = McpManager()
    await mcp_manager.initialize(MCP_CONFIG_PATH, llm_client, agent)
    agent.initialize_mcp(mcp_manager)
    
    # 3. 注册 MCP Executor
    from core.task.executors.mcp import McpExecutor
    mcp_executor = McpExecutor(
        router=mcp_manager.router,
        connections=mcp_manager.connections,
        task_queue=agent.task_queue
    )
    agent.task_scheduler.register_executor(TaskType.MCP_CALL, mcp_executor)
    
    # 4. 创建 ConversationExecutor（带唤醒词）
    conversation_executor = ConversationExecutorWithWake(
        agent=agent,
        llm_client=llm_client,
        wake_words=["你好小狐狸", "小狐狸", "hey fox"],
        idle_timeout=30.0,
        max_idle_rounds=2,
        state_callback=state_callback  # 👈 传入回调
    )
    
    # 5. 注册 Executor
    agent.task_scheduler.register_executor(
        TaskType.CONVERSATION,
        conversation_executor
    )
    
    # 6. 启动 Agent
    agent.start()
    
    # 7. 创建永久监听任务
    task = UnifiedTask(
        task_type=TaskType.CONVERSATION,
        priority=10,
        execution_data={"mode": "loop"}  # 永久循环模式
    )
    
    await agent.submit_task(task)
    
    print("✅ 系统初始化完成，等待前端连接...\n")

@app.on_event("shutdown")
async def shutdown():
    """关闭时清理"""
    global agent, conversation_executor
    
    print("\n🛑 关闭系统...")
    
    if conversation_executor:
        conversation_executor.stop()
        conversation_executor.cleanup()
    
    if agent:
        await agent.stop()
    
    print("✅ 系统已关闭")

# ==================== WebSocket 端点 ====================
@app.websocket("/ws/conversation")
async def websocket_conversation(websocket: WebSocket):
    """WebSocket 连接端点"""
    await websocket.accept()
    active_connections.add(websocket)
    
    print(f"✅ 前端已连接，当前连接数: {len(active_connections)}")
    
    # 发送欢迎消息
    await websocket.send_json({
        "type": "connected",
        "message": "已连接到数字人对话系统",
        "wake_words": conversation_executor.wake_words,
        "current_state": conversation_executor.current_state
    })
    
    try:
        while True:
            # 接收前端消息（可选：前端可以主动控制）
            data = await websocket.receive_json()
            message_type = data.get("type")
            
            if message_type == "ping":
                await websocket.send_json({"type": "pong"})
            
            elif message_type == "get_state":
                await websocket.send_json({
                    "type": "current_state",
                    "state": conversation_executor.current_state,
                    "total_conversations": conversation_executor.total_conversations
                })
    
    except WebSocketDisconnect:
        print(f"❌ 前端断开连接，剩余连接数: {len(active_connections) - 1}")
    
    finally:
        active_connections.discard(websocket)

# ==================== HTTP 端点（可选）====================
@app.get("/")
async def root():
    """根路径"""
    return {
        "name": "数字人对话 API",
        "version": "1.0.0",
        "endpoints": {
            "websocket": "/ws/conversation",
            "status": "/status"
        }
    }

@app.get("/status")
async def get_status():
    """获取系统状态"""
    return {
        "agent_running": agent is not None,
        "conversation_state": conversation_executor.current_state if conversation_executor else None,
        "total_conversations": conversation_executor.total_conversations if conversation_executor else 0,
        "active_connections": len(active_connections)
    }

# ==================== 启动服务器 ====================
if __name__ == "__main__":
    import uvicorn
    
    print("\n" + "="*60)
    print("🦊 数字人对话 WebSocket 服务器")
    print("="*60)
    print("\n启动中...\n")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )