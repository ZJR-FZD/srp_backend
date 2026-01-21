# core/task/models.py
"""统一任务模型定义"""
import uuid
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


class TaskType(Enum):
    """任务类型枚举"""
    PATROL = "patrol"                # 周期性巡逻任务
    MCP_CALL = "mcp_call"           # MCP工具调用任务
    USER_COMMAND = "user_command"    # 用户指令任务
    ACTION_CHAIN = "action_chain"    # Action链式调用
    DISPATCHER = "dispatcher"        # TaskDispatcher任务


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"      # 待执行
    RUNNING = "running"      # 执行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"        # 失败
    CANCELLED = "cancelled"  # 已取消
    RETRYING = "retrying"    # 重试中


class PlanStepStatus(Enum):
    """计划步骤状态枚举"""
    PENDING = "pending"          # 待执行
    IN_PROGRESS = "in_progress"  # 执行中
    COMPLETED = "completed"      # 已完成
    SKIPPED = "skipped"          # 已跳过（因上游结果改变）
    FAILED = "failed"            # 执行失败


@dataclass
class PlanStep:
    """执行计划中的单个步骤
    
    表示任务执行计划中的一个具体步骤，包含步骤描述、预期工具、执行状态等信息
    """
    step_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""  # 步骤描述（自然语言）
    expected_tool: Optional[str] = None  # 预期使用的工具名称（可选）
    status: PlanStepStatus = PlanStepStatus.PENDING
    execution_result: Optional[Dict[str, Any]] = None  # 执行结果（完成后填充）
    skip_reason: Optional[str] = None  # 跳过原因（如果被跳过）
    started_at: Optional[float] = None  # 开始执行时间戳
    completed_at: Optional[float] = None  # 完成时间戳
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式
        
        Returns:
            Dict[str, Any]: 字典表示
        """
        return {
            "step_id": self.step_id,
            "description": self.description,
            "expected_tool": self.expected_tool,
            "status": self.status.value,
            "execution_result": self.execution_result,
            "skip_reason": self.skip_reason,
            "started_at": self.started_at,
            "completed_at": self.completed_at
        }


@dataclass
class TaskPlan:
    """任务执行计划
    
    包含完整的执行步骤列表和计划元数据
    """
    steps: List[PlanStep] = field(default_factory=list)
    current_step_index: int = 0  # 当前执行到的步骤索引（从0开始）
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    updated_at: float = field(default_factory=lambda: datetime.now().timestamp())
    revision_count: int = 0  # 计划修订次数
    
    def get_current_step(self) -> Optional[PlanStep]:
        """获取当前待执行的步骤
        
        Returns:
            Optional[PlanStep]: 当前步骤，如果已全部完成则返回None
        """
        if self.current_step_index < len(self.steps):
            return self.steps[self.current_step_index]
        return None
    
    def is_completed(self) -> bool:
        """检查计划是否全部完成
        
        Returns:
            bool: 是否所有步骤都已完成或跳过
        """
        if not self.steps:
            return False
        return all(
            step.status in [PlanStepStatus.COMPLETED, PlanStepStatus.SKIPPED]
            for step in self.steps
        ) and self.current_step_index >= len(self.steps)
    
    def advance_step(self) -> None:
        """移动到下一步骤"""
        self.current_step_index += 1
        self.updated_at = datetime.now().timestamp()
    
    def increment_revision(self) -> None:
        """增加修订计数"""
        self.revision_count += 1
        self.updated_at = datetime.now().timestamp()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式
        
        Returns:
            Dict[str, Any]: 字典表示
        """
        return {
            "steps": [step.to_dict() for step in self.steps],
            "current_step_index": self.current_step_index,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "revision_count": self.revision_count
        }


