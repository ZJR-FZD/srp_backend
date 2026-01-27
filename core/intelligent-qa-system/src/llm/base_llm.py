"""
LLM 基类
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class ChatMessage:
    """聊天消息"""
    role: str  # 'system', 'user', 'assistant'
    content: str
    
    def to_dict(self) -> Dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass
class LLMResponse:
    """LLM 响应"""
    content: str
    model: str
    usage: Optional[Dict[str, int]] = None
    finish_reason: Optional[str] = None
    
    def __str__(self):
        return self.content


class BaseLLM(ABC):
    """LLM 基类"""
    
    def __init__(self, model: str, temperature: float = 0.7, max_tokens: int = 2000):
        """
        初始化 LLM
        
        Args:
            model: 模型名称
            temperature: 温度参数 (0-1)
            max_tokens: 最大生成 token 数
        """
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
    
    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """
        生成文本
        
        Args:
            prompt: 用户提示
            system_prompt: 系统提示
            **kwargs: 其他参数
            
        Returns:
            LLMResponse: 生成结果
        """
        pass
    
    @abstractmethod
    def chat(
        self,
        messages: List[ChatMessage],
        **kwargs
    ) -> LLMResponse:
        """
        多轮对话
        
        Args:
            messages: 消息列表
            **kwargs: 其他参数
            
        Returns:
            LLMResponse: 生成结果
        """
        pass
    
    def create_prompt_with_context(
        self,
        question: str,
        context: str,
        system_prompt: Optional[str] = None
    ) -> str:
        """
        创建带上下文的提示
        
        Args:
            question: 用户问题
            context: 检索到的上下文
            system_prompt: 系统提示
            
        Returns:
            str: 完整提示
        """
        if system_prompt:
            prompt = f"{system_prompt}\n\n"
        else:
            prompt = ""
        
        prompt += f"""基于以下上下文信息回答问题。如果上下文中没有相关信息，请说"根据提供的信息无法回答这个问题"。

上下文信息:
{context}

问题: {question}

回答:"""
        
        return prompt
    
    def format_chat_history(
        self,
        history: List[tuple],
        current_question: str,
        context: str
    ) -> List[ChatMessage]:
        """
        格式化聊天历史为消息列表
        
        Args:
            history: 历史对话 [(question, answer), ...]
            current_question: 当前问题
            context: 检索到的上下文
            
        Returns:
            List[ChatMessage]: 消息列表
        """
        messages = []
        
        # 系统提示
        system_msg = ChatMessage(
            role="system",
            content="你是一个智能问答助手。请基于提供的上下文信息准确回答用户的问题。"
        )
        messages.append(system_msg)
        
        # 历史对话
        for q, a in history[-3:]:  # 只保留最近3轮对话
            messages.append(ChatMessage(role="user", content=q))
            messages.append(ChatMessage(role="assistant", content=a))
        
        # 当前问题
        user_msg = ChatMessage(
            role="user",
            content=f"""基于以下上下文信息回答问题:

上下文信息:
{context}

问题: {current_question}"""
        )
        messages.append(user_msg)
        
        return messages