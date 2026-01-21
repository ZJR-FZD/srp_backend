# core/client/openai_client.py
"""OpenAI API 统一客户端

支持调用多个 Qwen 模型：
- qwen-max: 任务决策推理
- qwen-vl-plus: 图像理解
- qwen-omni-flash: 用户交互（TTS/ASR）
"""

import asyncio
import base64
import json
from typing import Dict, List, Any, Optional
from openai import AsyncOpenAI
from config import OPENAI_BASE_URL, OPENAI_API_KEY

GENERAL_MODEL = "qwen-plus"  # 通用对话模型

class OpenAIClient:
    """OpenAI API 统一客户端"""
    
    def __init__(
        self,
        api_key: str = OPENAI_API_KEY,
        base_url: str = OPENAI_BASE_URL,
        timeout: int = 30,
        max_retries: int = 3
    ):
        """初始化客户端
        
        Args:
            api_key: OpenAI API 密钥
            base_url: API 基础 URL
            timeout: 请求超时时间（秒）
            max_retries: 失败重试次数
        """
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        
        # 初始化 OpenAI 客户端
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries
        )
        
        print(f"[OpenAI Client] Initialized with base_url: {base_url}")

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ) -> str:
        """文本对话/推理
        
        Args:
            model: 模型名称（如 qwen-max）
            messages: 消息列表
            temperature: 生成温度
            max_tokens: 最大生成 token 数
            **kwargs: 其他参数
            
        Returns:
            str: 模型生成的文本
        """
        try:
            print(f"[OpenAI Client] Calling chat_completion with model: {GENERAL_MODEL}")
            print(f"[OpenAI Client] API Key: {self.api_key[:20]}...")
            print(f"[OpenAI Client] Base URL: {self.base_url}")
            print(f"[OpenAI Client] Messages count: {len(messages)}")
            
            response = await self.client.chat.completions.create(
                model=GENERAL_MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            
            result = response.choices[0].message.content
            print(f"[OpenAI Client] Chat completion success, length: {len(result)}")
            return result
            
        except Exception as e:
            print(f"[OpenAI Client] Error in chat_completion: {e}")
            print(f"[OpenAI Client] Error type: {type(e)}")
            import traceback
            traceback.print_exc()
            raise

    async def chat_completion_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ):
        """流式文本对话"""
        try:
            print(f"[OpenAI Client] Streaming chat_completion...")
            
            response = await self.client.chat.completions.create(
                model=GENERAL_MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,  # 关键
                **kwargs
            )
            
            async for chunk in response:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
            
            print(f"[OpenAI Client] Streaming finished")
            
        except Exception as e:
            print(f"[OpenAI Client] Streaming error: {e}")
            raise

    async def function_call_completion(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]],
        **kwargs
    ) -> Any:
        """函数调用/推理
        
        Args:
            messages: 消息列表
            tools: 工具列表
            **kwargs: 其他参数
            
        Returns:
            Any: 包含 tool_calls 的响应对象的 message 部分
        """
        try:
            print(f"[OpenAI Client] Calling function_call_completion with model: {GENERAL_MODEL}")
            
            response = await self.client.chat.completions.create(
                model=GENERAL_MODEL,
                messages=messages,
                tools=tools,
                **kwargs
            )
            
            message = response.choices[0].message
            print(f"[OpenAI Client] Function call completion success")
            if hasattr(message, 'tool_calls') and message.tool_calls:
                print(f"[OpenAI Client] Tool calls: {message.tool_calls}")
            else:
                print(f"[OpenAI Client] No tool calls, content: {message.content}")
            return message
            
        except Exception as e:
            print(f"[OpenAI Client] Error in function_call_completion: {e}")
            raise
        
    
    async def vision_completion(
        self,
        model: str,
        image: bytes,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 500,
        **kwargs
    ) -> Dict[str, Any]:
        """图像理解
        
        Args:
            model: 模型名称（如 qwen-vl-plus）
            image: 图像字节数据
            prompt: 提示词
            temperature: 生成温度
            max_tokens: 最大生成 token 数
            **kwargs: 其他参数
            
        Returns:
            Dict: 解析后的结构化数据
        """
        try:
            print(f"[OpenAI Client] Calling vision_completion with model: {model}")
            
            # 将图像编码为 base64
            image_base64 = base64.b64encode(image).decode('utf-8')
            image_url = f"data:image/jpeg;base64,{image_base64}"
            
            # 构造消息
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": image_url}
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ]
            
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            
            result_text = response.choices[0].message.content
            print(f"[OpenAI Client] Vision completion success, result: {result_text[:100]}...")
            
            # 尝试解析为 JSON
            try:
                result_dict = json.loads(result_text)
                return result_dict
            except json.JSONDecodeError:
                # 如果不是 JSON，返回原始文本
                return {"description": result_text, "raw_response": True}
            
        except Exception as e:
            print(f"[OpenAI Client] Error in vision_completion: {e}")
            raise
    
    async def tts_completion(
        self,
        model: str,
        text: str,
        voice: str = "default",
        speed: float = 1.0,
        **kwargs
    ) -> bytes:
        """文本转语音
        
        Args:
            model: 模型名称（如 qwen-omni-flash）
            text: 要转换的文本
            voice: 音色类型
            speed: 语速倍率
            **kwargs: 其他参数
            
        Returns:
            bytes: 音频数据
        """
        try:
            print(f"[OpenAI Client] Calling tts_completion with model: {model}")
            print(f"[OpenAI Client] Text to speak: {text}")
            
            response = await self.client.audio.speech.create(
                model=model,
                input=text,
                voice=voice,
                speed=speed,
                **kwargs
            )
            
            # 读取音频数据
            audio_bytes = response.content
            print(f"[OpenAI Client] TTS completion success, audio size: {len(audio_bytes)} bytes")
            return audio_bytes
            
        except Exception as e:
            print(f"[OpenAI Client] Error in tts_completion: {e}")
            # 如果 API 不支持，返回模拟数据
            print(f"[OpenAI Client] Warning: TTS API might not be available, returning mock data")
            return b""  # 返回空字节，避免崩溃
    
    async def asr_completion(
        self,
        model: str,
        audio: bytes,
        language: str = "zh",
        **kwargs
    ) -> str:
        """语音转文本
        
        Args:
            model: 模型名称（如 qwen-omni-flash）
            audio: 音频字节数据
            language: 语言代码
            **kwargs: 其他参数
            
        Returns:
            str: 识别的文本
        """
        try:
            print(f"[OpenAI Client] Calling asr_completion with model: {model}")
            
            response = await self.client.audio.transcriptions.create(
                model=model,
                file=audio,
                language=language,
                **kwargs
            )
            
            result = response.text
            print(f"[OpenAI Client] ASR completion success: {result}")
            return result
            
        except Exception as e:
            print(f"[OpenAI Client] Error in asr_completion: {e}")
            print(f"[OpenAI Client] Warning: ASR API might not be available")
            return ""  # 返回空字符串，避免崩溃
    
    def close(self):
        """关闭客户端连接"""
        print("[OpenAI Client] Closing client")
        # AsyncOpenAI 客户端会自动管理连接
        pass
