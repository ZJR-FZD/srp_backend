"""
Qwen (通义千问) LLM
"""
from typing import List, Optional
import dashscope
from dashscope import Generation

from config.settings import settings
from .base_llm import BaseLLM, ChatMessage, LLMResponse


class QwenLLM(BaseLLM):
    """Qwen LLM"""
    
    def __init__(
        self,
        model: str = None,
        api_key: str = None,
        temperature: float = None,
        max_tokens: int = None
    ):
        """
        初始化 Qwen LLM
        
        Args:
            model: 模型名称
            api_key: API Key
            temperature: 温度参数
            max_tokens: 最大 token 数
        """
        model = model or settings.QWEN_MODEL
        temperature = temperature or settings.LLM_TEMPERATURE
        max_tokens = max_tokens or settings.LLM_MAX_TOKENS
        
        super().__init__(model, temperature, max_tokens)
        
        self.api_key = api_key or settings.QWEN_API_KEY
        if not self.api_key:
            raise ValueError("未设置 QWEN_API_KEY，请在 .env 文件中配置")
        
        # 设置 API Key
        dashscope.api_key = self.api_key
        
        print(f"✅ Qwen LLM 初始化成功！模型: {self.model}")
    
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
        messages = []
        
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        messages.append({
            "role": "user",
            "content": prompt
        })
        
        return self._call_api(messages, **kwargs)
    
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
        # 转换为 API 格式
        api_messages = [msg.to_dict() for msg in messages]
        
        return self._call_api(api_messages, **kwargs)
    
    def _call_api(self, messages: List[dict], **kwargs) -> LLMResponse:
        """
        调用 Qwen API
        
        Args:
            messages: 消息列表
            **kwargs: 其他参数
            
        Returns:
            LLMResponse: 生成结果
        """
        try:
            response = Generation.call(
                model=self.model,
                messages=messages,
                result_format='message',
                temperature=kwargs.get('temperature', self.temperature),
                max_tokens=kwargs.get('max_tokens', self.max_tokens),
                top_p=kwargs.get('top_p', 0.8)
            )
            
            if response.status_code == 200:
                output = response.output
                content = output['choices'][0]['message']['content']
                
                # 提取使用信息
                usage = {
                    'prompt_tokens': output['usage']['input_tokens'],
                    'completion_tokens': output['usage']['output_tokens'],
                    'total_tokens': output['usage']['total_tokens']
                }
                
                return LLMResponse(
                    content=content,
                    model=self.model,
                    usage=usage,
                    finish_reason=output['choices'][0].get('finish_reason')
                )
            else:
                raise Exception(f"API 调用失败: {response.message}")
        
        except Exception as e:
            raise Exception(f"Qwen API 错误: {e}")