import json
from typing import TypedDict, Dict, Any, List, Optional
from dataclasses import dataclass

from core.mcp_control.protocols import LLMClientProtocol
from core.mcp_control.tool_index import ToolIndex, ToolIndexEntry
from util.decoder import json_safe_encoder

ROUTER_SYSTEM_PROMPT = """
You are a routing engine that selects the most appropriate tool for a given task.

Your task is to analyze the task goal and environment, then call exactly ONE tool from the available tool list.

Rules:
- ALWAYS use the function calling mechanism to invoke a tool.
- Only select tools from the provided tool list.
- Do NOT invent tools or arguments.
- If no suitable tool is available or the task is already complete, explain why in a text response instead of calling a tool.

**Parameter Mapping**:
- When calling a tool, you MUST map parameters from the Environment section to the tool's input schema.
- The Environment contains all available data for this task (e.g., "to", "content", "subject", etc.).
- Use these values directly as tool arguments. Do NOT ignore or omit them.
- Example: If Environment has {"to": "user@example.com", "content": "Hello"}, 
  and tool send_email requires {"to": array, "subject": string, "body": string},
  then map: {"to": ["user@example.com"], "subject": "Notification", "body": "Hello"}.

**Home Automation Device Mapping** (for Home Assistant tools):
- When the task goal includes device information (entity_id, friendly_name, area), use this information to select the correct device.
- The Environment may contain a list of available devices with their entity_ids, friendly names, areas, and current states.
- You MUST map user-friendly device names (e.g., "客厅主灯") to actual entity_ids (e.g., "light.living_room_main").
- If you don't know the floor then don't pass the floor parameter.
- When multiple devices match, select the most relevant one based on:
  1. Area/location match
  2. Friendly name similarity
  3. Current state (if relevant to the operation)
- Always use entity_id as the parameter value, not friendly names.
- For cover devices (curtains, blinds, shades): position value ranges from 0-100, where 100 means fully open and 0 means fully closed.
- Example: If user says "打开客厅的灯" and environment shows:
  - light.living_room_main (客厅主灯, 区域:客厅, 状态:off)
  - light.living_room_spot (客厅射灯, 区域:客厅, 状态:off)
  Then call HassTurnOn with {"entity_id": "light.living_room_main"} (or both if user said "all lights").

**Important**:
- Use the function calling feature to invoke the selected tool.
- Do not output JSON text manually - let the tool calling mechanism handle it.
- For home automation tasks, ensure you use the actual entity_id from the device list, not user-provided names.
"""


class RouterContext(TypedDict, total=False):
    """路由上下文"""
    goal: str
    current_step: int
    history: List[Dict]
    environment: Dict[str, Any]


@dataclass
class RouterDecision:
    """路由决策结果"""
    server_id: Optional[str]
    tool: Optional[str]
    arguments: Dict[str, Any]
    confidence: float
    reasoning: str = ""


