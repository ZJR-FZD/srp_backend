# core/task/executors/base.py
"""任务执行器基类"""
from abc import ABC, abstractmethod
from typing import Dict, Any
from core.task.models import UnifiedTask, TaskStatus


class BaseTaskExecutor(ABC):
    """任务执行器抽象基类
    
    所有任务执行器必须继承此类并实现相应的抽象方法
    """
    
    def __init__(self):
        """初始化执行器"""
        self._name = self.__class__.__name__
        print(f"[{self._name}] Initialized")
    
    @abstractmethod
    async def execute(self, task: UnifiedTask) -> None:
        """执行任务（核心业务逻辑）
        
        Args:
            task: 要执行的任务
            
        Note:
            - 执行器负责更新任务状态（transition_to）
            - 执行器负责设置任务结果（task.result）
            - 如需重试，执行器应创建新任务并入队
        """
        pass
    
    async def validate(self, task: UnifiedTask) -> bool:
        """验证任务参数（可选重写）
        
        Args:
            task: 要验证的任务
            
        Returns:
            bool: 是否验证通过
        """
        # 基础验证
        if not task.execution_data:
            print(f"[{self._name}] Task {task.task_id[:8]} has no execution_data")
            return False
        
        return True
    
    async def handle_error(self, task: UnifiedTask, error: Exception) -> None:
        """错误处理（可选重写）
        
        Args:
            task: 发生错误的任务
            error: 错误对象
        """
        print(f"[{self._name}] Error handling task {task.task_id[:8]}: {error}")
        task.result = {"error": str(error), "error_type": type(error).__name__}
        task.transition_to(TaskStatus.FAILED, f"Error: {str(error)}")
    
    def _log(self, task: UnifiedTask, message: str, level: str = "INFO") -> None:
        """记录日志到任务历史
        
        Args:
            task: 任务对象
            message: 日志消息
            level: 日志级别
        """
        from datetime import datetime
        
        task.history.append({
            "timestamp": datetime.now().timestamp(),
            "event": "log",
            "level": level,
            "message": message,
            "executor": self._name
        })
        
        print(f"[{self._name}:{level}] Task {task.task_id[:8]} - {message}")
