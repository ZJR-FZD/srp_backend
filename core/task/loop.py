# core/task/loop.py
"""统一任务循环实现"""
import asyncio
from typing import Optional
from core.task.models import TaskStatus
from core.task.queue import TaskQueue
from core.task.scheduler import TaskScheduler


class UnifiedTaskLoop:
    """统一任务循环
    
    协调任务队列和调度器，运行主循环
    """
    
    def __init__(self, task_queue: TaskQueue, scheduler: TaskScheduler, loop_interval: float = 1.0):
        """初始化统一任务循环
        
        Args:
            task_queue: 任务队列
            scheduler: 任务调度器
            loop_interval: 主循环检查间隔（秒）
        """
        self.task_queue = task_queue
        self.scheduler = scheduler
        self.loop_interval = loop_interval
        
        self._running = False
        self._main_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        
        print(f"[UnifiedTaskLoop] Initialized with loop_interval={loop_interval}s")
    
    def start(self) -> None:
        """启动任务循环"""
        if self._running:
            print("[UnifiedTaskLoop] Already running")
            return
        
        self._running = True
        self._main_task = asyncio.create_task(self._main_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        print("[UnifiedTaskLoop] Task loop started")
    
    def stop(self) -> None:
        """停止任务循环"""
        if not self._running:
            print("[UnifiedTaskLoop] Not running")
            return
        
        self._running = False
        
        # 取消主循环
        if self._main_task:
            self._main_task.cancel()
            self._main_task = None
        
        # 取消清理循环
        if self._cleanup_task:
            self._cleanup_task.cancel()
            self._cleanup_task = None
        
        print("[UnifiedTaskLoop] Task loop stopped")
    
    async def _main_loop(self) -> None:
        """主循环逻辑"""
        try:
            print("[UnifiedTaskLoop] Entering main loop")
            
            while self._running:
                # 1. 检查是否有待执行任务
                queue_size = await self.task_queue.size()
                
                if queue_size > 0 and self.scheduler.can_schedule():
                    # 2. 从队列中取出优先级最高的任务
                    task = await self.task_queue.dequeue()
                    
                    if task:
                        # 3. 调度任务执行
                        scheduled = await self.scheduler.schedule(task)
                        
                        if not scheduled:
                            # 调度失败，重新入队
                            await self.task_queue.enqueue(task)
                
                # 4. 短暂休眠避免CPU占用
                await asyncio.sleep(self.loop_interval)
                
        except asyncio.CancelledError:
            print("[UnifiedTaskLoop] Main loop cancelled")
        except Exception as e:
            print(f"[UnifiedTaskLoop] Error in main loop: {e}")
    
    async def _cleanup_loop(self) -> None:
        """清理循环 - 定期清理已完成的任务"""
        try:
            print("[UnifiedTaskLoop] Entering cleanup loop")
            
            while self._running:
                # 每10秒清理一次
                await asyncio.sleep(10.0)
                
                # 清理任务队列中的已完成任务
                removed_count = await self.task_queue.remove_completed()
                
                # 清理调度器中的已完成异步任务
                cleaned_count = await self.scheduler.cleanup_finished_tasks()
                
                if removed_count > 0 or cleaned_count > 0:
                    print(f"[UnifiedTaskLoop] Cleanup: removed {removed_count} tasks from queue, "
                          f"cleaned {cleaned_count} finished async tasks")
                
                # 打印统计信息
                stats = await self.task_queue.get_statistics()
                running_count = self.scheduler.get_running_count()
                print(f"[UnifiedTaskLoop] Stats: queue_total={stats['total']}, "
                      f"pending={stats['pending']}, running={running_count}, "
                      f"completed={stats['completed']}, failed={stats['failed']}")
                
        except asyncio.CancelledError:
            print("[UnifiedTaskLoop] Cleanup loop cancelled")
        except Exception as e:
            print(f"[UnifiedTaskLoop] Error in cleanup loop: {e}")
    
    def is_running(self) -> bool:
        """检查任务循环是否正在运行
        
        Returns:
            bool: 是否正在运行
        """
        return self._running
    
    async def get_statistics(self) -> dict:
        """获取任务循环统计信息
        
        Returns:
            dict: 统计信息
        """
        queue_stats = await self.task_queue.get_statistics()
        
        return {
            "loop_running": self._running,
            "queue_size": await self.task_queue.size(),
            "running_tasks": self.scheduler.get_running_count(),
            "max_concurrent_tasks": self.scheduler.max_concurrent_tasks,
            **queue_stats
        }
