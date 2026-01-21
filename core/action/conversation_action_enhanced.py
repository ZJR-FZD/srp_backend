"""ConversationActionEnhanced - 增强版语音对话（永久待机版）

新增功能：
1. 语音唤醒（"你好小艾"）- 永久待机，循环唤醒
2. 自然结束（静音超时 / "再见"关键词）
3. 更快的响应速度
4. 更自然的交互体验
5. 永久待机：聊天结束后自动回到唤醒监听状态
"""

import asyncio
import time
import signal
from typing import Dict, Any, Optional

from core.action.base import BaseAction, ActionContext, ActionResult, ActionMetadata
from core.action.listen_action_vad import ListenActionVAD, VADPresets
from core.action.speak_action import SpeakAction
from core.client.openai_client import OpenAIClient
from config import OPENAI_API_KEY, OPENAI_BASE_URL


class ConversationActionEnhanced(BaseAction):
    """增强版语音对话 Action（永久待机版）
    
    核心特性：
    - 永久待机：聊天结束后自动回到唤醒监听状态
    - 语音唤醒：说"你好小艾"启动对话
    - 自动结束：连续无语音或说"再见"
    - 优雅退出：支持 Ctrl+C 手动终止
    """
    
    def __init__(self):
        """初始化 ConversationActionEnhanced"""
        super().__init__()
        self.listen_action = None
        self.speak_action = None
        self.llm_client = None
        self.conversation_history = []
        self.max_history_length = 10
        
        # 唤醒词配置 - 永久待机关键：取消唤醒超时，设为None（无限等待）
        self.wake_words = ["你好小艾", "小艾", "hey ai","你好小爱", "小爱","小爱同学"]
        self.wake_timeout = None  # 改为None：无限等待唤醒词，不再超时终止
        
        # 结束配置
        self.idle_timeout = 30.0  # 聊天时无语音自动结束时间
        self.max_idle_rounds = 2  # 聊天时连续无语音的轮数
        
        # VAD 配置
        self.vad_preset = "STANDARD"
        
        # 新增：初始化累计唤醒次数（实例变量）
        self.total_conversations = 0  # 关键：从局部变量改为实例变量

        # 程序运行状态（用于优雅退出）
        self.running = True

    def get_metadata(self) -> ActionMetadata:
        """获取 Action 元信息"""
        return ActionMetadata(
            name="conversation_enhanced",
            version="2.1.0",
            description="增强版语音对话（永久待机），支持循环唤醒和优雅退出",
            dependencies=["dashscope_api", "openai_api", "audio_device", "webrtcvad"],
            capabilities=["asr", "vad", "llm_chat", "tts", "wake_word", "auto_end", "permanent_standby"],
            author="Robot Agent Team"
        )
    
    def initialize(self, config_dict: Dict[str, Any]) -> None:
        """初始化 ConversationActionEnhanced"""
        try:
            print("[ConversationEnhanced] Initializing...")
            
            # 更新配置
            self.wake_words = config_dict.get("wake_words", self.wake_words)
            self.wake_timeout = config_dict.get("wake_timeout", self.wake_timeout)
            self.idle_timeout = config_dict.get("idle_timeout", self.idle_timeout)
            self.max_idle_rounds = config_dict.get("max_idle_rounds", self.max_idle_rounds)
            self.vad_preset = config_dict.get("vad_preset", self.vad_preset)
            
            # 获取 VAD 配置
            vad_config = self._get_vad_config()
            
            # 初始化子组件
            self.listen_action = ListenActionVAD()
            self.listen_action.initialize(vad_config)
            
            self.speak_action = SpeakAction()
            self.speak_action.initialize({})
            
            self.llm_client = OpenAIClient(
                api_key=OPENAI_API_KEY,
                base_url=OPENAI_BASE_URL
            )
            
            # 注册 Ctrl+C 信号处理（优雅退出）
            signal.signal(signal.SIGINT, self._handle_exit)
            
            self._initialized = True
            print("[ConversationEnhanced] Initialization complete")
            print(f"  Wake words: {self.wake_words}")
            print(f"  Idle timeout: {self.idle_timeout}s")
            print(f"  🟢 已进入永久待机模式，按 Ctrl+C 退出")
            
        except Exception as e:
            print(f"[ConversationEnhanced] Initialization failed: {e}")
            raise

    def _handle_exit(self, signum, frame):
        """处理 Ctrl+C 退出信号"""
        print("\n\n[ConversationEnhanced] 收到退出信号，正在优雅关闭...")
        self.running = False
        # 清理资源
        self.cleanup()
        print("[ConversationEnhanced] 程序已退出")
        exit(0)
    
    def _get_vad_config(self) -> Dict[str, Any]:
        """获取 VAD 配置"""
        preset_map = {
            "QUICK_RESPONSE": VADPresets.QUICK_RESPONSE,
            "STANDARD": VADPresets.STANDARD,
            "LONG_SPEECH": VADPresets.LONG_SPEECH
        }
        return preset_map.get(self.vad_preset, VADPresets.STANDARD)
    
    async def execute(self, context: ActionContext) -> ActionResult:
        """执行永久待机版语音对话
        
        流程：
        1. 无限循环等待唤醒词
        2. 每次唤醒后进行一轮聊天
        3. 聊天结束后自动回到待机状态
        4. 支持 Ctrl+C 手动退出
        
        Returns:
            ActionResult: 包含总运行信息
        """
        start_time = time.time()
        all_conversation_results = []
        
        try:
            print("\n[ConversationEnhanced] Starting permanent standby mode...")
            
            if not self._initialized:
                raise RuntimeError("ConversationEnhanced not initialized")
            
            # ========== 核心：无限循环等待唤醒 ==========
            while self.running:
                # 1. 等待唤醒词（无限等待，直到检测到或手动退出）
                print(f"\n{'='*40}")
                print(f"💤 等待唤醒词: {', '.join(self.wake_words)}")
                print(f"   (永久待机，按 Ctrl+C 退出)")
                print(f"{'='*40}")
                
                awakened = await self._wait_for_wake_word()
                
                # 如果是手动退出，终止循环
                if not self.running:
                    break
                
                # 没检测到唤醒词（只是普通语音），继续循环监听
                if not awakened:
                    continue
                
                # 2. 播报欢迎语
                self.total_conversations += 1
                print(f"\n🎉 第 {self.total_conversations} 次唤醒成功！")
                await self._speak_text("我在，请和我聊天吧！", context)
                
                # 3. 单次对话循环
                conversation_results = await self._single_conversation_round(context)
                
                # 记录本次对话结果
                all_conversation_results.extend(conversation_results)
                
                # 4. 聊天结束，重置状态，回到待机
                self.clear_history()
                print(f"\n🔄 聊天结束，回到待机状态...")
            
            # 程序退出时统计
            elapsed_time = time.time() - start_time
            print(f"\n[ConversationEnhanced] 程序退出统计")
            print(f"  总运行时间: {elapsed_time:.2f}s")
            print(f"  累计唤醒次数: {self.total_conversations}")
            print(f"  累计对话轮数: {len(all_conversation_results)}")
            
            return ActionResult(
                success=True,
                output={
                    "total_conversations": self.total_conversations,
                    "all_conversation_results": all_conversation_results,
                    "total_running_time": elapsed_time
                },
                metadata={
                    "elapsed_time": elapsed_time,
                    "permanent_standby": True
                }
            )
            
        except Exception as e:
            elapsed_time = time.time() - start_time
            print(f"[ConversationEnhanced] Execution failed: {e}")
            import traceback
            traceback.print_exc()
            return ActionResult(
                success=False,
                error=str(e),
                metadata={
                    "elapsed_time": elapsed_time,
                    "total_conversations": self.total_conversations
                }
            )
    
    async def _wait_for_wake_word(self) -> bool:
        """等待唤醒词（无限等待，直到检测到或手动退出）"""
        try:
            print("[ConversationEnhanced] Listening for wake word...")
            
            # 无限等待：timeout设为None或极大值（这里用3600s=1小时，循环监听）
            listen_timeout = self.wake_timeout if self.wake_timeout else 3600.0
            
            while self.running:
                context = ActionContext(
                    agent_state=None,
                    input_data=listen_timeout
                )
                
                result = await self.listen_action.execute(context)
                
                # 手动退出
                if not self.running:
                    return False
                
                if result.success:
                    text = result.output.get("text", "").strip().lower()
                    
                    # 检查是否包含唤醒词
                    for wake_word in self.wake_words:
                        if wake_word.lower() in text:
                            print(f"[ConversationEnhanced] Wake word detected: {wake_word}")
                            return True
                    
                    # 没有唤醒词，但有语音 → 继续监听
                    print(f"[ConversationEnhanced] Speech detected but no wake word: {text}")
                    continue
                else:
                    # 超时（1小时）→ 继续循环监听
                    continue
                
        except Exception as e:
            print(f"[ConversationEnhanced] Error waiting for wake word: {e}")
            return False
    
    async def _single_conversation_round(self, context: ActionContext) -> list:
        """单次聊天循环（唤醒后）"""
        conversation_results = []
        conversation_count = 0
        idle_count = 0
        max_rounds = 20
        
        while conversation_count < max_rounds and self.running:
            round_start = time.time()
            print(f"\n[ConversationEnhanced] Round {conversation_count + 1}")
            
            # 监听用户输入
            user_text = await self._listen_with_timeout(self.idle_timeout)
            
            # 手动退出
            if not self.running:
                break
            
            if not user_text or user_text.strip() == "":
                idle_count += 1
                print(f"[ConversationEnhanced] No speech ({idle_count}/{self.max_idle_rounds})")
                
                if idle_count >= self.max_idle_rounds:
                    print("[ConversationEnhanced] Idle timeout, ending conversation")
                    await self._speak_text("好的，有需要随时叫我！", context)
                    break
                else:
                    await self._speak_text("还在吗？有什么想聊的吗？", context)
                    continue
            
            idle_count = 0
            print(f"[ConversationEnhanced] User: {user_text}")
            
            # 检查结束关键词
            if self._is_goodbye(user_text):
                print("[ConversationEnhanced] Goodbye detected")
                await self._speak_text("好的，再见！有需要随时叫我！", context)
                break
            
            # LLM 生成响应
            bot_response = await self._generate_response(user_text)
            if not bot_response:
                bot_response = "抱歉，我没听清，能再说一遍吗？"
            
            print(f"[ConversationEnhanced] Bot: {bot_response}")
            
            # 播放响应
            await self._speak_text(bot_response, context)
            
            round_elapsed = time.time() - round_start
            
            # 记录对话
            conversation_results.append({
                "conversation_id": self.total_conversations,
                "round": conversation_count + 1,
                "user_input": user_text,
                "bot_response": bot_response,
                "round_time": round_elapsed,
                "timestamp": time.time()
            })
            
            print(f"[ConversationEnhanced] Round {conversation_count + 1} completed in {round_elapsed:.2f}s")
            
            conversation_count += 1
        
        return conversation_results
    
    async def _listen_with_timeout(self, timeout: float) -> str:
        """监听语音（带超时）"""
        try:
            context = ActionContext(
                agent_state=None,
                input_data=timeout
            )
            
            result = await self.listen_action.execute(context)
            
            if result.success:
                return result.output.get("text", "").strip()
            else:
                return ""
                
        except Exception as e:
            print(f"[ConversationEnhanced] Error listening: {e}")
            return ""
    
    async def _generate_response(self, user_text: str) -> str:
        """生成 LLM 响应"""
        try:
            print("[ConversationEnhanced] Generating response...")
            
            self.conversation_history.append({"role": "user", "content": user_text})
            
            # 更新系统提示词
            messages = [
                {
                    "role": "system",
                    "content": "你是小艾，一个友好、幽默的聊天机器人。"
                               "请用简洁、自然、口语化的中文回答。"
                               "回答要简短（1-2句话），适合语音播报，不要在最后加上表情或动作描述词，因为你是在对话。"
                               "保持轻松愉快的聊天氛围。"
                }
            ]
            
            recent_history = self.conversation_history[-self.max_history_length:]
            messages.extend(recent_history)
            
            response = await self.llm_client.chat_completion(
                messages=messages,
                temperature=0.8,
                max_tokens=150
            )
            
            self.conversation_history.append({"role": "assistant", "content": response})
            
            if len(self.conversation_history) > self.max_history_length * 2:
                self.conversation_history = self.conversation_history[-self.max_history_length:]
            
            return response
            
        except Exception as e:
            print(f"[ConversationEnhanced] Error generating response: {e}")
            return "抱歉，我现在有点问题，能再说一遍吗？"
    
    async def _speak_text(self, text: str, context: ActionContext) -> bool:
        """播放语音"""
        try:
            speak_context = ActionContext(
                agent_state=context.agent_state if context else None,
                input_data=text,
                shared_data=context.shared_data if context else {},
                config={}
            )
            
            result = await self.speak_action.execute(speak_context)
            return result.success
                
        except Exception as e:
            print(f"[ConversationEnhanced] Error speaking: {e}")
            return False
    
    def _is_goodbye(self, text: str) -> bool:
        """检查是否是再见"""
        goodbye_keywords = [
            "再见", "拜拜", "byebye", "goodbye", "886",
            "结束", "停止", "退出", "关闭","你退下吧"
        ]
        
        text_lower = text.lower().strip()
        
        for keyword in goodbye_keywords:
            if keyword in text_lower:
                return True
        
        return False
    
    def clear_history(self) -> None:
        """清空对话历史"""
        self.conversation_history.clear()
    
    def cleanup(self) -> None:
        """清理资源"""
        print("[ConversationEnhanced] Cleaning up...")
        
        if self.listen_action:
            self.listen_action.cleanup()
        
        if self.speak_action:
            self.speak_action.cleanup()
        
        if self.llm_client:
            self.llm_client.close()
        
        self.conversation_history.clear()
        self.running = False
        
        self._initialized = False
        print("[ConversationEnhanced] Cleanup complete")


