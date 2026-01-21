# core/task/executors/user_task.py
"""用户任务执行器"""
from typing import TYPE_CHECKING
from core.task.executors.base import BaseTaskExecutor
from core.task.models import UnifiedTask, TaskStatus

if TYPE_CHECKING:
    from core.agent import RobotAgent


class UserTaskExecutor(BaseTaskExecutor):
    """用户任务执行器
    
    执行用户通过API或WebSocket发送的自定义任务
    """
    
    def __init__(self, agent: 'RobotAgent'):
        """初始化用户任务执行器
        
        Args:
            agent: RobotAgent实例
        """
        super().__init__()
        self.agent = agent
    
    async def validate(self, task: UnifiedTask) -> bool:
        """验证任务参数"""
        if not await super().validate(task):
            return False
        
        # 验证command_type
        command_type = task.execution_data.get("command_type")
        if not command_type:
            self._log(task, "No command_type provided", "ERROR")
            return False
        
        return True
    
    async def execute(self, task: UnifiedTask) -> None:
        """执行用户任务
        
        执行流程：
        1. 解析任务context中的命令类型
        2. 根据命令类型调用对应的Action或Action链
        3. 返回执行结果
        """
        try:
            # 验证参数
            if not await self.validate(task):
                task.transition_to(TaskStatus.FAILED, "Validation failed")
                return
            
            # 获取参数
            command_type = task.execution_data.get("command_type")
            command_params = task.execution_data.get("command_params", {})
            
            self._log(task, f"Executing user command: {command_type}")
            
            # 根据命令类型执行
            if command_type == "speak":
                await self._handle_speak_command(task, command_params)
            elif command_type == "alert":
                await self._handle_alert_command(task, command_params)
            elif command_type == "action":
                await self._handle_action_command(task, command_params)
            elif command_type == "custom":
                await self._handle_custom_command(task, command_params)
            else:
                self._log(task, f"Unknown command type: {command_type}", "ERROR")
                task.result = {"success": False, "error": f"Unknown command type: {command_type}"}
                task.transition_to(TaskStatus.FAILED, f"Unknown command type: {command_type}")
            
        except Exception as e:
            await self.handle_error(task, e)
    
    async def _handle_speak_command(self, task: UnifiedTask, params: dict) -> None:
        """处理speak命令"""
        text = params.get("text", "")
        if not text:
            self._log(task, "No text provided for speak command", "ERROR")
            task.transition_to(TaskStatus.FAILED, "No text provided")
            return
        
        result = await self.agent.execute_action("speak", input_data=text)
        
        if result.success:
            task.result = {"success": True, "action": "speak"}
            self._log(task, "Speak command completed")
            task.transition_to(TaskStatus.COMPLETED, "Speak completed")
        else:
            task.result = {"success": False, "error": str(result.error)}
            task.transition_to(TaskStatus.FAILED, f"Speak failed: {result.error}")
    
    async def _handle_alert_command(self, task: UnifiedTask, params: dict) -> None:
        """处理alert命令"""
        result = await self.agent.execute_action("alert", input_data=params)
        
        if result.success:
            task.result = {"success": True, "action": "alert"}
            self._log(task, "Alert command completed")
            task.transition_to(TaskStatus.COMPLETED, "Alert completed")
        else:
            task.result = {"success": False, "error": str(result.error)}
            task.transition_to(TaskStatus.FAILED, f"Alert failed: {result.error}")
    
    async def _handle_action_command(self, task: UnifiedTask, params: dict) -> None:
        """处理通用action命令"""
        action_name = params.get("action_name")
        if not action_name:
            self._log(task, "No action_name provided", "ERROR")
            task.transition_to(TaskStatus.FAILED, "No action_name provided")
            return
        
        if action_name not in self.agent.actions:
            self._log(task, f"Action '{action_name}' not registered", "ERROR")
            task.transition_to(TaskStatus.FAILED, f"Action '{action_name}' not found")
            return
        
        input_data = params.get("input_data")
        result = await self.agent.execute_action(action_name, input_data)
        
        if result.success:
            task.result = {"success": True, "action": action_name, "output": result.output}
            self._log(task, f"Action '{action_name}' completed")
            task.transition_to(TaskStatus.COMPLETED, f"Action '{action_name}' completed")
        else:
            task.result = {"success": False, "error": str(result.error)}
            task.transition_to(TaskStatus.FAILED, f"Action failed: {result.error}")
    
    async def _handle_custom_command(self, task: UnifiedTask, params: dict) -> None:
        """处理自定义命令"""
        self._log(task, "Custom command execution not implemented", "WARNING")
        task.result = {"success": False, "error": "Custom command not implemented"}
        task.transition_to(TaskStatus.FAILED, "Not implemented")
