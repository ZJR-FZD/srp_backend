# core/task/executors/patrol.py
"""巡逻任务执行器"""
from typing import TYPE_CHECKING
from core.task.executors.base import BaseTaskExecutor
from core.task.models import UnifiedTask, TaskStatus, TaskType

if TYPE_CHECKING:
    from core.agent import RobotAgent


class PatrolExecutor(BaseTaskExecutor):
    """巡逻任务执行器
    
    执行周期性巡逻任务，调用Watch Action进行环境监测
    """
    
    def __init__(self, agent: 'RobotAgent', task_queue=None):
        """初始化巡逻执行器
        
        Args:
            agent: RobotAgent实例
            task_queue: 任务队列（用于创建紧急任务）
        """
        super().__init__()
        self.agent = agent
        self.task_queue = task_queue
    
    async def validate(self, task: UnifiedTask) -> bool:
        """验证任务参数"""
        if not await super().validate(task):
            return False
        
        # 验证Watch Action已注册
        action_name = task.execution_data.get("action_name", "watch")
        if action_name not in self.agent.actions:
            self._log(task, f"Action '{action_name}' not registered", "ERROR")
            return False
        
        return True
    
    async def execute(self, task: UnifiedTask) -> None:
        """执行巡逻任务
        
        执行流程：
        1. 验证Watch Action已注册
        2. 调用agent.execute_action("watch")
        3. 分析返回结果，判断是否有紧急情况
        4. 如有紧急情况，创建高优先级的AlertTask并入队
        5. 记录巡逻日志到任务历史
        6. 更新任务状态为COMPLETED
        """
        try:
            # 验证参数
            if not await self.validate(task):
                task.transition_to(TaskStatus.FAILED, "Validation failed")
                return
            
            # 获取参数
            action_name = task.execution_data.get("action_name", "watch")
            emergency_threshold = task.execution_data.get("emergency_threshold", 0.8)
            
            self._log(task, f"Starting patrol with action '{action_name}'")
            
            # 执行Watch Action
            result = await self.agent.execute_action(action_name)
            
            if not result.success:
                self._log(task, f"Watch action failed: {result.error}", "ERROR")
                task.result = {"success": False, "error": str(result.error)}
                task.transition_to(TaskStatus.FAILED, f"Action failed: {result.error}")
                return
            
            # 分析结果
            analysis_result = result.output or {}
            self._log(task, f"Watch action completed: {analysis_result}")
            
            # 检查是否有紧急情况
            is_emergency = analysis_result.get("emergency", False)
            confidence = analysis_result.get("confidence", 0.0)
            
            if is_emergency and confidence >= emergency_threshold:
                self._log(task, f"Emergency detected (confidence={confidence})", "WARNING")
                
                # 创建紧急AlertTask并入队
                await self._create_alert_task(analysis_result)
            
            # 记录巡逻结果
            task.result = {
                "success": True,
                "analysis": analysis_result,
                "emergency_detected": is_emergency
            }
            
            self._log(task, "Patrol completed successfully")
            task.transition_to(TaskStatus.COMPLETED, "Patrol completed")
            
        except Exception as e:
            await self.handle_error(task, e)
    
    async def _create_alert_task(self, emergency_data: dict) -> None:
        """创建紧急Alert任务
        
        Args:
            emergency_data: 紧急情况数据
        """
        if not self.task_queue:
            print(f"[{self._name}] Cannot create alert task: task_queue not set")
            return
        
        # 创建Alert任务
        alert_task = UnifiedTask(
            task_type=TaskType.USER_COMMAND,
            priority=8,  # 高优先级
            timeout=30.0,
            execution_data={
                "command_type": "alert",
                "command_params": emergency_data
            }
        )
        
        await self.task_queue.enqueue(alert_task)
        print(f"[{self._name}] Created alert task {alert_task.task_id[:8]}")
