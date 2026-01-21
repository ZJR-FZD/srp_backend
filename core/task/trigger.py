# core/task/trigger.py
"""周期性任务触发器"""
import asyncio
from typing import Optional, Dict, Any
from core.task.models import UnifiedTask, TaskType
from core.task.queue import TaskQueue


class PeriodicTaskTrigger:
    """周期性任务触发器
    
    按照配置的时间间隔自动创建任务并入队
    """
    
    def __init__(
        self,
        task_queue: TaskQueue,
        interval: float,
        task_template: Dict[str, Any],
        enabled: bool = True
    ):
        """初始化周期性任务触发器
        
        Args:
            task_queue: 任务队列
            interval: 间隔时间（秒）
            task_template: 任务模板（包含task_type、execution_data等）
            enabled: 是否启用
        """
        self.task_queue = task_queue
        self.interval = interval
        self.task_template = task_template
        self.enabled = enabled
        
        self._running = False
        self._trigger_task: Optional[asyncio.Task] = None
        
        print(f"[PeriodicTaskTrigger] Initialized with interval={interval}s, enabled={enabled}")
    
    def start(self) -> None:
        """启动触发器"""
        if not self.enabled:
            print("[PeriodicTaskTrigger] Trigger is disabled, not starting")
            return
        
        if self._running:
            print("[PeriodicTaskTrigger] Already running")
            return
        
        self._running = True
        self._trigger_task = asyncio.create_task(self._trigger_loop())
        
        print("[PeriodicTaskTrigger] Trigger started")
    
    def stop(self) -> None:
        """停止触发器"""
        if not self._running:
            print("[PeriodicTaskTrigger] Not running")
            return
        
        self._running = False
        
        if self._trigger_task:
            self._trigger_task.cancel()
            self._trigger_task = None
        
        print("[PeriodicTaskTrigger] Trigger stopped")
    
    async def _trigger_loop(self) -> None:
        """触发循环"""
        try:
            print("[PeriodicTaskTrigger] Entering trigger loop")
            
            while self._running:
                # 创建任务
                await self._create_task()
                
                # 等待下次触发
                await asyncio.sleep(self.interval)
                
        except asyncio.CancelledError:
            print("[PeriodicTaskTrigger] Trigger loop cancelled")
        except Exception as e:
            print(f"[PeriodicTaskTrigger] Error in trigger loop: {e}")
    
    async def _create_task(self) -> None:
        """根据模板创建任务"""
        try:
            # 从模板创建任务
            task = UnifiedTask(
                task_type=TaskType(self.task_template.get("task_type", "patrol")),
                priority=self.task_template.get("priority", 3),
                timeout=self.task_template.get("timeout", 60.0),
                max_retries=self.task_template.get("max_retries", 3),
                context=self.task_template.get("context", {}),
                execution_data=self.task_template.get("execution_data", {})
            )
            
            # 入队
            await self.task_queue.enqueue(task)
            print(f"[PeriodicTaskTrigger] Created periodic task {task.task_id[:8]}")
            
        except Exception as e:
            print(f"[PeriodicTaskTrigger] Error creating task: {e}")
    
    def is_running(self) -> bool:
        """检查触发器是否正在运行
        
        Returns:
            bool: 是否正在运行
        """
        return self._running
    
    def set_enabled(self, enabled: bool) -> None:
        """设置触发器启用状态
        
        Args:
            enabled: 是否启用
        """
        self.enabled = enabled
        
        if enabled and not self._running:
            self.start()
        elif not enabled and self._running:
            self.stop()