class McpRouter:
    """MCP Router - 工具路由决策引擎
    
    基于 LLM 进行工具选择决策。
    """
    
    def __init__(self, llm_client: LLMClientProtocol, tool_index: ToolIndex):
        """初始化 Router
        
        Args:
            llm_client: LLM 客户端实例(符合 LLMClientProtocol 协议)
            tool_index: 工具索引实例
        """
        self.llm = llm_client
        self.tool_index = tool_index
        print("[McpRouter] Initialized")
    
    def _build_tools_for_llm(self, tools: List[ToolIndexEntry]) -> List[Dict[str, Any]]:
        """构建 LLM function calling 格式的工具定义
        
        Args:
            tools: 工具索引条目列表
            
        Returns:
            List[Dict[str, Any]]: LLM 工具定义列表
        """
        llm_tools = []
        for tool in tools:
            llm_tools.append({
                "type": "function",
                "function": {
                    "name": tool.tool_name,
                    "description": tool.description,
                    "parameters": tool.input_schema
                }
            })
        return llm_tools
    
    def _build_context_prompt(self, context: RouterContext) -> str:
        """构建上下文提示词
        
        Args:
            context: 路由上下文
            
        Returns:
            str: 上下文描述
        """
        prompt_parts = []
        
        prompt_parts.append(f"Task goal: {context.get('goal', 'unknown')}")
        
        if 'current_step' in context:
            prompt_parts.append(f"Current step: {context['current_step']}")
        
        if 'history' in context and context['history']:
            history_str = "Previous actions:\n"
            for entry in context['history'][-3:]:  # 只显示最近3条
                history_str += f"- {entry.get('tool', 'unknown')}: {entry.get('result', {}).get('success', 'unknown')}\n"
            prompt_parts.append(history_str)
        
        if 'environment' in context:
            env_data = context['environment']
            if isinstance(env_data, dict) and env_data:
                # 将 environment 展开为更清晰的格式
                env_str = "Environment (available data for tool parameters):\n"
                for key, value in env_data.items():
                    # 格式化值，保持可读性
                    if isinstance(value, str):
                        env_str += f"  - {key}: \"{value}\"\n"
                    else:
                        env_str += f"  - {key}: {json.dumps(value, default=json_safe_encoder, ensure_ascii=False)}\n"
                prompt_parts.append(env_str)
            else:
                # 如果不是字典或为空，使用原来的 JSON 格式
                env_str = f"Environment: {json.dumps(env_data)}"
                prompt_parts.append(env_str)
        
        return "\n".join(prompt_parts)
    
    async def route(self, context: RouterContext) -> RouterDecision:
        """执行路由决策
        
        Args:
            context: 路由上下文
            
        Returns:
            RouterDecision: 决策结果
        """
        try:
            print(f"[McpRouter] Routing for goal: {context.get('goal', 'unknown')}")
            
            # 从 Tool Index 获取所有工具
            all_tools = self.tool_index.get_all_tools()
            
            if not all_tools:
                print("[McpRouter] No tools available in index")
                return RouterDecision(
                    server_id=None,
                    tool=None,
                    arguments={},
                    confidence=0.0,
                    reasoning="No tools available"
                )
            
            # 构建 LLM 工具定义
            llm_tools = self._build_tools_for_llm(all_tools)
            
            # 构建提示词
            context_prompt = self._build_context_prompt(context)
            
            messages = [
                {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
                {"role": "user", "content": context_prompt}
            ]
            
            # 调用 LLM function calling
            print(f"[McpRouter] Calling LLM with {len(llm_tools)} tools")
            response = await self.llm.function_call_completion(
                messages=messages,
                tools=llm_tools
            )
            
            # 解析 LLM 返回
            if not hasattr(response, 'tool_calls') or not response.tool_calls:
                # LLM 没有调用工具,可能认为任务已完成或无合适工具
                reasoning = response.content if hasattr(response, 'content') and response.content else "LLM did not select any tool"
                print(f"[McpRouter] No tool_calls in LLM response. Reasoning: {reasoning}")
                return RouterDecision(
                    server_id=None,
                    tool=None,
                    arguments={},
                    confidence=0.3,  # 较低置信度,表示未找到合适工具
                    reasoning=reasoning
                )
            
            # 提取第一个工具调用
            tool_call = response.tool_calls[0]
            tool_name = tool_call.function.name
            
            try:
                arguments = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                arguments = {}
            
            # 从 Tool Index 查找 server_id
            server_id = self.tool_index.get_server_by_tool(tool_name)
            
            if not server_id:
                print(f"[McpRouter] Tool {tool_name} not found in index")
                return RouterDecision(
                    server_id=None,
                    tool=None,
                    arguments={},
                    confidence=0.0,
                    reasoning=f"Tool {tool_name} not in index"
                )
            
            # 默认置信度为 0.8（因为 LLM 选择了工具）
            confidence = 0.8
            
            print(f"[McpRouter] Decision: tool={tool_name}, server={server_id}, confidence={confidence}")
            
            return RouterDecision(
                server_id=server_id,
                tool=tool_name,
                arguments=arguments,
                confidence=confidence,
                reasoning=f"Selected {tool_name} from {server_id}"
            )
            
        except Exception as e:
            print(f"[McpRouter] Routing error: {e}")
            return RouterDecision(
                server_id=None,
                tool=None,
                arguments={},
                confidence=0.0,
                reasoning=f"Routing error: {str(e)}"
            )
    
