# core/task/scheduler.py
"""任务调度器实现"""
import asyncio
from typing import Dict, Optional
from datetime import datetime
from core.task.models import UnifiedTask, TaskType, TaskStatus


class TaskScheduler:
    """任务调度器 - 根据任务类型选择执行器，管理并发限制"""
    
    def __init__(self, max_concurrent_tasks: int = 5):
        """初始化任务调度器
        
        Args:
            max_concurrent_tasks: 最大并发任务数
        """
        self.max_concurrent_tasks = max_concurrent_tasks
        self._executors: Dict[TaskType, 'BaseTaskExecutor'] = {}  # 执行器映射
        self._running_tasks: Dict[str, asyncio.Task] = {}  # 运行中的异步任务
        
        print(f"[TaskScheduler] Initialized with max_concurrent_tasks={max_concurrent_tasks}")
    
    def register_executor(self, task_type: TaskType, executor: 'BaseTaskExecutor') -> None:
        """注册任务执行器
        
        Args:
            task_type: 任务类型
            executor: 执行器实例
        """
        self._executors[task_type] = executor
        print(f"[TaskScheduler] Registered executor for {task_type.value}")
    
    def get_executor(self, task_type: TaskType) -> Optional['BaseTaskExecutor']:
        """获取任务执行器
        
        Args:
            task_type: 任务类型
            
        Returns:
            Optional[BaseTaskExecutor]: 执行器实例，如果未注册返回None
        """
        return self._executors.get(task_type)
    
    def can_schedule(self) -> bool:
        """检查是否可以调度新任务（检查并发限制）
        
        Returns:
            bool: 是否可以调度
        """
        return len(self._running_tasks) < self.max_concurrent_tasks
    
    async def schedule(self, task: UnifiedTask) -> bool:
        """调度任务执行
        
        Args:
            task: 要调度的任务
            
        Returns:
            bool: 是否成功调度
        """
        # 检查并发限制
        if not self.can_schedule():
            print(f"[TaskScheduler] Cannot schedule task {task.task_id[:8]}: "
                  f"concurrent limit reached ({len(self._running_tasks)}/{self.max_concurrent_tasks})")
            return False
        
        # 获取执行器
        executor = self.get_executor(task.task_type)
        if not executor:
            print(f"[TaskScheduler] No executor found for task type {task.task_type.value}")
            task.transition_to(TaskStatus.FAILED, f"No executor for {task.task_type.value}")
            return False
        
        # 更新任务状态
        task.transition_to(TaskStatus.RUNNING, "Scheduled by TaskScheduler")
        
        # 创建异步任务
        print(f"[TaskScheduler] Scheduling task {task.task_id[:8]} "
              f"(type={task.task_type.value}, executor={executor.__class__.__name__})")
        
        async_task = asyncio.create_task(self._execute_with_monitoring(task, executor))
        self._running_tasks[task.task_id] = async_task
        
        return True
    
    async def _execute_with_monitoring(self, task: UnifiedTask, executor: 'BaseTaskExecutor') -> None:
        """执行任务并监控超时
        
        Args:
            task: 要执行的任务
            executor: 执行器实例
        """
        start_time = datetime.now().timestamp()
        
        try:
            # 使用超时控制
            await asyncio.wait_for(executor.execute(task), timeout=task.timeout)
            
            execution_time = datetime.now().timestamp() - start_time
            print(f"[TaskScheduler] Task {task.task_id[:8]} completed "
                  f"in {execution_time:.2f}s")
            
        except asyncio.TimeoutError:
            print(f"[TaskScheduler] Task {task.task_id[:8]} timed out after {task.timeout}s")
            task.transition_to(TaskStatus.FAILED, f"Timeout after {task.timeout}s")
            
        except asyncio.CancelledError:
            print(f"[TaskScheduler] Task {task.task_id[:8]} was cancelled")
            task.transition_to(TaskStatus.CANCELLED, "Task cancelled")
            
        except Exception as e:
            print(f"[TaskScheduler] Task {task.task_id[:8]} failed with error: {e}")
            task.transition_to(TaskStatus.FAILED, f"Execution error: {str(e)}")
            task.result = {"error": str(e)}
            
        finally:
            # 从运行中任务列表移除
            if task.task_id in self._running_tasks:
                del self._running_tasks[task.task_id]
    
    async def cancel_task(self, task_id: str) -> bool:
        """取消运行中的任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否成功取消
        """
        async_task = self._running_tasks.get(task_id)
        if async_task:
            async_task.cancel()
            print(f"[TaskScheduler] Cancelled running task {task_id[:8]}")
            return True
        return False
    
    def get_running_count(self) -> int:
        """获取运行中任务数量
        
        Returns:
            int: 运行中任务数量
        """
        return len(self._running_tasks)
    
    def get_running_task_ids(self) -> list:
        """获取运行中任务ID列表
        
        Returns:
            list: 任务ID列表
        """
        return list(self._running_tasks.keys())
    
    async def cleanup_finished_tasks(self) -> int:
        """清理已完成的异步任务
        
        Returns:
            int: 清理的任务数量
        """
        finished_ids = []
        for task_id, async_task in self._running_tasks.items():
            if async_task.done():
                finished_ids.append(task_id)
        
        for task_id in finished_ids:
            del self._running_tasks[task_id]
        
        if finished_ids:
            print(f"[TaskScheduler] Cleaned up {len(finished_ids)} finished tasks")
        
        return len(finished_ids)