@dataclass
class UnifiedTask:
    """统一任务数据结构
    
    所有类型的任务都使用此数据结构，通过task_type区分具体类型
    """
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_type: TaskType = TaskType.USER_COMMAND
    priority: int = 5  # 优先级 1-10，数字越大越优先
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    updated_at: float = field(default_factory=lambda: datetime.now().timestamp())
    timeout: float = 60.0  # 超时时间（秒）
    retry_count: int = 0  # 当前重试次数
    max_retries: int = 3  # 最大重试次数
    context: Dict[str, Any] = field(default_factory=dict)  # 任务上下文数据
    execution_data: Dict[str, Any] = field(default_factory=dict)  # 执行相关数据
    history: List[Dict[str, Any]] = field(default_factory=list)  # 执行历史记录
    result: Optional[Any] = None  # 任务执行结果
    plan: Optional[TaskPlan] = None  # 任务执行计划（计划驱动模式）
    
    def transition_to(self, new_status: TaskStatus, reason: str = "") -> None:
        """状态转换
        
        Args:
            new_status: 新状态
            reason: 转换原因
        """
        old_status = self.status
        self.status = new_status
        self.updated_at = datetime.now().timestamp()
        
        # 记录状态转换到历史
        self.history.append({
            "timestamp": self.updated_at,
            "event": "status_transition",
            "old_status": old_status.value,
            "new_status": new_status.value,
            "reason": reason
        })
        
        print(f"[Task:{self.task_id[:8]}] {old_status.value} -> {new_status.value} ({reason})")
    
    def is_terminal(self) -> bool:
        """检查是否为终态
        
        Returns:
            bool: 是否为终态（completed/failed/cancelled）
        """
        return self.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]
    
    def is_timeout(self) -> bool:
        """检查是否超时
        
        Returns:
            bool: 是否超时
        """
        current_time = datetime.now().timestamp()
        return (current_time - self.created_at) > self.timeout
    
    def can_retry(self) -> bool:
        """检查是否可以重试
        
        Returns:
            bool: 是否可以重试
        """
        return self.retry_count < self.max_retries
    
    def increment_retry(self) -> None:
        """增加重试计数"""
        self.retry_count += 1
        self.updated_at = datetime.now().timestamp()
        
        self.history.append({
            "timestamp": self.updated_at,
            "event": "retry",
            "retry_count": self.retry_count,
            "max_retries": self.max_retries
        })
    
    def get_plan_summary(self) -> Optional[Dict[str, Any]]:
        """获取计划摘要
        
        Returns:
            Optional[Dict[str, Any]]: 计划摘要，如果无计划则返回None
        """
        if not self.plan:
            return None
        
        return {
            "total_steps": len(self.plan.steps),
            "current_step": self.plan.current_step_index + 1,
            "revision_count": self.plan.revision_count,
            "is_completed": self.plan.is_completed(),
            "steps_summary": [
                {
                    "index": i + 1,
                    "description": step.description[:50] + "..." if len(step.description) > 50 else step.description,
                    "status": step.status.value,
                    "expected_tool": step.expected_tool
                }
                for i, step in enumerate(self.plan.steps)
            ]
        }
    
    def get_step_history(self) -> List[Dict[str, Any]]:
        """获取所有步骤的执行历史
        
        Returns:
            List[Dict[str, Any]]: 步骤执行历史列表
        """
        if not self.plan:
            return []
        
        return [
            {
                "step_index": i + 1,
                "description": step.description,
                "status": step.status.value,
                "expected_tool": step.expected_tool,
                "execution_result": step.execution_result,
                "skip_reason": step.skip_reason,
                "started_at": step.started_at,
                "completed_at": step.completed_at,
                "duration": (step.completed_at - step.started_at) if (step.started_at and step.completed_at) else None
            }
            for i, step in enumerate(self.plan.steps)
        ]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式
        
        Returns:
            Dict[str, Any]: 字典表示
        """
        result = {
            "task_id": self.task_id,
            "task_type": self.task_type.value,
            "priority": self.priority,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "timeout": self.timeout,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "context": self.context,
            "execution_data": self.execution_data,
            "history": self.history,
            "result": self.result
        }
        
        # 如果有计划，添加计划信息
        if self.plan:
            result["plan"] = self.plan.to_dict()
        
        return result
