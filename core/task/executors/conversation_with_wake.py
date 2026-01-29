# core/task/executors/conversation_with_wake.py
"""ConversationExecutor with Wake Word - 带唤醒词的对话执行器"""

from typing import TYPE_CHECKING, Dict, Any, Optional, Callable
from core.task.executors.base import BaseTaskExecutor
from core.task.models import UnifiedTask, TaskStatus, TaskType
from core.action.listen_action_vad import ListenActionVAD, VADPresets
import asyncio
import time

if TYPE_CHECKING:
    from core.agent import RobotAgent


class ConversationState:
    """对话状态"""
    WAITING_WAKE = "waiting_wake"      # 等待唤醒
    CONVERSING = "conversing"          # 对话中
    IDLE = "idle"                      # 闲置（无语音）


class ConversationExecutorWithWake(BaseTaskExecutor):
    """带唤醒词的对话执行器
    
    流程：
    1. 永久监听唤醒词（"你好，小狐狸"）
    2. 唤醒后进入对话模式
    3. 对话结束（再见/超时）后回到待机
    """
    
    def __init__(self, agent: 'RobotAgent', llm_client, 
                 wake_words: list = None,
                 idle_timeout: float = 30.0,
                 max_idle_rounds: int = 2,
                 state_callback: Optional[Callable] = None):
        """初始化
        
        Args:
            agent: Agent 实例
            llm_client: LLM 客户端
            wake_words: 唤醒词列表
            idle_timeout: 对话时无语音超时（秒）
            max_idle_rounds: 最大无语音轮数
            state_callback: 状态回调函数 (state, data) -> None
        """
        super().__init__()
        self.agent = agent
        self.llm_client = llm_client
        self.wake_words = wake_words or ["你好小狐狸", "小狐狸", "hey fox"]
        self.idle_timeout = idle_timeout
        self.max_idle_rounds = max_idle_rounds
        self.state_callback = state_callback  # 用于推送状态给前端
        
        # 对话历史
        self.conversation_history = []
        self.max_history_length = 10
        
        # 💬 新增：消息列表（用于前端字幕显示）
        self.messages = []  # 格式: [{"role": "user|assistant", "content": "...", "timestamp": ...}]
        self.max_messages = 50
        
        # 监听器
        self.listen_action = ListenActionVAD()
        self.listen_action.initialize(VADPresets.STANDARD)
        
        # 状态控制
        self.current_state = ConversationState.WAITING_WAKE
        self.running = False  # 👈 改为 False，由前端启动
        self.listening_active = False  # 👈 新增：当前是否在监听
        self.total_conversations = 0
    
    def _add_message(self, role: str, content: str):
        """添加消息到列表（供前端显示）"""
        message = {
            "role": role,
            "content": content,
            "timestamp": time.time()
        }
        self.messages.append(message)
        
        # 限制消息数量
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages:]
        
        # 通过状态回调推送给前端
        if self.state_callback:
            self.state_callback("message", {
                "message": message,
                "total_messages": len(self.messages)
            })
    
    def get_messages(self, limit: int = None) -> list:
        """获取消息列表"""
        if limit:
            return self.messages[-limit:]
        return self.messages
    
    def clear_messages(self):
        """清空消息列表"""
        self.messages.clear()
    
    def start_listening(self):
        """启动监听（由前端调用）"""
        if not self.running:
            self.running = True
            self.listening_active = True
            print("🎤 监听已启动")
            
            # 通知前端
            if self.state_callback:
                self.state_callback("listening_started", {
                    "message": "监听已启动"
                })
    
    def stop_listening(self):
        """停止监听（由前端调用）"""
        self.running = False
        self.listening_active = False
        print("🛑 监听已停止")
        
        # 通知前端
        if self.state_callback:
            self.state_callback("listening_stopped", {
                "message": "监听已停止"
            })
    
    def _log(self, task: Optional[UnifiedTask], message: str, level: str = "INFO"):
        """自定义日志方法，避免访问 None 的 history 属性"""
        # 1. 控制台打印（保留原有日志逻辑）
        log_prefix = f"[ConversationExecutorWithWake:{level}]"
        if task:
            log_prefix += f" Task {task.task_id[:8]}"
        print(f"{log_prefix} {message}")
        
        # 2. 如果 task 不为空，才记录到 task.history（避免 None 报错）
        if task is not None and hasattr(task, 'history'):
            task.history.append({
                "timestamp": time.time(),
                "event": "log",
                "level": level,
                "message": message,
                "executor": self.__class__.__name__
            })

    async def validate(self, task: UnifiedTask) -> bool:
        return await super().validate(task)
    
    async def execute(self, task: UnifiedTask) -> None:
        """执行永久监听对话
        
        task.execution_data 可选参数：
        - mode: "once" (单次对话) / "loop" (永久监听，默认)
        """
        try:
            mode = task.execution_data.get("mode", "loop")
            
            self._log(task, f"Starting conversation (mode={mode})")
            
            if mode == "loop":
                # 永久监听模式
                await self._permanent_standby_loop(task)
            else:
                # 单次对话模式
                await self._single_conversation(task)
            
            task.result = {
                "success": True,
                "total_conversations": self.total_conversations
            }
            task.transition_to(TaskStatus.COMPLETED, "Conversation ended")
            
        except Exception as e:
            await self.handle_error(task, e)
    
    async def _permanent_standby_loop(self, task: UnifiedTask):
        """永久待机循环 - 真正的永久监听，直到手动停止"""
        self._log(task, "Entering permanent standby mode (waiting for start signal)")
        print("=" * 60)
        print("🎧 等待启动监听...")
        print("💡 请在前端点击【启动监听】按钮开始")
        print("=" * 60)
        
        # 等待前端启动信号
        while not self.running:
            await asyncio.sleep(0.5)
        
        print("\n✅ 监听已启动！开始永久待机循环...")
        
        while self.running:
            # 1. 等待唤醒
            print(f"\n💤 等待唤醒词: {', '.join(self.wake_words)}")
            
            self._set_state(ConversationState.WAITING_WAKE, {
                "message": f"等待唤醒词: {', '.join(self.wake_words)}"
            })
            
            print("📢 开始监听语音...")
            awakened = await self._wait_for_wake_word()
            print(f"✅ 监听结束，唤醒状态: {awakened}")
            
            if not self.running:
                break
            
            if not awakened:
                continue
            
            # 2. 唤醒成功
            self.total_conversations += 1
            self._log(task, f"Awakened (conversation #{self.total_conversations})")
            
            self._set_state("awakened", {
                "message": "唤醒成功",
                "conversation_id": self.total_conversations
            })
            
            # 播报欢迎语
            welcome_msg = "我在，请和我聊天吧！"
            self._add_message("assistant", welcome_msg)
            await self._speak(welcome_msg)
            
            # 3. 进入对话循环
            await self._conversation_loop(task)
            
            # 4. 对话结束，重置
            self._log(task, "Conversation ended, back to standby")
            self.conversation_history.clear()
            
            self._set_state("goodbye", {
                "message": "对话结束，回到待机",
                "conversation_id": self.total_conversations
            })
            
            await asyncio.sleep(1)  # 短暂延迟
    
    async def _single_conversation(self, task: UnifiedTask):
        """单次对话（用于测试或 API 调用）"""
        self.total_conversations += 1
        
        self._set_state("conversing", {
            "conversation_id": self.total_conversations
        })
        
        await self._conversation_loop(task)
        
        self._set_state("completed", {
            "conversation_id": self.total_conversations
        })
    
    async def _wait_for_wake_word(self) -> bool:
        """等待唤醒词 - 真正的永久监听，直到检测到唤醒词或被停止"""
        from core.action.base import ActionContext
        
        print("\n[_wait_for_wake_word] 进入唤醒词监听...")
        
        while self.running:
            print(f"[_wait_for_wake_word] 开始监听（无限循环，直到检测到唤醒词或手动停止）")
            
            # 监听语音 - 使用较长超时（60秒），但会循环重试
            context = ActionContext(agent_state=None, input_data=60.0)
            result = await self.listen_action.execute(context)
            
            print(f"[_wait_for_wake_word] 监听结果: success={result.success}")
            
            if not self.running:
                return False
            
            if result.success:
                text = result.output.get("text", "").strip().lower()
                print(f"[_wait_for_wake_word] 识别到语音: {text}")
                
                # 检查唤醒词
                for wake_word in self.wake_words:
                    if wake_word.lower() in text:
                        print(f"[_wait_for_wake_word] ✅ 检测到唤醒词: {wake_word}")
                        return True
                
                # 没有唤醒词，继续监听
                print(f"[_wait_for_wake_word] ⚠️  语音中没有唤醒词，继续监听")
            else:
                print(f"[_wait_for_wake_word] ⚠️  监听超时或失败，继续下一轮")
            
            await asyncio.sleep(0.1)
        
        return False
    
    async def _conversation_loop(self, task: UnifiedTask):
        """对话循环"""
        from core.action.base import ActionContext
        
        idle_count = 0
        round_count = 0
        max_rounds = 20
        
        self._set_state(ConversationState.CONVERSING, {
            "conversation_id": self.total_conversations
        })
        
        while self.running and round_count < max_rounds:
            print(f"\n--- 第 {round_count + 1} 轮对话 ---")
            
            # 监听用户输入
            print(f"🎤 监听用户输入（超时 {self.idle_timeout}s）...")
            
            context = ActionContext(agent_state=None, input_data=self.idle_timeout)
            result = await self.listen_action.execute(context)
            
            if not self.running:
                break
            
            if not result.success:
                idle_count += 1
                print(f"⏱️  无语音输入 ({idle_count}/{self.max_idle_rounds})")
                
                self._set_state(ConversationState.IDLE, {
                    "idle_count": idle_count,
                    "max_idle_rounds": self.max_idle_rounds
                })
                
                if idle_count >= self.max_idle_rounds:
                    print("⏱️  超时次数过多，结束对话")
                    goodbye_msg = "好的，我先休息了，有需要再叫我"
                    self._add_message("assistant", goodbye_msg)
                    await self._speak(goodbye_msg)
                    break
                
                continue
            
            # 重置闲置计数
            idle_count = 0
            
            # 获取用户输入
            user_text = result.output.get("text", "").strip()
            print(f"👤 用户: {user_text}")
            
            if not user_text:
                continue
            
            # 添加到消息列表
            self._add_message("user", user_text)
            
            # 检查再见
            if self._is_goodbye(user_text):
                print("👋 检测到再见关键词")
                goodbye_msg = "再见，下次见！"
                self._add_message("assistant", goodbye_msg)
                await self._speak(goodbye_msg)
                break
            
            # 处理输入
            response_text = await self._handle_user_input(user_text)
            print(f"🤖 助手: {response_text}")
            
            # 添加到消息列表
            self._add_message("assistant", response_text)
            
            # 播报
            self._set_state(ConversationState.CONVERSING, {
                "user_input": user_text,
                "bot_response": response_text,
                "round": round_count + 1
            })
            
            await self._speak(response_text)
            
            round_count += 1
    
    async def _handle_user_input(self, user_text: str) -> str:
        """处理用户输入（意图分析 + MCP）"""
        # 1. 意图分析
        intent_result = await self._analyze_intent(user_text)
        
        intent_type = intent_result.get("intent_type")
        response_text = intent_result.get("response", "")
        task_info = intent_result.get("task_info")
        
        # 2. 如需 MCP 工具
        if intent_type == "task_request" and task_info:
            executor_type = task_info.get("executor_type")
            
            if executor_type == "mcp":
                mcp_result = await self._call_mcp_tool(task_info)
                
                if mcp_result.get("success"):
                    response_text = await self._generate_final_response(
                        user_text, mcp_result
                    )
                else:
                    response_text = f"抱歉，执行任务时出错了：{mcp_result.get('error', '未知错误')}"
        
        # 3. 更新历史
        self.conversation_history.append({"role": "user", "content": user_text})
        self.conversation_history.append({"role": "assistant", "content": response_text})
        
        if len(self.conversation_history) > self.max_history_length * 2:
            self.conversation_history = self.conversation_history[-self.max_history_length:]
        
        return response_text
    
    async def _analyze_intent(self, user_text: str) -> Dict[str, Any]:
        """意图分析（复用原逻辑）"""
        from config import build_analyze_prompt
        import json
        
        mcp_tools = []
        if hasattr(self.agent, 'mcp_manager') and self.agent.mcp_manager:
            all_tools = self.agent.mcp_manager.tool_index.get_all_tools()
            mcp_tools = [(tool.tool_name, tool.description) for tool in all_tools]
        
        prompt = build_analyze_prompt(
            available_actions=[("speak", "语音播报", ["tts"])],
            mcp_tools=mcp_tools
        )
        
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_text}
        ]
        
        response = await self.llm_client.chat_completion(
            messages=messages,
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        return json.loads(response)
    
    async def _call_mcp_tool(self, task_info: Dict) -> Dict[str, Any]:
        """调用 MCP 工具（复用原逻辑）"""
        params = task_info.get("parameters", {})
        user_intent = params.get("user_intent", "")
        context = params.get("context", {})
        
        mcp_task = UnifiedTask(
            task_type=TaskType.MCP_CALL,
            priority=7,
            timeout=3000.0,
            execution_data={
                "goal": user_intent,
                "user_intent": user_intent,
                "max_steps": 5
            },
            context=context
        )
        
        task_id = await self.agent.submit_task(mcp_task)
        
        max_wait = 60
        waited = 0
        
        while waited < max_wait:
            task_status = await self.agent.get_task_status(task_id)
            
            if task_status == TaskStatus.COMPLETED:
                task_detail = await self.agent.get_task_detail(task_id)
                
                if not task_detail or not task_detail.result:
                    return {"success": False, "error": "No result"}
                
                if not isinstance(task_detail.result, dict):
                    return {"success": False, "error": f"Invalid result type"}
                
                return task_detail.result
            
            elif task_status == TaskStatus.FAILED:
                task_detail = await self.agent.get_task_detail(task_id)
                error_msg = "Unknown error"
                if task_detail and task_detail.result:
                    error_msg = task_detail.result.get("error", str(task_detail.result))
                return {"success": False, "error": error_msg}
            
            await asyncio.sleep(1)
            waited += 1
        
        return {"success": False, "error": "Timeout"}
    
    async def _generate_final_response(self, user_text: str, mcp_result: Dict) -> str:
        """融合 MCP 结果生成回复"""
        
        # 👇 修复：更智能地提取工具输出
        tool_output = None
        
        # 尝试多种路径获取实际结果
        if "final_result" in mcp_result:
            tool_output = mcp_result["final_result"]
        elif "result" in mcp_result:
            tool_output = mcp_result["result"]
        elif "step_results" in mcp_result and mcp_result["step_results"]:
            # 如果有步骤结果，取最后一个
            last_step = mcp_result["step_results"][-1]
            tool_output = last_step.get("result")
        
        # 如果 tool_output 是嵌套字典，继续提取
        if isinstance(tool_output, dict):
            if "result" in tool_output:
                tool_output = tool_output["result"]
            elif "content" in tool_output:
                tool_output = tool_output["content"]
        
        # 格式化输出（处理列表、字典等）
        if isinstance(tool_output, list):
            # 如果是搜索结果列表
            if tool_output and isinstance(tool_output[0], dict):
                # 提取关键信息（如标题、摘要）
                formatted_output = []
                for i, item in enumerate(tool_output[:3], 1):  # 只取前3条
                    if "title" in item:
                        formatted_output.append(f"{i}. {item.get('title', '')} - {item.get('snippet', '')[:100]}")
                    else:
                        formatted_output.append(f"{i}. {str(item)[:100]}")
                tool_output = "\n".join(formatted_output)
            else:
                tool_output = "\n".join(str(item) for item in tool_output[:5])
        elif isinstance(tool_output, dict):
            # 如果是字典，尝试提取 query 和 results
            if "query" in tool_output and "results" in tool_output:
                results = tool_output["results"]
                if results:
                    formatted_results = []
                    for i, r in enumerate(results[:3], 1):
                        title = r.get("title", "")
                        snippet = r.get("snippet", "")
                        formatted_results.append(f"{i}. {title}\n   {snippet[:150]}")
                    tool_output = "\n\n".join(formatted_results)
                else:
                    tool_output = "未找到相关结果"
        
        system_prompt = f"""你是一个友好的智能助手。

用户问题："{user_text}"

工具返回的信息：
{tool_output}

请用简洁、自然、口语化的中文回复用户（2-3句话，总结关键信息）。
如果是新闻或搜索结果，简要概括前几条即可。"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text}
        ]
        
        response = await self.llm_client.chat_completion(
            messages=messages,
            temperature=0.7,
            max_tokens=200
        )
        
        return response
    
    async def _speak(self, text: str) -> bool:
        """语音播报"""
        result = await self.agent.execute_action("speak", input_data=text)
        return result.success
    
    def _is_goodbye(self, text: str) -> bool:
        """检查再见关键词"""
        goodbye_keywords = [
            "再见", "拜拜", "byebye", "goodbye", "886",
            "结束", "停止", "退出", "你退下吧"
        ]
        text_lower = text.lower().strip()
        return any(kw in text_lower for kw in goodbye_keywords)
    
    def _set_state(self, state: str, data: Dict = None):
        """设置状态并触发回调"""
        self.current_state = state
        
        if self.state_callback:
            self.state_callback(state, data or {})
        
        self._log(None, f"State changed: {state}")
    
    def stop(self):
        """停止监听"""
        self.running = False
        self.listening_active = False
    
    def cleanup(self):
        """清理资源"""
        self.listen_action.cleanup()
        self.conversation_history.clear()
        self.messages.clear()