# 便捷测试函数
async def conversation_enhanced_test():
    """测试永久待机版对话"""
    from core.agent import AgentState
    
    print("="*60)
    print("增强版语音对话测试（永久待机版）")
    print("="*60)
    print("\n功能:")
    print("  1. 说 '你好小艾' 唤醒（永久待机，循环唤醒）")
    print("  2. 自由聊天")
    print("  3. 说 '再见' 或 30 秒无语音自动结束聊天（回到待机）")
    print("  4. 按 Ctrl+C 手动退出程序")
    print("="*60)
    
    action = ConversationActionEnhanced()
    action.initialize({
        "wake_words": ["你好小艾", "小艾", "hey ai","你好，小爱", "小爱","小爱同学"],
        "wake_timeout": None,  # 永久待机
        "idle_timeout": 30.0,
        "max_idle_rounds": 2,
        "vad_preset": "STANDARD"
    })
    
    context = ActionContext(
        agent_state=AgentState.IDLE,
        input_data=None
    )
    
    result = await action.execute(context)
    
    if result.success:
        print("\n" + "="*60)
        print("程序退出统计:")
        print("="*60)
        print(f"  累计唤醒次数: {result.output['total_conversations']}")
        print(f"  累计对话轮数: {len(result.output['all_conversation_results'])}")
        print(f"  总运行时间: {result.metadata['elapsed_time']:.2f}s")
    else:
        print("\n错误:", result.error)
    
    action.cleanup()
    return result


if __name__ == "__main__":
    import asyncio
    asyncio.run(conversation_enhanced_test())