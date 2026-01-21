# core/task/executors/dispatcher_task.py
"""TaskDispatcher 任务执行器

专门处理来自 TaskDispatcher 的任务请求
"""
from typing import TYPE_CHECKING, Dict, Any
from core.task.executors.base import BaseTaskExecutor
from core.task.models import UnifiedTask, TaskStatus

if TYPE_CHECKING:
    from core.server.task_dispatcher import TaskDispatcher


class DispatcherTaskExecutor(BaseTaskExecutor):
    """TaskDispatcher 任务执行器
    
    负责执行通过 TaskDispatcher 提交的各类任务
    支持：execute_action, mcp_tool, user_input 等任务类型
    """
    
    def __init__(self, task_dispatcher: 'TaskDispatcher'):
        """初始化执行器
        
        Args:
            task_dispatcher: TaskDispatcher 实例引用
        """
        super().__init__()
        self.task_dispatcher = task_dispatcher
    
    async def validate(self, task: UnifiedTask) -> bool:
        """验证任务参数"""
        if not await super().validate(task):
            return False
        
        # 验证是否包含 task_request
        task_request = task.execution_data.get("task_request")
        if not task_request:
            self._log(task, "No task_request in execution_data", "ERROR")
            return False
        
        return True
    
    async def execute(self, task: UnifiedTask) -> None:
        """执行 TaskDispatcher 任务
        
        执行流程：
        1. 从 execution_data 中提取 task_request
        2. 调用 TaskDispatcher._execute_task_by_type 执行具体逻辑
        3. 同步结果到 TaskDispatcher.task_status_map
        4. 触发回调通知
        """
        try:
            # 验证参数
            if not await self.validate(task):
                task.transition_to(TaskStatus.FAILED, "Validation failed")
                return
            
            # 获取参数
            task_request = task.execution_data.get("task_request")
            callback_task_id = task.execution_data.get("task_id_for_callback")
            
            self._log(task, f"Executing dispatcher task: {task_request.task_type}")
            
            # 更新 TaskDispatcher 状态为运行中
            if callback_task_id and callback_task_id in self.task_dispatcher.task_status_map:
                task_info = self.task_dispatcher.task_status_map[callback_task_id]
                task_info.status = "running"
                task_info.updated_at = self._get_timestamp()
            
            # 执行实际任务逻辑
            result = await self.task_dispatcher._execute_task_by_type(task_request)
            
            # 记录结果
            task.result = result
            
            # 检查是否成功
            if result.get("success", True):
                self._log(task, "Task completed successfully")
                task.transition_to(TaskStatus.COMPLETED, "Execution completed")
                
                # 更新 TaskDispatcher 状态为完成
                if callback_task_id and callback_task_id in self.task_dispatcher.task_status_map:
                    task_info = self.task_dispatcher.task_status_map[callback_task_id]
                    task_info.status = "completed"
                    task_info.message = "Task completed successfully"
                    task_info.result = result
                    task_info.updated_at = self._get_timestamp()
                
                # 触发完成回调
                if callback_task_id:
                    await self.task_dispatcher.on_task_complete(callback_task_id, result)
            else:
                error = result.get("error", "Unknown error")
                self._log(task, f"Task failed: {error}", "ERROR")
                task.transition_to(TaskStatus.FAILED, str(error))
                
                # 更新 TaskDispatcher 状态为失败
                if callback_task_id and callback_task_id in self.task_dispatcher.task_status_map:
                    task_info = self.task_dispatcher.task_status_map[callback_task_id]
                    task_info.status = "failed"
                    task_info.message = f"Task failed: {error}"
                    task_info.updated_at = self._get_timestamp()
                
                # 触发失败回调
                if callback_task_id:
                    await self.task_dispatcher.on_task_failed(callback_task_id, {"error": error})
            
        except Exception as e:
            await self.handle_error(task, e)
            
            # 更新 TaskDispatcher 状态为失败
            callback_task_id = task.execution_data.get("task_id_for_callback")
            if callback_task_id and callback_task_id in self.task_dispatcher.task_status_map:
                task_info = self.task_dispatcher.task_status_map[callback_task_id]
                task_info.status = "failed"
                task_info.message = f"Execution error: {str(e)}"
                task_info.updated_at = self._get_timestamp()
            
            # 触发失败回调
            if callback_task_id:
                await self.task_dispatcher.on_task_failed(callback_task_id, {"error": str(e)})
    
    def _get_timestamp(self) -> float:
        """获取当前时间戳"""
        import time
        return time.time()
