import asyncio
import os
from core.agent import RobotAgent
from core.action import SpeakAction, ListenAction, ConversationAction
from core.server import CommunicationServer, TaskDispatcher
from core.mcp_control.manager import McpManager
from core.client.openai_client import OpenAIClient
from core.task.executors.mcp import McpExecutor
from core.task.models import TaskType
import config

async def main():
    """主程序入口（使用新的通信架构）"""
    print("[Main] Initializing Robot Agent...")
    
    # 创建 Agent
    agent = RobotAgent()
    
    # 注册 Actions
    print("[Main] Registering actions...")
    agent.register_action("speak", SpeakAction())
    agent.register_action("listen", ListenAction())
    agent.register_action("conversation", ConversationAction())
    
    # ========== 初始化 MCP 子系统 ==========
    # 检查 MCP 配置文件是否存在
    mcp_config_path = config.MCP_CONFIG_PATH
    if os.path.exists(mcp_config_path):
        try:
            print("[Main] Initializing MCP Manager...")
            
            # 初始化 LLM 客户端
            llm_client = OpenAIClient(
                api_key=config.OPENAI_API_KEY,
                base_url=config.OPENAI_BASE_URL
            )
            
            # 初始化 McpManager 单例
            mcp_manager = McpManager()
            await mcp_manager.initialize(
                config_path=mcp_config_path,
                llm_client=llm_client,
                agent=agent
            )
            
            print("[Main] MCP Manager initialized successfully")
            print(f"[Main] Connected MCP servers: {list(mcp_manager.connections.keys())}")
            print(f"[Main] Total tools indexed: {len(mcp_manager.tool_index.tools)}")
            
            # 创建并注册 McpExecutor
            print("[Main] Registering McpExecutor...")
            mcp_executor = McpExecutor(
                router=mcp_manager.router,
                connections=mcp_manager.connections,
                task_queue=agent.task_queue
            )
            agent.task_scheduler.register_executor(TaskType.MCP_CALL, mcp_executor)
            print("[Main] McpExecutor registered for MCP_CALL tasks")
            
        except Exception as e:
            print(f"[Main] WARNING: Failed to initialize MCP subsystem: {e}")
            print("[Main] System will continue without MCP support")
    else:
        print(f"[Main] WARNING: MCP config file not found: {mcp_config_path}")
        print("[Main] System will continue without MCP support")
    
    # 创建 TaskDispatcher
    print("[Main] Creating TaskDispatcher...")
    task_dispatcher = TaskDispatcher(agent=agent)
    
    # 注册 DispatcherTaskExecutor
    print("[Main] Registering DispatcherTaskExecutor...")
    from core.task.executors.dispatcher_task import DispatcherTaskExecutor
    dispatcher_executor = DispatcherTaskExecutor(task_dispatcher=task_dispatcher)
    agent.task_scheduler.register_executor(TaskType.DISPATCHER, dispatcher_executor)
    
    # 创建 CommunicationServer
    print("[Main] Creating CommunicationServer...")
    comm_server = CommunicationServer(
        host=config.COMMUNICATION_HOST,
        port=config.COMMUNICATION_PORT,
        api_key=config.COMMUNICATION_API_KEY,
        agent_id=config.AGENT_ID,
        enable_cors=config.ENABLE_CORS,
        max_connections=config.MAX_WEBSOCKET_CONNECTIONS
    )
    
    # 建立双向引用
    comm_server.set_task_dispatcher(task_dispatcher)
    task_dispatcher.set_communication_server(comm_server)
    
    print("[Main] Actions registered:")
    for name, metadata in agent.action_metadata.items():
        print(f"  - {name}: {metadata.description}")
    
    # 启动 CommunicationServer
    print("[Main] Starting CommunicationServer...")
    await comm_server.start()
    
    # 启动 Agent
    print("[Main] Starting agent...")
    agent.start()
    
    try:
        # 保持运行
        print("[Main] Agent is running. Press Ctrl+C to stop.")
        while True:
            await asyncio.sleep(60)
    except KeyboardInterrupt:
        print("\n[Main] Shutting down...")
    finally:
        comm_server.stop()
        agent.stop()
        
        # 清理 MCP 资源
        try:
            mcp_manager = McpManager()
            if mcp_manager._initialized:
                print("[Main] Closing MCP connections...")
                await mcp_manager.close()
        except Exception as e:
            print(f"[Main] Error closing MCP connections: {e}")
        
        print("[Main] Agent stopped.")

if __name__ == "__main__":
    asyncio.run(main())
