# core/action/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from enum import Enum


@dataclass
class ActionMetadata:
    """Action 元信息"""
    name: str
    version: str
    description: str
    dependencies: List[str] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)
    author: str = "Robot Agent Team"


@dataclass
class ActionContext:
    """Action 执行上下文"""
    agent_state: Any  # AgentState 枚举
    input_data: Any = None
    shared_data: Dict[str, Any] = field(default_factory=dict)
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionResult:
    """Action 执行结果"""
    success: bool
    output: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    next_actions: List[str] = field(default_factory=list)
    error: Optional[Exception] = None


class BaseAction(ABC):
    """Action 抽象基类
    
    所有 Action 必须继承此类并实现相应的抽象方法
    """
    
    def __init__(self):
        """初始化 Action"""
        self._initialized = False
        self._metadata = self.get_metadata()
    
    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> None:
        """初始化 Action 所需资源
        
        Args:
            config: 配置参数字典
        """
        pass
    
    @abstractmethod
    async def execute(self, context: ActionContext) -> ActionResult:
        """执行 Action 的核心业务逻辑
        
        Args:
            context: Action 执行上下文
            
        Returns:
            ActionResult: 执行结果
        """
        pass
    
    @abstractmethod
    def cleanup(self) -> None:
        """清理资源,释放状态
        
        注意:如果子类需要异步清理,可以将此方法定义为 async
        """
        pass
    
    @abstractmethod
    def get_metadata(self) -> ActionMetadata:
        """获取 Action 元信息
        
        Returns:
            ActionMetadata: Action 元信息
        """
        pass
    
    @property
    def is_initialized(self) -> bool:
        """检查 Action 是否已初始化"""
        return self._initialized
    
    @property
    def metadata(self) -> ActionMetadata:
        """获取 Action 元信息"""
        return self._metadata
