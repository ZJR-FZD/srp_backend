# 硬件配置
VIDEO_DEV="/dev/video0"

# OpenAI API 配置
import os

OPENAI_API_KEY = "sk-f2466b8bdfa848c69051054f184939f6"
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "sk-f2466b8bdfa848c69051054f184939f6")
DASHSCOPE_INTL_API_KEY = os.getenv("DASHSCOPE_INTL_API_KEY", "sk-f2466b8bdfa848c69051054f184939f6")
DASHSCOPE_BASE_URL = os.getenv("DASHSCOPE_BASE_URL","https://dashscope.aliyuncs.com/api/v1")

# 模型配置
QWEN_MAX_MODEL = "qwen-max"  # 任务决策推理模型
QWEN_VL_MODEL = "qwen-vl-plus"  # 视觉理解模型
QWEN_OMNI_MODEL = "qwen-omni-flash"  # 多模态交互模型
QWEN_TTS_FLASH = "qwen3-tts-flash" # TTS 模型

# Agent 配置
PATROL_INTERVAL = 30.0  # 巡逻间隔（秒）
ACTION_TIMEOUT = 10.0  # Action 默认超时（秒）

# 统一任务循环配置
TASK_LOOP_INTERVAL = 1.0  # 主循环检查间隔（秒）
MAX_CONCURRENT_TASKS = 5  # 最大并发任务数
TASK_DEFAULT_TIMEOUT = 60.0  # 默认任务超时时间（秒）
TASK_DEFAULT_RETRIES = 3  # 默认最大重试次数

# 巡逻任务配置
PATROL_ENABLED = True  # 是否启用巡逻任务
PATROL_PRIORITY = 3  # 巡逻任务优先级
PATROL_EMERGENCY_THRESHOLD = 0.8  # 紧急情况置信度阈值

# MCP任务配置
MCP_TASK_MAX_STEPS = 10  # MCP任务最大执行步数
MCP_TASK_PRIORITY = 5  # MCP任务默认优先级
MCP_TASK_TIMEOUT = 120.0  # MCP任务超时时间（秒）
MCP_DECISION_CONFIDENCE_THRESHOLD = 0.6  # 决策置信度阈值

# 通信模块配置
COMMUNICATION_HOST = os.getenv("COMMUNICATION_HOST", "0.0.0.0")  # 通信服务器监听地址
COMMUNICATION_PORT = int(os.getenv("COMMUNICATION_PORT", "8080"))  # 通信服务器端口
COMMUNICATION_API_KEY = os.getenv("COMMUNICATION_API_KEY", "robot-agent-default-key")  # API 认证密钥
AGENT_ID = os.getenv("AGENT_ID", "robot-agent-default")  # 智能体唯一标识
ENABLE_CORS = os.getenv("ENABLE_CORS", "true").lower() == "true"  # 是否启用 CORS
MAX_WEBSOCKET_CONNECTIONS = int(os.getenv("MAX_WEBSOCKET_CONNECTIONS", "100"))  # 最大 WebSocket 连接数
MESSAGE_SIZE_LIMIT = int(os.getenv("MESSAGE_SIZE_LIMIT", "1048576"))  # 消息大小限制（字节，默认1MB）
CONNECTION_TIMEOUT = int(os.getenv("CONNECTION_TIMEOUT", "300"))  # 连接超时时间（秒）

# MCP 工具调用配置
MCP_TOOL_TIMEOUT = int(os.getenv("MCP_TOOL_TIMEOUT", "30"))  # MCP 工具单次调用超时时间（秒）
MCP_TOOL_RETRY_COUNT = int(os.getenv("MCP_TOOL_RETRY_COUNT", "2"))  # 工具调用失败重试次数
MCP_CONFIG_PATH = os.getenv("MCP_CONFIG_PATH", "core/mcp_control/mcp_server.json")  # MCP Server 配置文件路径

