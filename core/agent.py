# core/agent.py
import asyncio
from enum import Enum
from typing import Dict, Any, Optional, List

# 导入 Action 相关类
from core.action import (
    BaseAction,
    ActionContext,
    ActionResult,
    ActionMetadata,
    SpeakAction,
)

# 导入统一任务管理模块
from core.task import (
    UnifiedTask,
    TaskType,
    TaskStatus,
    TaskQueue,
    TaskScheduler,
    UnifiedTaskLoop,
    UserTaskExecutor,
    ActionChainExecutor,
    ConversationExecutor
)
import config


class AgentState(Enum):
    """代理状态枚举"""
    IDLE = "idle"
    PATROLLING = "patrolling"
    RESPONDING = "responding"
    ALERT = "alert"


class RobotAgent:
    """智能问答机器人代理主类
    
    通过 Actions 插槽机制实现能力的灵活扩展
    集成统一任务循环管理所有任务
    """
    
    def __init__(self):
        """初始化机器人代理"""
        self.state = AgentState.IDLE
        self.mcp_manager = None  # MCP Manager（延迟注入）
        
        # Actions 插槽
        self.actions: Dict[str, BaseAction] = {}
        self.action_metadata: Dict[str, ActionMetadata] = {}
        self.shared_context: Dict[str, Any] = {}
        
        # 初始化统一任务管理系统
        self.task_queue = TaskQueue()
        self.task_scheduler = TaskScheduler(
            max_concurrent_tasks=getattr(config, 'MAX_CONCURRENT_TASKS', 5)
        )
        self.task_loop = UnifiedTaskLoop(
            task_queue=self.task_queue,
            scheduler=self.task_scheduler,
            loop_interval=getattr(config, 'TASK_LOOP_INTERVAL', 1.0)
        )
        
        # 执行器（延迟初始化）
        self._executors_initialized = False
        
        print("[Agent] Robot agent initialized in IDLE state")
        print("[Agent] Using unified task loop architecture")
    
    def initialize_mcp(self, mcp_manager):
        """初始化 MCP Manager（外部注入）"""
        self.mcp_manager = mcp_manager
        print("[Agent] MCP Manager initialized")
    
    def start(self):
        """启动代理"""
        print("[Agent] Starting robot agent...")
        
        if not self._executors_initialized:
            self._initialize_executors()
        
        self.task_loop.start()
        self.set_state(AgentState.RESPONDING)
    
    async def stop(self):  # ✅ 改为 async
        """停止代理"""
        print("[Agent] Stopping robot agent...")
        
        self.task_loop.stop()
        
        # ✅ 正确 await 异步清理
        for action_name in list(self.actions.keys()):
            await self.unregister_action(action_name)
        
        self.set_state(AgentState.IDLE)
    
    def register_action(self, name: str, action: BaseAction, config_dict: Dict[str, Any] = None) -> None:
        """注册并初始化一个 Action"""
        try:
            print(f"[Agent] Registering action: {name}")
            
            if config_dict is None:
                config_dict = {}
            config_dict["agent"] = self
            action.initialize(config_dict)
            
            self.actions[name] = action
            self.action_metadata[name] = action.metadata
            
            print(f"[Agent] Action '{name}' registered successfully")
            
        except Exception as e:
            print(f"[Agent] Failed to register action '{name}': {e}")
            raise
    
    async def unregister_action(self, name: str) -> None:
        """注销 Action 并清理资源"""
        if name in self.actions:
            print(f"[Agent] Unregistering action: {name}")
            
            action = self.actions[name]
            import inspect
            if inspect.iscoroutinefunction(action.cleanup):
                await action.cleanup()
            else:
                action.cleanup()
            
            del self.actions[name]
            del self.action_metadata[name]
            
            print(f"[Agent] Action '{name}' unregistered")
    
    async def execute_action(self, name: str, input_data: Any = None, config_dict: Dict[str, Any] = None) -> ActionResult:
        """执行指定的 Action"""
        if name not in self.actions:
            print(f"[Agent] Action '{name}' not found")
            return ActionResult(
                success=False,
                error=Exception(f"Action '{name}' not registered")
            )
        
        try:
            context = ActionContext(
                agent_state=self.state,
                input_data=input_data,
                shared_data=self.shared_context,
                config=config_dict or {}
            )
            
            action = self.actions[name]
            result = await action.execute(context)
            
            return result
            
        except Exception as e:
            print(f"[Agent] Error executing action '{name}': {e}")
            return ActionResult(
                success=False,
                error=e
            )
    
    async def execute_action_chain(self, action_names: List[str], input_data: Any = None) -> List[ActionResult]:
        """按顺序执行多个 Action"""
        results = []
        current_input = input_data
        
        for action_name in action_names:
            result = await self.execute_action(action_name, current_input)
            results.append(result)
            
            if not result.success:
                print(f"[Agent] Action chain stopped at '{action_name}' due to failure")
                break
            
            current_input = result.output
        
        return results
    
    def set_state(self, state: AgentState):
        """设置代理状态"""
        print(f"[Agent] State changed from {self.state.value} to {state.value}")
        self.state = state
    
    def _initialize_executors(self):
        """初始化执行器并注册到调度器"""
        print("[Agent] Initializing task executors...")
        
        # 用户任务执行器
        user_task_executor = UserTaskExecutor(agent=self)
        self.task_scheduler.register_executor(TaskType.USER_COMMAND, user_task_executor)
        
        # Action链执行器
        action_chain_executor = ActionChainExecutor(agent=self)
        self.task_scheduler.register_executor(TaskType.ACTION_CHAIN, action_chain_executor)
        
        # 对话执行器
        from core.client.openai_client import OpenAIClient
        from config import OPENAI_API_KEY, OPENAI_BASE_URL
        
        llm_client = OpenAIClient(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
        
        conversation_executor = ConversationExecutor(
            agent=self,
            llm_client=llm_client
        )
        self.task_scheduler.register_executor(TaskType.CONVERSATION, conversation_executor)
        
        self._executors_initialized = True
        print("[Agent] Task executors initialized")
    
    async def submit_task(self, task: UnifiedTask) -> str:
        """提交任务到统一队列"""
        await self.task_queue.enqueue(task)
        print(f"[Agent] Task {task.task_id[:8]} submitted")
        return task.task_id
    
    async def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """查询任务状态"""
        task = await self.task_queue.get_by_id(task_id)
        return task.status if task else None
    
    async def get_task_detail(self, task_id: str) -> Optional[UnifiedTask]:
        """获取任务详情"""
        return await self.task_queue.get_by_id(task_id)
    
    async def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        cancelled = await self.task_queue.cancel(task_id)
        
        if not cancelled:
            cancelled = await self.task_scheduler.cancel_task(task_id)
        
        return cancelled


# 示例主函数
async def main():
    """主函数示例"""
    agent = RobotAgent()
    
    agent.register_action("speak", SpeakAction())
    
    agent.start()
    
    await asyncio.sleep(300)
    await agent.stop()


if __name__ == "__main__":
    asyncio.run(main())