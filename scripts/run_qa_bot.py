# scripts/run_qa_bot.py
"""智能问答机器人主程序"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.agent import RobotAgent
from core.action import ListenActionVAD, SpeakAction
from core.action.listen_action_vad import VADPresets
from core.task.models import UnifiedTask, TaskType
from core.action.base import ActionContext
from core.agent import AgentState


async def main():
    print("\n" + "="*60)
    print("🤖 智能问答机器人")
    print("="*60)
    print("\n初始化中...\n")
    
    # 1. 初始化 Agent
    agent = RobotAgent()
    
    # 2. 注册 Actions
    agent.register_action("speak", SpeakAction())
    
    # 3. 初始化 MCP
    from core.mcp_control import McpManager
    from core.client.openai_client import OpenAIClient
    from config import OPENAI_API_KEY, OPENAI_BASE_URL, MCP_CONFIG_PATH
    
    llm_client = OpenAIClient(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
    mcp_manager = McpManager()
    await mcp_manager.initialize(MCP_CONFIG_PATH, llm_client, agent)
    agent.initialize_mcp(mcp_manager)
    
    # 注册 MCP Executor
    from core.task.executors.mcp import McpExecutor
    mcp_executor = McpExecutor(
        router=mcp_manager.router,
        connections=mcp_manager.connections,
        task_queue=agent.task_queue
    )
    agent.task_scheduler.register_executor(TaskType.MCP_CALL, mcp_executor)
    
    # 4. 启动 Agent
    agent.start()
    
    # 5. 创建语音监听器
    listen_action = ListenActionVAD()
    listen_action.initialize(VADPresets.STANDARD)
    
    print("✅ 初始化完成！\n")
    print("💬 请说话，我会回答你的问题...")
    print("👋 说 '再见' 或 '退出' 结束对话\n")
    print("="*60 + "\n")
    
    running = True
    conversation_count = 0
    
    try:
        while running:
            # 监听语音
            context = ActionContext(
                agent_state=AgentState.IDLE,
                input_data=60.0  # 60秒超时
            )
            
            result = await listen_action.execute(context)
            
            # 无语音或识别失败
            if not result.success or not result.output.get("text"):
                continue
            
            user_text = result.output.get("text").strip()
            
            if not user_text:
                continue
            
            conversation_count += 1
            print(f"\n[对话 {conversation_count}]")
            print(f"🎤 用户: {user_text}")
            
            # 检查退出命令
            exit_keywords = ["再见", "拜拜", "退出", "结束", "停止"]
            if any(kw in user_text.lower() for kw in exit_keywords):
                print("👋 收到退出指令\n")
                await agent.execute_action("speak", "再见！很高兴为你服务！")
                running = False
                break
            
            # 创建对话任务
            task = UnifiedTask(
                task_type=TaskType.CONVERSATION,
                priority=8,
                execution_data={
                    "user_text": user_text
                }
            )
            
            # 提交任务
            task_id = await agent.submit_task(task)
            print(f"📝 任务已提交 (ID: {task_id[:8]})")
            
            # 等待任务完成（简单轮询）
            max_wait = 120
            waited = 0
            
            while waited < max_wait:
                from core.task.models import TaskStatus
                status = await agent.get_task_status(task_id)
                
                if status == TaskStatus.COMPLETED:
                    task_detail = await agent.get_task_detail(task_id)
                    if task_detail and task_detail.result:
                        bot_response = task_detail.result.get("bot_response", "")
                        used_mcp = task_detail.result.get("used_mcp", False)
                        print(f"🤖 助手: {bot_response}")
                        if used_mcp:
                            print("   (使用了外部工具)")
                    break
                
                elif status == TaskStatus.FAILED:
                    print("❌ 任务执行失败")
                    break
                
                await asyncio.sleep(0.5)
                waited += 0.5
            
            print()  # 空行分隔
    
    except KeyboardInterrupt:
        print("\n\n⚠️  收到中断信号 (Ctrl+C)")
    
    finally:
        print("\n正在关闭...")
        await agent.stop()
        listen_action.cleanup()
        print("👋 再见！")
        print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())