# Prompt 配置
def build_analyze_prompt(available_actions: list = None, mcp_tools: list = None, include_tool_schemas: bool = False) -> str:
    """构建动态意图分析 Prompt（执行器选择模式）
    
    Args:
        available_actions: 可用的 Action 列表，格式为 [(name, description, capabilities), ...]
        mcp_tools: 可用的 MCP 工具列表，格式为 [(tool_name, description), ...]
                   注意：仅包含名称和描述，不包含 schema
        include_tool_schemas: 已废弃参数，保留仅为向后兼容
    
    Returns:
        str: 完整的分析 Prompt
    """
    # 默认 Actions
    if available_actions is None:
        available_actions = [
            ("watch", "图像理解，用于巡检期间的环境分析", ["vision", "object_detection", "emergency_detection"]),
            ("speak", "语音播报，将文本转为语音输出", ["tts", "audio_output"]),
            ("alert", "应急响应，处理需要多轮决策和推理的复杂紧急情况", ["emergency_call", "multi_step_reasoning"])
        ]
    
    # 构建 Actions 描述
    actions_desc = ["【执行器一：内置 Actions】"]
    for name, desc, capabilities in available_actions:
        cap_str = ", ".join(capabilities)
        actions_desc.append(f"  - **{name}**: {desc} (能力: {cap_str})")
    
    actions_text = "\n".join(actions_desc)
    
    # 构建 MCP 工具服务类型描述（只显示工具名称，不含详细schema）
    mcp_text = ""
    if mcp_tools:
        mcp_desc = ["\n【执行器二：MCP 工具服务（智能决策引擎）】"]
        mcp_desc.append("  MCP工具服务包含以下能力：")
        for tool_info in mcp_tools:
            if len(tool_info) >= 2:
                tool_name, tool_desc = tool_info[0], tool_info[1]
                # 只显示工具名称和描述，不包含参数信息
                mcp_desc.append(f"  - **{tool_name}**: {tool_desc}")
        mcp_desc.append("  注：具体的工具参数将由智能决策引擎自动推理和填充")
        mcp_text = "\n".join(mcp_desc)
    
    return f"""你是一个巡检机器人的意图分析引擎。

你的任务是判断用户输入是：
1. **simple_chat**: 简单的问候、闲聊或一般对话（例如："你好"、"谢谢"、"今天天气怎么样"）
2. **task_request**: 需要执行具体任务（例如："帮我巡逻一下"、"看看周围有什么异常"、"拍张照片"、"打开客厅的灯"、"发送紧急邮件"）

**当前机器人可用的执行器分为两类**：

{actions_text}{mcp_text}

**执行器选择规则**：
1. **action 执行器**: 执行内置 Action
   - 适用场景：
     - watch: 拍照并分析环境
     - speak: 语音播报内容
     - alert: 处理需要多轮决策和推理的复杂紧急情况
   - 需要指定：action_name 和 input_data

2. **mcp 执行器**: 调用 MCP 工具服务（智能决策模式）
   - 适用场景：用户明确要求调用外部服务（如"打开灯"、"发送邮件"、"查询天气"）
   - 只需提供：
     - user_intent: 用户意图的自然语言描述
     - context: 从用户输入中提取的关键上下文信息（如位置、目标、动作等）
   - **注意**：不需要选择具体工具名称和参数，这些将由MCP智能决策引擎根据用户意图自动推理

**输出格式**：
```json
{{
  "intent_type": "simple_chat" 或 "task_request",
  "response": "给用户的回复文本",
  "task_info": {{
    "executor_type": "action" 或 "mcp",
    "task_name": "任务简短名称",
    "parameters": {{
      // 对于 action 执行器:
      "action_name": "watch" | "speak" | "alert",
      "input_data": {{
        "text": "要播报的文本（针对speak）",
        "content": "事件描述（针对alert）"
      }}
      // 对于 mcp 执行器:
      "user_intent": "用户意图的自然语言描述",
      "context": {{
        "location": "提取的位置信息（如有）",
        "target": "操作目标（如有）",
        "action": "动作类型（如有）",
        // 其他从用户输入中提取的关键信息
      }}
    }}
  }}
}}
```

**示例**：
- 用户："打开客厅的灯"
  - executor_type: "mcp"
  - user_intent: "打开客厅的灯"
  - context: {{"location": "客厅", "target": "灯", "action": "打开"}}

注意：
- 如果是 simple_chat，可以省略 task_info
- response 字段必须包含，用于语音回复给用户
- 回复要简洁、友好、自然
- 对于 mcp 执行器，只需要提供 user_intent 和 context，不要尝试选择具体工具或填充工具参数
"""

def _extract_key_params(schema: dict) -> str:
    """从 schema 中提取关键参数描述
    
    Args:
        schema: 工具的 input schema
        
    Returns:
        str: 简化的参数描述
    """
    if not schema or not isinstance(schema, dict):
        return ""
    
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    
    if not properties:
        return ""
    
    param_list = []
    for param_name, param_info in properties.items():
        is_required = param_name in required
        param_type = param_info.get("type", "any")
        param_desc = param_info.get("description", "")
        
        required_mark = "*" if is_required else ""
        param_list.append(f"{param_name}{required_mark}({param_type})")
    
    return ", ".join(param_list[:3])  # 最多展示3个参数，避免过长

# 默认 Prompt（向后兼容）
ANALYZE_PROMPT = build_analyze_prompt()
