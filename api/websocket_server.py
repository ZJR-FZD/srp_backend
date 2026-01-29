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
from core.task.models import UnifiedTask, TaskType, TaskStatus
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
    print(f"\n🔔 [state_callback] 状态变更: {state}")
    print(f"   数据: {data}")
    print(f"   当前连接数: {len(active_connections)}")
    
    # 🔧 修复：message 类型单独处理
    if state == "message":
        # 消息事件：直接使用 message 作为类型
        message = {
            "type": "message",
            "data": data,
            "timestamp": asyncio.get_event_loop().time()
        }
    elif state in ["listening_started", "listening_stopped", "messages_cleared"]:
        # 控制事件：直接使用状态名作为类型
        message = {
            "type": state,
            "message": data.get("message", ""),
            "timestamp": asyncio.get_event_loop().time()
        }
    else:
        # 其他状态变化：包装为 state_change
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
        state_callback=state_callback
    )
    
    # ⚠️ 关键：先启动 Agent（会自动注册旧的 ConversationExecutor）
    agent.start()
    
    # 👇 新增：重新注册，覆盖旧的 ConversationExecutor
    print("[websocket_server] 覆盖旧的 ConversationExecutor，注册 ConversationExecutorWithWake")
    agent.task_scheduler.register_executor(
        TaskType.CONVERSATION,
        conversation_executor
    )
    
    # 7. 创建永久监听任务（设置超长超时）
    task = UnifiedTask(
        task_type=TaskType.CONVERSATION,
        priority=10,
        timeout=86400.0,  # 👈 24小时超时（实际上会永久运行直到手动停止）
        execution_data={"mode": "loop"}  # 👈 注意：不要传 user_text
    )
    
    task_id = await agent.submit_task(task)
    print(f"✅ 永久监听任务已提交: {task_id}")
    
    # 等待一下，确认任务开始执行
    await asyncio.sleep(1)
    
    task_status = await agent.get_task_status(task_id)
    print(f"📊 任务状态: {task_status}")
    
    # 👇 修复：正确获取任务失败原因（移除不存在的 message 属性）
    if task_status == TaskStatus.FAILED:
        task_detail = await agent.get_task_detail(task_id)
        # 修复点1：从 task_detail 的 history 或 result 中获取失败原因
        fail_reason = "Unknown"
        if task_detail:
            # 方式1：从执行历史中找状态转换的失败原因
            for record in reversed(task_detail.history):
                if record.get("event") == "status_transition" and record.get("new_status") == "failed":
                    fail_reason = record.get("reason", "No reason provided")
                    break
            # 方式2：如果有result，也可以补充显示
            if task_detail.result:
                fail_reason = f"{fail_reason} | Result: {str(task_detail.result)[:200]}"
        
        print(f"❌ 任务失败原因: {fail_reason}")
        print(f"   执行器类型: {type(conversation_executor).__name__}")
        # 可选：打印完整的任务历史，方便调试
        print(f"   任务完整历史: {json.dumps(task_detail.history, ensure_ascii=False, indent=2)}")
    else:
        print(f"✅ 任务运行正常，执行器: {type(conversation_executor).__name__}")
    
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

# ==================== HTTP 端点 ====================
@app.get("/")
async def root():
    """根路径"""
    return {
        "name": "数字人对话 API",
        "version": "2.0.0",
        "endpoints": {
            "websocket": "/ws/conversation",
            "status": "/status",
            "messages": "/messages",
            "control": {
                "start": "/control/start",
                "stop": "/control/stop",
                "clear_messages": "/messages/clear"
            }
        }
    }

@app.get("/status")
async def get_status():
    """获取系统状态"""
    return {
        "agent_running": agent is not None,
        "conversation_state": conversation_executor.current_state if conversation_executor else None,
        "listening_active": conversation_executor.listening_active if conversation_executor else False,
        "total_conversations": conversation_executor.total_conversations if conversation_executor else 0,
        "active_connections": len(active_connections),
        "total_messages": len(conversation_executor.messages) if conversation_executor else 0
    }

@app.get("/messages")
async def get_messages(limit: int = 20):
    """获取消息列表（用于字幕显示）"""
    if not conversation_executor:
        return {"messages": []}
    
    messages = conversation_executor.get_messages(limit=limit)
    return {
        "messages": messages,
        "total": len(conversation_executor.messages)
    }

@app.post("/control/start")
async def start_listening():
    """启动监听"""
    if not conversation_executor:
        return {"success": False, "message": "系统未初始化"}
    
    conversation_executor.start_listening()
    
    # 广播给所有前端
    await broadcast({
        "type": "listening_started",
        "message": "监听已启动",
        "timestamp": asyncio.get_event_loop().time()
    })
    
    return {
        "success": True,
        "message": "监听已启动"
    }

@app.post("/control/stop")
async def stop_listening():
    """停止监听"""
    if not conversation_executor:
        return {"success": False, "message": "系统未初始化"}
    
    conversation_executor.stop_listening()
    
    # 广播给所有前端
    await broadcast({
        "type": "listening_stopped",
        "message": "监听已停止",
        "timestamp": asyncio.get_event_loop().time()
    })
    
    return {
        "success": True,
        "message": "监听已停止"
    }

@app.post("/messages/clear")
async def clear_messages():
    """清空消息列表"""
    if not conversation_executor:
        return {"success": False, "message": "系统未初始化"}
    
    conversation_executor.clear_messages()
    
    # 广播给所有前端
    await broadcast({
        "type": "messages_cleared",
        "message": "消息已清空",
        "timestamp": asyncio.get_event_loop().time()
    })
    
    return {
        "success": True,
        "message": "消息已清空"
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