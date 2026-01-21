# core/server/task_dispatcher.py
"""任务调度器

负责 Agent 层任务调度
"""

import time
import uuid
import json
import asyncio
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
import httpx

from core.server.message_router import TaskRequest
from core.action.speak_action import speak_one_time
from core.client.openai_client import OpenAIClient
import config


@dataclass
class TaskInfo:
    """任务信息存储"""
    task_id: str
    status: str
    created_at: float
    updated_at: float
    message: str
    callback_url: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    parameters: Dict[str, Any] = field(default_factory=dict)


class TaskDispatcher:
    """任务调度器
    
    专注于 Agent 层任务调度管理
    """
    
    def __init__(self, agent, communication_server=None):
        """初始化任务调度器
        
        Args:
            agent: RobotAgent 实例引用
            communication_server: CommunicationServer 实例（用于状态广播）
        """
        self.agent = agent
        self.communication_server = communication_server
        self.task_status_map: Dict[str, TaskInfo] = {}
        
        # 初始化 LLM 客户端用于用户意图分析
        self.llm_client = OpenAIClient(
            api_key=config.OPENAI_API_KEY,
            base_url=config.OPENAI_BASE_URL
        )
        
        # MCP Manager 引用（延迟初始化）
        self.mcp_manager = None
        self._mcp_tools_cache = None
        self._cache_timestamp = 0
        
        print("[TaskDispatcher] Initialized")
    
    def set_communication_server(self, communication_server):
        """设置通信服务器引用（用于双向注入）
        
        Args:
            communication_server: CommunicationServer 实例
        """
        self.communication_server = communication_server
    
    async def dispatch_task(self, task_request: TaskRequest) -> str:
        """创建并分发任务
        
        Args:
            task_request: 任务请求对象
            
        Returns:
            str: 任务 ID
        """
        # 生成任务 ID
        task_id = str(uuid.uuid4())
        
        # 导入统一任务模型
        from core.task.models import UnifiedTask, TaskType
        
        # 映射任务类型到 TaskType 枚举
        # 所有 TaskDispatcher 任务统一使用 DISPATCHER 类型
        unified_task_type = TaskType.DISPATCHER
        
        # 创建 UnifiedTask 对象
        task = UnifiedTask(
            task_id=task_id,
            task_type=unified_task_type,
            priority=getattr(task_request, 'priority', 5),
            timeout=task_request.timeout,
            context={
                "dispatcher_task_type": task_request.task_type,
                "task_name": task_request.task_name,
            },
            execution_data={
                "task_request": task_request,
                "task_id_for_callback": task_id,
            }
        )
        
        # 记录任务信息
        task_info = TaskInfo(
            task_id=task_id,
            status="pending",
            created_at=time.time(),
            updated_at=time.time(),
            message="Task created and queued",
            callback_url=task_request.callback_url,
            parameters=task_request.parameters
        )
        self.task_status_map[task_id] = task_info
        
        print(f"[TaskDispatcher] Task created: {task_id} ({task_request.task_type}:{task_request.task_name})")
        
        # 提交到统一任务队列
        await self.agent.submit_task(task)
        
        return task_id
    
    async def dispatch_user_input(self, input_data: Dict[str, Any]) -> str:
        """处理用户输入请求
        
        Args:
            input_data: 用户输入数据
            
        Returns:
            str: 任务 ID
        """
        # 将用户输入包装为任务请求
        task_request = TaskRequest(
            task_type="user_input",
            task_name=f"user_input_{input_data.get('input_type', 'unknown')}",
            parameters=input_data
        )
        
        return await self.dispatch_task(task_request)
    
    async def _execute_task_by_type(self, task_request: TaskRequest) -> Dict[str, Any]:
        """根据任务类型执行任务
        
        Args:
            task_request: 任务请求数据
            
        Returns:
            Dict[str, Any]: 执行结果
        """
        task_type = task_request.task_type
        parameters = task_request.parameters
        
        if task_type == "execute_action":
            # 执行指定的 Action
            action_name = parameters.get("action_name")
            input_data = parameters.get("input_data")
            
            if not action_name:
                raise ValueError("Missing 'action_name' in parameters")
            
            result = await self.agent.execute_action(action_name, input_data)
            return {
                "success": result.success,
                "output": result.output,
                "metadata": result.metadata
            }
        
        elif task_type == "mcp_tool":
            # 调用 MCP 工具（使用统一任务队列）
            # 参数格式：user_intent + context（由 Router 智能决策）
            
            # 确保 MCP Manager 已初始化
            await self._ensure_mcp_manager()
            
            # 检查 MCP Manager 是否成功初始化
            if self.mcp_manager is None:
                raise RuntimeError("MCP Manager initialization failed")
            
            # 检查 router 是否存在
            if not hasattr(self.mcp_manager, 'router') or self.mcp_manager.router is None:
                raise RuntimeError("MCP Manager router not initialized")
            
            # 用户意图检测
            user_intent = parameters.get("user_intent")
            context = parameters.get("context", {})
            
            if user_intent:
                # 直接使用 user_intent 作为 goal
                goal = user_intent
                
                # 合并 context 到任务上下文
                task_context = {
                    "user_intent": user_intent,
                    **context  # 展开上下文信息
                }
            else:
                raise ValueError("Missing 'user_intent' in parameters")
            
            # 创建 MCP_CALL 任务并提交到统一队列
            from core.task.models import UnifiedTask, TaskType
            
            mcp_task = UnifiedTask(
                task_type=TaskType.MCP_CALL,
                priority=5,  # 默认优先级
                timeout=300.0,  # 5分钟超时
                max_retries=3,
                context=task_context,
                execution_data={
                    "goal": goal,
                    "current_step": 0,
                    "max_steps": 10,
                    "user_intent": user_intent or goal
                }
            )
            
            # 提交到统一队列
            await self.agent.submit_task(mcp_task)
            mcp_task_id = mcp_task.task_id
            
            print(f"[TaskDispatcher] Created MCP_CALL task {mcp_task_id[:8]} with goal: {goal}")
            
            # 等待任务完成（异步轮询统一队列）
            max_wait_time = 300  # 5分钟超时
            wait_interval = 1  # 1秒轮询一次
            elapsed = 0
            
            while elapsed < max_wait_time:
                await asyncio.sleep(wait_interval)
                elapsed += wait_interval
                
                # 从统一队列查询任务详情
                task_detail = await self.agent.task_queue.get_by_id(mcp_task_id)
                if not task_detail:
                    break
                
                # 检查是否终止
                if task_detail.is_terminal():
                    from core.task.models import TaskStatus as UnifiedTaskStatus
                    
                    if task_detail.status == UnifiedTaskStatus.COMPLETED:
                        # 从历史记录中获取最后一次成功的结果
                        last_success_result = None
                        for entry in reversed(task_detail.history):
                            if entry.get("result", {}).get("success"):
                                last_success_result = entry["result"]
                                break
                        
                        return {
                            "success": True,
                            "output": last_success_result.get("content") if last_success_result else "Task completed",
                            "metadata": {
                                "task_id": mcp_task_id,
                                "steps": task_detail.execution_data.get("current_step", 0),
                                "history": task_detail.history
                            }
                        }
                    else:
                        # 任务失败
                        error_msg = "Task failed"
                        if task_detail.result:
                            error_msg = task_detail.result.get("error", error_msg)
                        
                        return {
                            "success": False,
                            "error": error_msg,
                            "metadata": {
                                "task_id": mcp_task_id,
                                "status": task_detail.status.value,
                                "history": task_detail.history
                            }
                        }
            
            # 超时
            return {
                "success": False,
                "error": "Task execution timeout",
                "metadata": {
                    "task_id": mcp_task_id,
                    "elapsed": elapsed
                }
            }
        
        elif task_type == "user_input":
            # 处理用户输入
            if parameters.get("input_type") == "text":
                user_text = parameters.get("content", "")
                return await self._process_user_text_input(user_text)
            
            return {"message": "User input processed", "parameters": parameters}
        
        else:
            # 自定义任务类型
            return {"message": f"Custom task '{task_type}' executed", "parameters": parameters}
    
    async def _process_user_text_input(self, user_text: str) -> Dict[str, Any]:
        """处理用户文本输入
        
        Args:
            user_text: 用户输入的文本
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        # 分析用户意图
        intent_result = await self._analyze_user_intent(user_text)
        intent_type = intent_result["intent_type"]
        
        # 根据意图类型分发处理
        if intent_type == "simple_chat":
            return await self._handle_simple_chat(intent_result)
        elif intent_type == "task_request":
            return await self._handle_task_request(intent_result)
        else:
            return await self._handle_unknown_intent()
    
    async def _handle_simple_chat(self, intent_result: Dict[str, Any]) -> Dict[str, Any]:
        """处理简单对话
        
        Args:
            intent_result: 意图分析结果
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        response_text = intent_result.get("response", "好的，我明白了")
        await speak_one_time(response_text)
        
        return {
            "message": "Simple chat processed",
            "intent_type": "simple_chat",
            "response": response_text
        }
    
    async def _handle_task_request(self, intent_result: Dict[str, Any]) -> Dict[str, Any]:
        """处理任务请求
        
        Args:
            intent_result: 意图分析结果
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        task_info = intent_result.get("task_info", {})
        
        # 语音确认
        confirmation = intent_result.get("response", "好的，我来处理")
        await speak_one_time(confirmation)
        
        # 创建并分发新任务
        new_task_id = await self._create_task_from_intent(task_info)
        
        return {
            "message": "Task created from user input",
            "intent_type": "task_request",
            "new_task_id": new_task_id,
            "task_info": task_info
        }
    
    async def _handle_unknown_intent(self) -> Dict[str, Any]:
        """处理未知意图
        
        Returns:
            Dict[str, Any]: 处理结果
        """
        await speak_one_time("抱歉，我不太明白您的意思")
        return {
            "message": "Unknown intent",
            "intent_type": "unknown"
        }
    
    async def _ensure_mcp_manager(self) -> None:
        """确保 MCP Manager 已初始化并可用
        
        获取策略：
        1. 优先从 Agent 的 alert Action 中获取已初始化的 MCP Manager（单例复用）
        2. 如果 alert Action 未注册或 MCP Manager 未初始化，则独立创建
        3. 记录 mcp_manager 引用，避免重复获取
        """
        if self.mcp_manager is not None:
            return  # 已初始化
        
        # todo: 这里的写法有点奇怪，mcp_manager不应该从AlertAction获取
        # 尝试从 AlertAction 复用
        if self.agent and hasattr(self.agent, 'actions'):
            alert_action = self.agent.actions.get('alert')
            if alert_action and hasattr(alert_action, 'mcp_manager'):
                if alert_action.mcp_manager is not None:
                    print("[TaskDispatcher] Reusing MCP Manager from AlertAction")
                    self.mcp_manager = alert_action.mcp_manager
                    return
        
        # 独立初始化
        try:
            print("[TaskDispatcher] Initializing MCP Manager independently...")
            from core.mcp_control.manager import McpManager
            
            mcp_config_path = config.MCP_CONFIG_PATH
            
            # 创建 MCP Manager（单例模式自动返回同一实例）
            self.mcp_manager = McpManager()
            await self.mcp_manager.initialize(mcp_config_path, self.llm_client, agent=self.agent)
            
            print("[TaskDispatcher] MCP Manager initialized successfully")
        except Exception as e:
            print(f"[TaskDispatcher] Failed to initialize MCP Manager: {e}")
            # 不抛出异常，允许降级为仅 Action 模式
            self.mcp_manager = None
    
    async def _get_mcp_tools_cached(self) -> list:
        """获取 MCP 工具列表（带缓存）
        
        仅返回工具名称和描述，不包含 schema。
        这样可以减少意图分析阶段的 token 消耗。
        
        Returns:
            list: MCP 工具列表，格式为 [(tool_name, description), ...]
        """
        import time
        
        # 检查缓存是否有效（60秒）
        cache_ttl = 60
        current_time = time.time()
        
        if self._mcp_tools_cache is not None and (current_time - self._cache_timestamp) < cache_ttl:
            return self._mcp_tools_cache
        
        # 缓存过期或不存在，重新获取
        mcp_tools = []
        
        try:
            # 确保 MCP Manager 已初始化
            await self._ensure_mcp_manager()
            
            if self.mcp_manager and hasattr(self.mcp_manager, 'tool_index'):
                tool_index = self.mcp_manager.tool_index
                all_tools = tool_index.get_all_tools()
                
                for tool in all_tools:
                    # 仅获取工具名称和描述，不包含 schema
                    mcp_tools.append((tool.tool_name, tool.description))
                
                print(f"[TaskDispatcher] Loaded {len(mcp_tools)} MCP tools (name + description only)")
        except Exception as e:
            print(f"[TaskDispatcher] Failed to get MCP tools: {e}")
            mcp_tools = []
        
        # 更新缓存
        self._mcp_tools_cache = mcp_tools
        self._cache_timestamp = current_time
        
        return mcp_tools
    
    def _infer_goal_from_tool(self, tool_name: str, tool_arguments: Dict[str, Any]) -> str:
        """根据工具名称和参数推断任务目标
        
        Args:
            tool_name: 工具名称
            tool_arguments: 工具参数
            
        Returns:
            str: 推断出的任务目标描述
        """
        # 尝试从工具索引中获取工具的实际描述
        tool_description = None
        if self.mcp_manager and hasattr(self.mcp_manager, 'tool_index'):
            tool_index = self.mcp_manager.tool_index
            tools = tool_index.get_all_tools()
            for tool in tools:
                if tool.tool_name == tool_name:
                    tool_description = tool.description
                    break
        
        # 提取参数中的关键信息
        target_info = self._extract_target_info_from_arguments(tool_arguments)
        
        # 构建目标描述
        if tool_description:
            # 使用工具的实际描述作为基础
            if target_info:
                return f"{tool_description}: {target_info}"
            else:
                return tool_description
        else:
            # 降级方案: 根据工具名称和参数智能推断
            return self._fallback_infer_goal(tool_name, tool_arguments, target_info)
    
    def _extract_target_info_from_arguments(self, arguments: Dict[str, Any]) -> str:
        """从参数中提取目标信息（通用方法）
        
        Args:
            arguments: 工具参数
            
        Returns:
            str: 提取的目标信息字符串
        """
        if not arguments:
            return ""
        
        # 尝试提取最有意义的参数值
        # 优先提取常见的标识符参数
        identifier_keys = ["name", "id", "entity_id", "target", "subject", "title"]
        for key in identifier_keys:
            if key in arguments and arguments[key]:
                main_value = str(arguments[key])
                
                # 收集其他有意义的参数作为补充信息
                extra_params = []
                for param_key, param_value in arguments.items():
                    if param_key != key and param_value is not None:
                        # 过滤掉一些通用的元数据参数
                        if param_key not in ["domain", "type", "class", "metadata"]:
                            extra_params.append(f"{param_key}: {param_value}")
                
                # 如果有额外参数,附加显示
                if extra_params:
                    return f"{main_value} ({', '.join(extra_params[:2])})"  # 最多显示2个额外参数
                else:
                    return main_value
        
        # 如果没有标识符参数,尝试组合所有非空参数
        meaningful_params = []
        for key, value in arguments.items():
            if value is not None and key not in ["type", "class", "metadata"]:
                meaningful_params.append(f"{key}: {value}")
        
        if meaningful_params:
            return ", ".join(meaningful_params[:3])  # 最多显示3个参数
        
        return ""
    
    def _fallback_infer_goal(self, tool_name: str, tool_arguments: Dict[str, Any], target_info: str) -> str:
        """降级方案: 根据工具名称模式推断目标（通用语义分析）
        
        Args:
            tool_name: 工具名称
            tool_arguments: 工具参数
            target_info: 已提取的目标信息
            
        Returns:
            str: 推断的目标描述
        """
        # 通用动作词识别（支持多种命名风格）
        name_lower = tool_name.lower()
        
        # CRUD 操作
        if any(word in name_lower for word in ["create", "add", "new", "insert"]):
            action = "创建"
        elif any(word in name_lower for word in ["get", "read", "list", "query", "find", "search", "fetch", "retrieve"]):
            action = "查询"
        elif any(word in name_lower for word in ["update", "modify", "edit", "change", "set"]):
            action = "更新"
        elif any(word in name_lower for word in ["delete", "remove", "drop"]):
            action = "删除"
        
        # 控制操作
        elif any(word in name_lower for word in ["start", "begin", "launch", "run", "execute"]):
            action = "启动"
        elif any(word in name_lower for word in ["stop", "end", "terminate", "halt"]):
            action = "停止"
        elif any(word in name_lower for word in ["enable", "activate", "turnon", "turn_on", "open"]):
            action = "启用"
        elif any(word in name_lower for word in ["disable", "deactivate", "turnoff", "turn_off", "close"]):
            action = "禁用"
        
        # 通信操作
        elif any(word in name_lower for word in ["send", "post", "publish", "notify"]):
            action = "发送"
        elif any(word in name_lower for word in ["receive", "subscribe"]):
            action = "接收"
        
        # 其他常见操作
        elif any(word in name_lower for word in ["upload", "push"]):
            action = "上传"
        elif any(word in name_lower for word in ["download", "pull"]):
            action = "下载"
        elif any(word in name_lower for word in ["sync", "synchronize"]):
            action = "同步"
        elif any(word in name_lower for word in ["validate", "verify", "check"]):
            action = "验证"
        elif any(word in name_lower for word in ["process", "handle"]):
            action = "处理"
        else:
            # 默认使用工具名称本身
            action = f"执行 {tool_name}"
        
        # 组合动作和目标
        if target_info:
            goal = f"{action} {target_info}"
        else:
            goal = action
        
        # 如果是需要目标的操作但缺少目标信息,添加提示
        needs_target = any(word in name_lower for word in [
            "turn", "set", "control", "send", "update", "delete", "enable", "disable"
        ])
        if not target_info and needs_target:
            goal += ",需要先查询可用资源,然后执行操作"
        
        return goal
    
    async def _create_task_from_intent(self, task_info: Dict[str, Any]) -> str:
        """从意图信息创建任务（支持执行器选择模式）
        
        Args:
            task_info: 任务信息字典
                - executor_type: "action" 或 "mcp"
                - task_name: 任务简短名称
                - parameters: 参数字典
            
        Returns:
            str: 新创建的任务 ID
        """
        executor_type = task_info.get("executor_type")
        parameters = task_info.get("parameters", {})
        
        # 根据执行器类型映射到旧的 task_type（保持向后兼容）
        if executor_type == "action":
            task_type = "execute_action"
        elif executor_type == "mcp":
            # MCP 执行器：使用新的智能决策模式
            task_type = "mcp_tool"
            # 确保参数中包含 user_intent 和 context
            if "user_intent" not in parameters:
                # 兼容旧格式：如果没有 user_intent，尝试从 task_name 推断
                parameters["user_intent"] = task_info.get("task_name", "用户请求")
            if "context" not in parameters:
                parameters["context"] = {}
        else:
            # 兼容旧格式：task_type 字段
            task_type = task_info.get("task_type", "execute_action")
        
        task_request = TaskRequest(
            task_type=task_type,
            task_name=task_info.get("task_name", "user_requested_task"),
            parameters=parameters
        )
        
        return await self.dispatch_task(task_request)
    
    async def _analyze_user_intent(self, user_text: str) -> Dict[str, Any]:
        """分析用户意图
        
        Args:
            user_text: 用户输入的文本
            
        Returns:
            Dict[str, Any]: 意图分析结果
                - intent_type: "simple_chat" | "task_request" | "unknown"
                - response: 给用户的回复文本
                - task_info: 如果是 task_request，包含任务信息
        """
        try:
            # 动态构建 Prompt，包含当前可用的 Actions 和 MCP 工具
            available_actions = []
            if self.agent and hasattr(self.agent, 'action_metadata'):
                for action_name, metadata in self.agent.action_metadata.items():
                    available_actions.append((
                        action_name,
                        metadata.description,
                        metadata.capabilities
                    ))
            
            # 获取 MCP 工具列表（带缓存）
            mcp_tools = await self._get_mcp_tools_cached()
            
            # 构建动态 Prompt
            analyze_prompt = config.build_analyze_prompt(
                available_actions=available_actions if available_actions else None,
                mcp_tools=mcp_tools if mcp_tools else None,
                include_tool_schemas=False  # 默认不包含 schema，保持 Prompt 简洁
            )
            
            # 注入分析系统提示词
            messages = [
                {"role": "system", "content": analyze_prompt},
                {"role": "user", "content": user_text}
            ]
            
            # 调用 LLM 分析
            response_text = await self.llm_client.chat_completion(
                messages=messages,
                temperature=0.3,  # 较低温度，保证结果稳定
                max_tokens=500
            )
            
            print(f"[TaskDispatcher] LLM intent analysis result: {response_text}")
            
            # 解析 JSON 结果
            try:
                # 尝试直接解析
                intent_result = json.loads(response_text)
            except json.JSONDecodeError:
                # 如果有 markdown 代码块，提取其中的 JSON
                if "```json" in response_text:
                    json_start = response_text.find("```json") + 7
                    json_end = response_text.find("```", json_start)
                    json_str = response_text[json_start:json_end].strip()
                    intent_result = json.loads(json_str)
                elif "```" in response_text:
                    json_start = response_text.find("```") + 3
                    json_end = response_text.find("```", json_start)
                    json_str = response_text[json_start:json_end].strip()
                    intent_result = json.loads(json_str)
                else:
                    # 无法解析，返回默认结果
                    print(f"[TaskDispatcher] Failed to parse LLM response, treating as simple chat")
                    intent_result = {
                        "intent_type": "simple_chat",
                        "response": response_text[:100]  # 截取前100个字符作为回复
                    }
            
            # 验证必要字段
            if "intent_type" not in intent_result:
                intent_result["intent_type"] = "simple_chat"
            if "response" not in intent_result:
                intent_result["response"] = "收到您的消息了"
            
            return intent_result
            
        except Exception as e:
            print(f"[TaskDispatcher] Error in intent analysis: {e}")
            # 出错时默认为简单对话
            return {
                "intent_type": "simple_chat",
                "response": f"收到您的消息：{user_text}"
            }
    
    def get_task_status(self, task_id: str) -> Optional[TaskInfo]:
        """查询任务状态
        
        Args:
            task_id: 任务 ID
            
        Returns:
            TaskInfo: 任务状态信息，不存在返回 None
        """
        return self.task_status_map.get(task_id)
    
    def list_tasks(self, limit: int = 50) -> List[TaskInfo]:
        """获取任务列表
        
        Args:
            limit: 返回数量限制
            
        Returns:
            List[TaskInfo]: 任务列表
        """
        return list(self.task_status_map.values())[:limit]
    
    async def on_task_complete(self, task_id: str, result: Dict[str, Any]) -> None:
        """任务完成回调
        
        Args:
            task_id: 任务 ID
            result: 执行结果
        """
        if task_id not in self.task_status_map:
            return
        
        task_info = self.task_status_map[task_id]
        
        # 发送回调通知
        if task_info.callback_url:
            await self._send_callback_notification(task_info.callback_url, task_id, result, True)
        
        # 广播状态更新
        await self._broadcast_task_status(task_id, task_info)
    
    async def on_task_failed(self, task_id: str, error: Dict[str, Any]) -> None:
        """任务失败回调
        
        Args:
            task_id: 任务 ID
            error: 错误信息
        """
        if task_id not in self.task_status_map:
            return
        
        task_info = self.task_status_map[task_id]
        
        # 发送回调通知
        if task_info.callback_url:
            await self._send_callback_notification(task_info.callback_url, task_id, error, False)
        
        # 广播状态更新
        await self._broadcast_task_status(task_id, task_info)
    
    async def _send_callback_notification(self, callback_url: str, task_id: str, result: Dict[str, Any], success: bool) -> None:
        """发送回调通知
        
        Args:
            callback_url: 回调 URL
            task_id: 任务 ID
            result: 执行结果
            success: 是否成功
        """
        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "task_id": task_id,
                    "success": success,
                    "result": result,
                    "timestamp": time.time()
                }
                response = await client.post(callback_url, json=payload, timeout=5.0)
                print(f"[TaskDispatcher] Callback sent to {callback_url}: {response.status_code}")
        except Exception as e:
            print(f"[TaskDispatcher] Failed to send callback to {callback_url}: {e}")
    
    async def _broadcast_task_status(self, task_id: str, task_info: TaskInfo) -> None:
        """通过 WebSocket 广播任务状态
        
        Args:
            task_id: 任务 ID
            task_info: 任务信息
        """
        if not self.communication_server:
            return
        
        message = {
            "message_type": "status",
            "from_agent": "task_dispatcher",
            "to_agent": None,
            "message_id": str(uuid.uuid4()),
            "timestamp": time.time(),
            "payload": {
                "task_id": task_id,
                "status": task_info.status,
                "message": task_info.message,
                "result": task_info.result
            }
        }
        
        # 通过 CommunicationServer 广播
        if hasattr(self.communication_server, 'broadcast_message'):
            await self.communication_server.broadcast_message(message)
