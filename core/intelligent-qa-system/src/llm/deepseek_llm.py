"""
DeepSeek LLM
"""
from typing import List, Optional
import httpx

from config.settings import settings
from .base_llm import BaseLLM, ChatMessage, LLMResponse


class DeepSeekLLM(BaseLLM):
    """DeepSeek LLM"""
    
    def __init__(
        self,
        model: str = None,
        api_key: str = None,
        api_base: str = None,
        temperature: float = None,
        max_tokens: int = None
    ):
        """
        初始化 DeepSeek LLM
        
        Args:
            model: 模型名称
            api_key: API Key
            api_base: API 基础 URL
            temperature: 温度参数
            max_tokens: 最大 token 数
        """
        model = model or settings.DEEPSEEK_MODEL
        temperature = temperature or settings.LLM_TEMPERATURE
        max_tokens = max_tokens or settings.LLM_MAX_TOKENS
        
        super().__init__(model, temperature, max_tokens)
        
        self.api_key = api_key or settings.DEEPSEEK_API_KEY
        if not self.api_key:
            raise ValueError("未设置 DEEPSEEK_API_KEY，请在 .env 文件中配置")
        
        self.api_base = api_base or settings.DEEPSEEK_API_BASE
        
        print(f"✅ DeepSeek LLM 初始化成功！模型: {self.model}")
    
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
        调用 DeepSeek API
        
        Args:
            messages: 消息列表
            **kwargs: 其他参数
            
        Returns:
            LLMResponse: 生成结果
        """
        url = f"{self.api_base}/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": kwargs.get('temperature', self.temperature),
            "max_tokens": kwargs.get('max_tokens', self.max_tokens),
            "top_p": kwargs.get('top_p', 0.95),
            "stream": False
        }
        
        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                
                data = response.json()
                
                content = data['choices'][0]['message']['content']
                
                # 提取使用信息
                usage = data.get('usage', {})
                
                return LLMResponse(
                    content=content,
                    model=self.model,
                    usage=usage,
                    finish_reason=data['choices'][0].get('finish_reason')
                )
        
        except httpx.HTTPStatusError as e:
            raise Exception(f"DeepSeek API HTTP 错误: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            raise Exception(f"DeepSeek API 错误: {e}")