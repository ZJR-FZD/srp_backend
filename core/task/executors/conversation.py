# core/task/executors/conversation.py
"""ConversationExecutor - 智能对话任务执行器"""

from typing import TYPE_CHECKING, Dict, Any
from core.task.executors.base import BaseTaskExecutor
from core.task.models import UnifiedTask, TaskStatus, TaskType
import asyncio

if TYPE_CHECKING:
    from core.agent import RobotAgent


class ConversationExecutor(BaseTaskExecutor):
    """智能对话执行器
    
    流程：
    1. 接收用户语音文本
    2. 意图分析（是否需要 MCP 工具？）
    3. 如需工具 → 创建 MCP_CALL 任务并等待
    4. LLM 生成回复
    5. 语音播报
    """
    
    def __init__(self, agent: 'RobotAgent', llm_client):
        super().__init__()
        self.agent = agent
        self.llm_client = llm_client
        self.conversation_history = []
        self.max_history_length = 10
    
    async def validate(self, task: UnifiedTask) -> bool:
        if not await super().validate(task):
            return False
        
        user_text = task.execution_data.get("user_text")
        if not user_text:
            self._log(task, "No user_text provided", "ERROR")
            return False
        
        return True
    
    async def execute(self, task: UnifiedTask) -> None:
        """执行对话任务"""
        try:
            if not await self.validate(task):
                task.transition_to(TaskStatus.FAILED, "Validation failed")
                return
            
            user_text = task.execution_data.get("user_text")
            self._log(task, f"User: {user_text}")
            
            # 1. 意图分析
            intent_result = await self._analyze_intent(user_text)
            
            intent_type = intent_result.get("intent_type")
            response_text = intent_result.get("response", "")
            task_info = intent_result.get("task_info")
            
            # 2. 判断是否需要 MCP 工具
            if intent_type == "task_request" and task_info:
                executor_type = task_info.get("executor_type")
                
                if executor_type == "mcp":
                    self._log(task, "Calling MCP tool...")
                    
                    # 创建 MCP 任务并等待
                    mcp_result = await self._call_mcp_tool(task_info)
                    
                    if mcp_result.get("success"):
                        # 融合 MCP 结果生成回复
                        response_text = await self._generate_final_response(
                            user_text, 
                            mcp_result
                        )
                    else:
                        response_text = f"抱歉，执行任务时出错了：{mcp_result.get('error', '未知错误')}"
            
            # 3. 语音播报
            self._log(task, f"Bot: {response_text}")
            await self._speak(response_text)
            
            # 4. 更新对话历史
            self.conversation_history.append({"role": "user", "content": user_text})
            self.conversation_history.append({"role": "assistant", "content": response_text})
            
            if len(self.conversation_history) > self.max_history_length * 2:
                self.conversation_history = self.conversation_history[-self.max_history_length:]
            
            # 5. 任务完成
            task.result = {
                "success": True,
                "user_input": user_text,
                "bot_response": response_text,
                "used_mcp": executor_type == "mcp" if task_info else False
            }
            
            task.transition_to(TaskStatus.COMPLETED, "Conversation completed")
            
        except Exception as e:
            await self.handle_error(task, e)
    
    async def _analyze_intent(self, user_text: str) -> Dict[str, Any]:
        """意图分析"""
        from config import build_analyze_prompt
        
        # 获取 MCP 工具列表
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
        
        import json
        return json.loads(response)

    async def _call_mcp_tool(self, task_info: Dict) -> Dict[str, Any]:
        """调用 MCP 工具"""
        params = task_info.get("parameters", {})
        user_intent = params.get("user_intent", "")
        context = params.get("context", {})
        
        # 创建 MCP 任务
        mcp_task = UnifiedTask(
            task_type=TaskType.MCP_CALL,
            priority=7,
            timeout=60.0,
            execution_data={
                "goal": user_intent,
                "user_intent": user_intent,
                "max_steps": 5
            },
            context=context
        )
        
        # 提交并等待
        task_id = await self.agent.submit_task(mcp_task)
        
        max_wait = 60
        waited = 0
        
        while waited < max_wait:
            task_status = await self.agent.get_task_status(task_id)
            
            if task_status == TaskStatus.COMPLETED:
                task_detail = await self.agent.get_task_detail(task_id)
                
                # 👇 修复：防御性处理 result 为 None 的情况
                if not task_detail:
                    return {"success": False, "error": "Task detail not found"}
                
                if not task_detail.result:
                    return {"success": False, "error": "Task completed but no result"}
                
                # 👇 修复：确保 result 是字典
                if not isinstance(task_detail.result, dict):
                    return {
                        "success": False, 
                        "error": f"Invalid result type: {type(task_detail.result)}"
                    }
                
                return task_detail.result
            
            elif task_status == TaskStatus.FAILED:
                task_detail = await self.agent.get_task_detail(task_id)
                
                # 👇 修复：安全获取错误信息
                error_msg = "Unknown error"
                if task_detail and task_detail.result:
                    if isinstance(task_detail.result, dict):
                        error_msg = task_detail.result.get("error", "Unknown error")
                    else:
                        error_msg = str(task_detail.result)
                
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
        """播报语音"""
        result = await self.agent.execute_action("speak", input_data=text)
        return result.success