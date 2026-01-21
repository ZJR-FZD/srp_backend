"""ConversationAction - 实时语音对话 Action

整合语音识别、LLM响应和语音合成的完整对话流程
"""

import asyncio
import time
import json
from typing import Dict, Any, Optional

from core.action.base import BaseAction, ActionContext, ActionResult, ActionMetadata
from core.action.listen_action import ListenAction
from core.action.speak_action import SpeakAction
from core.client.openai_client import OpenAIClient
from config import OPENAI_API_KEY, OPENAI_BASE_URL, QWEN_MAX_MODEL


class ConversationAction(BaseAction):
    """实时语音对话 Action
    
    实现完整的语音对话流程：
    1. 语音识别（ASR）
    2. LLM 理解和响应
    3. 语音合成（TTS）
    """
    
    def __init__(self):
        """初始化 ConversationAction"""
        super().__init__()
        self.listen_action = None
        self.speak_action = None
        self.llm_client = None
        self.conversation_history = []  # 对话历史
        self.max_history_length = 10  # 最大历史记录长度
        self.listen_duration = 5.0  # 默认录音时长
        self.enable_continuous = False  # 是否启用连续对话模式
    
    def get_metadata(self) -> ActionMetadata:
        """获取 Action 元信息"""
        return ActionMetadata(
            name="conversation",
            version="1.0.0",
            description="实时语音对话 Action，整合语音识别、LLM响应和语音合成",
            dependencies=["dashscope_api", "openai_api", "audio_device"],
            capabilities=["asr", "llm_chat", "tts", "conversation"],
            author="Robot Agent Team"
        )
    
    def initialize(self, config_dict: Dict[str, Any]) -> None:
        """初始化 ConversationAction
        
        Args:
            config_dict: 配置参数
                - listen_duration: 录音时长（秒）
                - enable_continuous: 是否启用连续对话模式
                - max_history_length: 最大对话历史长度
        """
        try:
            print("[ConversationAction] Initializing...")
            
            # 更新配置参数
            self.listen_duration = config_dict.get("listen_duration", self.listen_duration)
            self.enable_continuous = config_dict.get("enable_continuous", self.enable_continuous)
            self.max_history_length = config_dict.get("max_history_length", self.max_history_length)
            
            # 初始化子组件
            self.listen_action = ListenAction()
            self.listen_action.initialize({})
            
            self.speak_action = SpeakAction()
            self.speak_action.initialize({})
            
            self.llm_client = OpenAIClient(
                api_key=OPENAI_API_KEY,
                base_url=OPENAI_BASE_URL
            )
            
            self._initialized = True
            print("[ConversationAction] Initialization complete")
            
        except Exception as e:
            print(f"[ConversationAction] Initialization failed: {e}")
            raise
    
    async def execute(self, context: ActionContext) -> ActionResult:
        """执行语音对话
        
        Args:
            context: Action 执行上下文
                - input_data: 可选的初始提示文本或配置
                - config.listen_duration: 录音时长（可选）
                - config.enable_continuous: 是否启用连续对话（可选）
                
        Returns:
            ActionResult: 包含对话结果的 ActionResult
        """
        start_time = time.time()
        conversation_results = []
        
        try:
            print("[ConversationAction] Starting conversation...")
            
            if not self._initialized:
                raise RuntimeError("ConversationAction not initialized")
            
            # 获取配置
            listen_duration = context.config.get("listen_duration", self.listen_duration)
            enable_continuous = context.config.get("enable_continuous", self.enable_continuous)
            
            # 如果有初始提示，先播报
            if isinstance(context.input_data, str) and context.input_data.strip():
                await self._speak_text(context.input_data, context)
            
            # 开始对话循环
            conversation_count = 0
            max_conversations = 10 if enable_continuous else 1
            
            while conversation_count < max_conversations:
                print(f"[ConversationAction] Starting conversation round {conversation_count + 1}")
                
                # 1. 语音识别
                user_text = await self._listen_for_speech(listen_duration, context)
                if not user_text or user_text.strip() == "":
                    print("[ConversationAction] No speech detected, ending conversation")
                    break
                
                print(f"[ConversationAction] User said: {user_text}")
                
                # 检查是否要结束对话
                if self._should_end_conversation(user_text):
                    await self._speak_text("好的，再见！", context)
                    break
                
                # 2. LLM 理解和响应
                bot_response = await self._generate_response(user_text)
                if not bot_response:
                    bot_response = "抱歉，我没有理解您的意思，请再说一遍。"
                
                print(f"[ConversationAction] Bot response: {bot_response}")
                
                # 3. 语音合成和播放
                await self._speak_text(bot_response, context)
                
                # 记录对话结果
                conversation_results.append({
                    "round": conversation_count + 1,
                    "user_input": user_text,
                    "bot_response": bot_response,
                    "timestamp": time.time()
                })
                
                conversation_count += 1
                
                # 如果不是连续对话模式，结束
                if not enable_continuous:
                    break
                
                # 连续对话模式下，短暂暂停
                await asyncio.sleep(1.0)
            
            elapsed_time = time.time() - start_time
            print(f"[ConversationAction] Conversation complete in {elapsed_time:.2f}s")
            print(f"[ConversationAction] Total rounds: {conversation_count}")
            
            return ActionResult(
                success=True,
                output={
                    "conversation_results": conversation_results,
                    "total_rounds": conversation_count,
                    "conversation_history": self.conversation_history[-self.max_history_length:]
                },
                metadata={
                    "elapsed_time": elapsed_time,
                    "enable_continuous": enable_continuous,
                    "listen_duration": listen_duration
                }
            )
            
        except Exception as e:
            elapsed_time = time.time() - start_time
            print(f"[ConversationAction] Execution failed: {e}")
            import traceback
            traceback.print_exc()
            return ActionResult(
                success=False,
                error=e,
                metadata={
                    "elapsed_time": elapsed_time,
                    "conversation_results": conversation_results
                }
            )
    
    async def _listen_for_speech(self, duration: float, context: ActionContext) -> str:
        """执行语音识别
        
        Args:
            duration: 录音时长
            context: 上下文
            
        Returns:
            str: 识别的文本
        """
        try:
            print(f"[ConversationAction] Listening for {duration} seconds...")
            
            # 创建 ListenAction 的上下文
            listen_context = ActionContext(
                agent_state=context.agent_state,
                input_data=duration,
                shared_data=context.shared_data,
                config={"duration": duration}
            )
            
            # 执行语音识别
            result = await self.listen_action.execute(listen_context)
            
            if result.success:
                text = result.output.get("text", "").strip()
                print(f"[ConversationAction] Speech recognition result: {text}")
                return text
            else:
                print(f"[ConversationAction] Speech recognition failed: {result.error}")
                return ""
                
        except Exception as e:
            print(f"[ConversationAction] Error in speech recognition: {e}")
            return ""
    
    async def _generate_response(self, user_text: str) -> str:
        """生成 LLM 响应
        
        Args:
            user_text: 用户输入文本
            
        Returns:
            str: LLM 生成的响应
        """
        try:
            print("[ConversationAction] Generating LLM response...")
            
            # 添加到对话历史
            self.conversation_history.append({"role": "user", "content": user_text})
            
            # 构建对话消息
            messages = [
                {
                    "role": "system",
                    "content": "你是一个友好的巡检机器人助手。请用简洁、自然的中文回答用户的问题。回答要简短，适合语音播报。"
                }
            ]
            
            # 添加对话历史（保持在限制范围内）
            recent_history = self.conversation_history[-self.max_history_length:]
            messages.extend(recent_history)
            
            # 调用 LLM
            response = await self.llm_client.chat_completion(
                messages=messages,
                temperature=0.7,
                max_tokens=200  # 限制响应长度，适合语音播报
            )
            
            # 添加到对话历史
            self.conversation_history.append({"role": "assistant", "content": response})
            
            # 保持历史长度在限制范围内
            if len(self.conversation_history) > self.max_history_length * 2:
                self.conversation_history = self.conversation_history[-self.max_history_length:]
            
            return response
            
        except Exception as e:
            print(f"[ConversationAction] Error generating response: {e}")
            return "抱歉，我现在无法处理您的请求，请稍后再试。"
    
    async def _speak_text(self, text: str, context: ActionContext) -> bool:
        """执行语音合成和播放
        
        Args:
            text: 要播报的文本
            context: 上下文
            
        Returns:
            bool: 是否成功
        """
        try:
            print(f"[ConversationAction] Speaking: {text}")
            
            # 创建 SpeakAction 的上下文
            speak_context = ActionContext(
                agent_state=context.agent_state,
                input_data=text,
                shared_data=context.shared_data,
                config={}
            )
            
            # 执行语音合成
            result = await self.speak_action.execute(speak_context)
            
            if result.success:
                print("[ConversationAction] Speech synthesis completed")
                return True
            else:
                print(f"[ConversationAction] Speech synthesis failed: {result.error}")
                return False
                
        except Exception as e:
            print(f"[ConversationAction] Error in speech synthesis: {e}")
            return False
    
    def _should_end_conversation(self, user_text: str) -> bool:
        """判断是否应该结束对话
        
        Args:
            user_text: 用户输入文本
            
        Returns:
            bool: 是否应该结束对话
        """
        end_keywords = [
            "再见", "拜拜", "结束", "停止", "退出", "关闭",
            "bye", "goodbye", "stop", "exit", "quit", "end"
        ]
        
        user_text_lower = user_text.lower().strip()
        
        for keyword in end_keywords:
            if keyword in user_text_lower:
                return True
        
        return False
    
    def clear_history(self) -> None:
        """清空对话历史"""
        self.conversation_history.clear()
        print("[ConversationAction] Conversation history cleared")
    
    def get_history(self) -> list:
        """获取对话历史
        
        Returns:
            list: 对话历史列表
        """
        return self.conversation_history.copy()
    
    def cleanup(self) -> None:
        """清理资源"""
        print("[ConversationAction] Cleaning up...")
        
        # 清理子组件
        if self.listen_action:
            self.listen_action.cleanup()
        
        if self.speak_action:
            self.speak_action.cleanup()
        
        if self.llm_client:
            self.llm_client.close()
        
        # 清空对话历史
        self.conversation_history.clear()
        
        self._initialized = False
        print("[ConversationAction] Cleanup complete")


# 便捷测试函数
async def conversation_test(duration: float = 5.0, continuous: bool = False):
    """测试语音对话功能
    
    Args:
        duration: 录音时长（秒）
        continuous: 是否启用连续对话模式
    """
    from core.agent import AgentState
    
    action = ConversationAction()
    action.initialize({
        "listen_duration": duration,
        "enable_continuous": continuous
    })
    
    context = ActionContext(
        agent_state=AgentState.IDLE,
        input_data="你好，我是巡检机器人，有什么可以帮助您的吗？"
    )
    
    result = await action.execute(context)
    
    if result.success:
        print("Conversation Success:")
        for round_result in result.output.get("conversation_results", []):
            print(f"  Round {round_result['round']}:")
            print(f"    User: {round_result['user_input']}")
            print(f"    Bot: {round_result['bot_response']}")
    else:
        print("Conversation Error:", result.error)
    
    action.cleanup()
    return result


if __name__ == "__main__":
    # 单次对话测试
    print("=== 单次对话测试 ===")
    asyncio.run(conversation_test(duration=5.0, continuous=False))
    
    print("\n=== 连续对话测试 ===")
    asyncio.run(conversation_test(duration=3.0, continuous=True))
