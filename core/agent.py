# core/agent.py
import asyncio
import time
from enum import Enum
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass
from abc import ABC, abstractmethod

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
    PeriodicTaskTrigger,
    PatrolExecutor,
    UserTaskExecutor,
    ActionChainExecutor
)
import config

class AgentState(Enum):
    """代理状态枚举"""
    IDLE = "idle"
    PATROLLING = "patrolling"
    RESPONDING = "responding"
    ALERT = "alert"

class RobotAgent:
    """巡检机器人代理主类（重构后的中枢管理器）
    
    通过 Actions 插槽机制实现能力的灵活扩展
    集成统一任务循环管理所有任务
    """
    
    def __init__(self, patrol_interval: float = None):
        """
        初始化机器人代理
        
        Args:
            patrol_interval: 巡逻间隔时间(秒)
        """
        self.state = AgentState.IDLE
        self.patrol_interval = patrol_interval or config.PATROL_INTERVAL
        
        # Actions 插槽
        self.actions: Dict[str, BaseAction] = {}
        self.action_metadata: Dict[str, ActionMetadata] = {}
        self.shared_context: Dict[str, Any] = {}  # Action 间共享的上下文
        
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
        
        # 周期性巡逻任务触发器（延迟初始化）
        self.patrol_trigger: Optional[PeriodicTaskTrigger] = None
        
        # 执行器（延迟初始化，等待Actions注册后）
        self._executors_initialized = False
        
        print("[Agent] Robot agent initialized in IDLE state")
        print("[Agent] Using unified task loop architecture")
    
    def start(self):
        """启动代理"""
        print("[Agent] Starting robot agent...")
        
        # 初始化执行器（如果还没有初始化）
        if not self._executors_initialized:
            self._initialize_executors()
        
        # 启动统一任务循环
        self.task_loop.start()
        
        # 启动巡逻触发器（如果启用）
        if self.patrol_trigger:
            self.patrol_trigger.start()
        
        self.set_state(AgentState.PATROLLING)
    
    def stop(self):
        """停止代理"""
        print("[Agent] Stopping robot agent...")
        
        # 停止巡逻触发器
        if self.patrol_trigger:
            self.patrol_trigger.stop()
        
        # 停止统一任务循环
        self.task_loop.stop()
        
        # 清理所有 Actions
        for action_name in list(self.actions.keys()):
            self.unregister_action(action_name)
        
        self.set_state(AgentState.IDLE)
    
    def register_action(self, name: str, action: BaseAction, config_dict: Dict[str, Any] = None) -> None:
        """注册并初始化一个 Action
        
        Args:
            name: Action 名称
            action: Action 实例
            config_dict: 配置参数
        """
        try:
            print(f"[Agent] Registering action: {name}")
            
            # 初始化 Action，自动传入agent引用
            if config_dict is None:
                config_dict = {}
            config_dict["agent"] = self  # 传入agent引用，供Action使用
            action.initialize(config_dict)
            
            # 存储 Action 和元信息
            self.actions[name] = action
            self.action_metadata[name] = action.metadata
            
            print(f"[Agent] Action '{name}' registered successfully")
            
        except Exception as e:
            print(f"[Agent] Failed to register action '{name}': {e}")
            raise
    
    async def unregister_action(self, name: str) -> None:
        """注销 Action 并清理资源
        
        Args:
            name: Action 名称
        """
        if name in self.actions:
            print(f"[Agent] Unregistering action: {name}")
            
            action = self.actions[name]
            # 支持异步和同步清理
            import inspect
            if inspect.iscoroutinefunction(action.cleanup):
                await action.cleanup()
            else:
                action.cleanup()
            
            del self.actions[name]
            del self.action_metadata[name]
            
            print(f"[Agent] Action '{name}' unregistered")
    
    async def execute_action(self, name: str, input_data: Any = None, config_dict: Dict[str, Any] = None) -> ActionResult:
        """执行指定的 Action
        
        Args:
            name: Action 名称
            input_data: 输入数据
            config_dict: 动态配置参数
            
        Returns:
            ActionResult: 执行结果
        """
        if name not in self.actions:
            print(f"[Agent] Action '{name}' not found")
            return ActionResult(
                success=False,
                error=Exception(f"Action '{name}' not registered")
            )
        
        try:
            # 构造 ActionContext
            context = ActionContext(
                agent_state=self.state,
                input_data=input_data,
                shared_data=self.shared_context,
                config=config_dict or {}
            )
            
            # 执行 Action
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
        """按顺序执行多个 Action
        
        Args:
            action_names: Action 名称列表
            input_data: 初始输入数据
            
        Returns:
            List[ActionResult]: 执行结果列表
        """
        results = []
        current_input = input_data
        
        for action_name in action_names:
            result = await self.execute_action(action_name, current_input)
            results.append(result)
            
            # 如果执行失败，停止后续 Action
            if not result.success:
                print(f"[Agent] Action chain stopped at '{action_name}' due to failure")
                break
            
            # 使用当前 Action 的输出作为下一个 Action 的输入
            current_input = result.output
        
        return results
    
    def set_state(self, state: AgentState):
        """设置代理状态"""
        print(f"[Agent] State changed from {self.state.value} to {state.value}")
        self.state = state
    
    def _initialize_executors(self):
        """初始化执行器并注册到调度器"""
        # todo: 巡逻相关部分要封装到PatrolAction，不要和主代码耦合
        print("[Agent] Initializing task executors...")
        
        # 初始化巡逻执行器
        patrol_executor = PatrolExecutor(agent=self, task_queue=self.task_queue)
        self.task_scheduler.register_executor(TaskType.PATROL, patrol_executor)
        
        # 初始化用户任务执行器
        user_task_executor = UserTaskExecutor(agent=self)
        self.task_scheduler.register_executor(TaskType.USER_COMMAND, user_task_executor)
        
        # 初始化Action链执行器
        action_chain_executor = ActionChainExecutor(agent=self)
        self.task_scheduler.register_executor(TaskType.ACTION_CHAIN, action_chain_executor)
        
        # 初始化巡逻任务触发器
        patrol_enabled = getattr(config, 'PATROL_ENABLED', True)
        patrol_priority = getattr(config, 'PATROL_PRIORITY', 3)
        patrol_emergency_threshold = getattr(config, 'PATROL_EMERGENCY_THRESHOLD', 0.8)
        
        self.patrol_trigger = PeriodicTaskTrigger(
            task_queue=self.task_queue,
            interval=self.patrol_interval,
            task_template={
                "task_type": TaskType.PATROL.value,
                "priority": patrol_priority,
                "timeout": 60.0,
                "execution_data": {
                    "action_name": "watch",
                    "emergency_threshold": patrol_emergency_threshold
                }
            },
            enabled=patrol_enabled
        )
        
        self._executors_initialized = True
        print("[Agent] Task executors initialized")
    
    async def submit_task(self, task: UnifiedTask) -> str:
        """提交任务到统一队列
        
        Args:
            task: 要提交的任务
            
        Returns:
            str: 任务ID
        """
        await self.task_queue.enqueue(task)
        print(f"[Agent] Task {task.task_id[:8]} submitted")
        return task.task_id
    
    async def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """查询任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            Optional[TaskStatus]: 任务状态，如果找不到返回None
        """
        task = await self.task_queue.get_by_id(task_id)
        return task.status if task else None
    
    async def get_task_detail(self, task_id: str) -> Optional[UnifiedTask]:
        """获取任务详情
        
        Args:
            task_id: 任务ID
            
        Returns:
            Optional[UnifiedTask]: 任务对象，如果找不到返回None
        """
        return await self.task_queue.get_by_id(task_id)
    
    async def cancel_task(self, task_id: str) -> bool:
        """取消任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否成功取消
        """
        # 尝试从队列中取消
        cancelled = await self.task_queue.cancel(task_id)
        
        # 如果任务正在运行，也需要取消调度器中的异步任务
        if not cancelled:
            cancelled = await self.task_scheduler.cancel_task(task_id)
        
        return cancelled


# 示例：使用统一任务循环的 main 函数
async def main():
    """主函数示例（使用统一任务循环）"""
    agent = RobotAgent(patrol_interval=30.0)
    
    # 注册 Actions
    agent.register_action("watch", WatchAction())
    agent.register_action("speak", SpeakAction())
    agent.register_action("alert", AlertAction())
    
    # 启动代理
    agent.start()
    
    # 运行一段时间后停止
    await asyncio.sleep(300)  # 运行5分钟
    agent.stop()

if __name__ == "__main__":
    asyncio.run(main())