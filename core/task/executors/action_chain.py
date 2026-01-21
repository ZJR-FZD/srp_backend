# core/task/executors/action_chain.py
"""Action链执行器"""
from typing import TYPE_CHECKING
from core.task.executors.base import BaseTaskExecutor
from core.task.models import UnifiedTask, TaskStatus

if TYPE_CHECKING:
    from core.agent import RobotAgent


class ActionChainExecutor(BaseTaskExecutor):
    """Action链执行器
    
    按顺序执行多个Action，支持数据传递和错误中断
    """
    
    def __init__(self, agent: 'RobotAgent'):
        """初始化Action链执行器
        
        Args:
            agent: RobotAgent实例
        """
        super().__init__()
        self.agent = agent
    
    async def validate(self, task: UnifiedTask) -> bool:
        """验证任务参数"""
        if not await super().validate(task):
            return False
        
        # 验证action_names
        action_names = task.execution_data.get("action_names", [])
        if not action_names:
            self._log(task, "No action_names provided", "ERROR")
            return False
        
        if not isinstance(action_names, list):
            self._log(task, "action_names must be a list", "ERROR")
            return False
        
        # 验证所有Action已注册
        for action_name in action_names:
            if action_name not in self.agent.actions:
                self._log(task, f"Action '{action_name}' not registered", "ERROR")
                return False
        
        return True
    
    async def execute(self, task: UnifiedTask) -> None:
        """执行Action链
        
        执行流程：
        1. 从execution_data获取action_names列表
        2. 按顺序执行每个Action
        3. 将前一个Action的输出作为后一个的输入
        4. 如某个Action失败，停止后续执行
        5. 记录所有Action的执行结果
        """
        try:
            # 验证参数
            if not await self.validate(task):
                task.transition_to(TaskStatus.FAILED, "Validation failed")
                return
            
            # 获取参数
            action_names = task.execution_data.get("action_names", [])
            initial_input = task.execution_data.get("initial_input")
            
            self._log(task, f"Starting action chain with {len(action_names)} actions")
            
            # 执行Action链
            results = []
            current_input = initial_input
            
            for i, action_name in enumerate(action_names):
                self._log(task, f"Executing action {i+1}/{len(action_names)}: {action_name}")
                
                # 执行Action
                result = await self.agent.execute_action(action_name, current_input)
                results.append({
                    "action": action_name,
                    "success": result.success,
                    "output": result.output,
                    "error": str(result.error) if result.error else None
                })
                
                # 检查是否成功
                if not result.success:
                    self._log(task, f"Action '{action_name}' failed: {result.error}", "ERROR")
                    task.result = {
                        "success": False,
                        "stopped_at": action_name,
                        "results": results
                    }
                    task.transition_to(TaskStatus.FAILED, f"Action '{action_name}' failed")
                    return
                
                # 使用当前Action的输出作为下一个Action的输入
                current_input = result.output
            
            # 所有Action执行成功
            task.result = {
                "success": True,
                "results": results,
                "final_output": current_input
            }
            
            self._log(task, f"Action chain completed successfully")
            task.transition_to(TaskStatus.COMPLETED, "All actions completed")
            
        except Exception as e:
            await self.handle_error(task, e)
