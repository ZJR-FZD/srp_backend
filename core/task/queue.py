# core/task/queue.py
"""任务队列实现"""
import asyncio
import heapq
from typing import Dict, List, Optional
from datetime import datetime
from core.task.models import UnifiedTask, TaskStatus


class TaskQueue:
    """任务队列 - 支持优先级排序
    
    使用堆实现优先级队列，优先级数字越大越优先
    """
    
    def __init__(self):
        """初始化任务队列"""
        self._heap: List[tuple] = []  # (负优先级, 创建时间, task_id, task)
        self._tasks: Dict[str, UnifiedTask] = {}  # task_id -> task 的映射
        self._lock = asyncio.Lock()  # 异步锁，保证线程安全
        
        print("[TaskQueue] Initialized")
    
    async def enqueue(self, task: UnifiedTask) -> None:
        """入队任务
        
        Args:
            task: 要入队的任务
        """
        async with self._lock:
            # 使用负优先级以实现大顶堆（Python heapq 是小顶堆）
            # 同优先级按创建时间排序
            heapq.heappush(
                self._heap,
                (-task.priority, task.created_at, task.task_id, task)
            )
            self._tasks[task.task_id] = task
            
            print(f"[TaskQueue] Enqueued task {task.task_id[:8]} "
                  f"(type={task.task_type.value}, priority={task.priority})")
    
    async def dequeue(self) -> Optional[UnifiedTask]:
        """出队任务（按优先级）
        
        Returns:
            Optional[UnifiedTask]: 优先级最高的待执行任务，如果队列为空返回None
        """
        async with self._lock:
            while self._heap:
                neg_priority, created_at, task_id, task = heapq.heappop(self._heap)
                
                # 检查任务是否仍然有效（可能已被取消）
                if task_id in self._tasks and task.status == TaskStatus.PENDING:
                    print(f"[TaskQueue] Dequeued task {task_id[:8]} "
                          f"(type={task.task_type.value}, priority={task.priority})")
                    return task
            
            return None
    
    async def get_by_id(self, task_id: str) -> Optional[UnifiedTask]:
        """根据ID查询任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            Optional[UnifiedTask]: 任务对象，如果找不到返回None
        """
        async with self._lock:
            return self._tasks.get(task_id)
    
    async def cancel(self, task_id: str) -> bool:
        """取消任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否成功取消
        """
        async with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            
            # 只能取消待执行或运行中的任务
            if task.status in [TaskStatus.PENDING, TaskStatus.RUNNING]:
                task.transition_to(TaskStatus.CANCELLED, "Cancelled by user")
                print(f"[TaskQueue] Cancelled task {task_id[:8]}")
                return True
            
            return False
    
    async def remove_completed(self) -> int:
        """移除已完成的任务
        
        Returns:
            int: 移除的任务数量
        """
        async with self._lock:
            # 移除终态任务
            terminal_task_ids = [
                task_id for task_id, task in self._tasks.items()
                if task.is_terminal()
            ]
            
            for task_id in terminal_task_ids:
                del self._tasks[task_id]
            
            if terminal_task_ids:
                print(f"[TaskQueue] Removed {len(terminal_task_ids)} completed tasks")
            
            return len(terminal_task_ids)
    
    async def size(self) -> int:
        """获取队列大小
        
        Returns:
            int: 待执行任务数量
        """
        async with self._lock:
            return len([t for t in self._tasks.values() if t.status == TaskStatus.PENDING])
    
    async def list_all(self) -> List[UnifiedTask]:
        """列出所有任务
        
        Returns:
            List[UnifiedTask]: 所有任务列表
        """
        async with self._lock:
            return list(self._tasks.values())
    
    async def get_statistics(self) -> Dict[str, int]:
        """获取队列统计信息
        
        Returns:
            Dict[str, int]: 统计信息
        """
        async with self._lock:
            stats = {
                "total": len(self._tasks),
                "pending": 0,
                "running": 0,
                "completed": 0,
                "failed": 0,
                "cancelled": 0,
                "retrying": 0
            }
            
            for task in self._tasks.values():
                stats[task.status.value] += 1
            
            return stats
