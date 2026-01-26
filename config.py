# 硬件配置
VIDEO_DEV="/dev/video0"

# OpenAI API 配置
import os
from dotenv import load_dotenv

# 加载项目根目录的 .env
load_dotenv(override=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv(
    "OPENAI_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
)

DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
DASHSCOPE_INTL_API_KEY = os.getenv("DASHSCOPE_INTL_API_KEY")
DASHSCOPE_BASE_URL = os.getenv(
    "DASHSCOPE_BASE_URL",
    "https://dashscope.aliyuncs.com/api/v1",
)

# 模型配置
QWEN_MAX_MODEL = "qwen-max"  # 任务决策推理模型
QWEN_VL_MODEL = "qwen-vl-plus"  # 视觉理解模型
QWEN_OMNI_MODEL = "qwen-omni-flash"  # 多模态交互模型
QWEN_TTS_FLASH = "qwen3-tts-flash" # TTS 模型

# Agent 配置
ACTION_TIMEOUT = 10.0  # Action 默认超时（秒）

# 统一任务循环配置
TASK_LOOP_INTERVAL = 1.0  # 主循环检查间隔（秒）
MAX_CONCURRENT_TASKS = 5  # 最大并发任务数
TASK_DEFAULT_TIMEOUT = 60.0  # 默认任务超时时间（秒）
TASK_DEFAULT_RETRIES = 3  # 默认最大重试次数

# ✅ 新增对话任务配置
CONVERSATION_PRIORITY = 8  # 对话任务优先级（高优先级）
CONVERSATION_TIMEOUT = 120.0  # 对话任务超时时间（秒）

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
    """构建意图分析 Prompt（智能问答模式）"""
    
    if available_actions is None:
        available_actions = [
            ("speak", "语音播报", ["tts"])
        ]
    
    actions_desc = ["【内置能力】"]
    for name, desc, capabilities in available_actions:
        actions_desc.append(f"  - **{name}**: {desc}")
    
    actions_text = "\n".join(actions_desc)
    
    mcp_text = ""
    if mcp_tools:
        mcp_desc = ["\n【MCP 工具服务】"]
        mcp_desc.append("  可调用外部工具获取实时信息：")
        for tool_name, tool_desc in mcp_tools:
            mcp_desc.append(f"  - **{tool_name}**: {tool_desc}")
        mcp_text = "\n".join(mcp_desc)
    
    return f"""你是一个智能问答助手的意图分析引擎。

你的任务是判断用户输入属于：
1. **simple_chat**: 闲聊、问候（例如："你好"、"你是谁"、"谢谢"）
2. **task_request**: 需要查询信息或执行任务（例如："今天天气怎么样"、"帮我搜索xxx"、"打开客厅的灯"）

**当前可用能力**：

{actions_text}{mcp_text}

**判断规则**：
- 简单闲聊 → simple_chat (直接回复)
- 需要外部信息或控制设备 → task_request (executor_type: "mcp")

**输出格式**（JSON）：
```json
{{
  "intent_type": "simple_chat" 或 "task_request",
  "response": "直接回复内容（simple_chat时使用）",
  "task_info": {{
    "executor_type": "mcp",
    "task_name": "任务名称",
    "parameters": {{
      "user_intent": "用户意图描述",
      "context": {{
        "query": "查询内容",
        "location": "位置（如有）"
      }}
    }}
  }}
}}
```

**示例1**：
用户："你好"
→ {{"intent_type": "simple_chat", "response": "你好！有什么我可以帮你的吗？"}}

**示例2**：
用户："今天北京天气怎么样？"
→ {{"intent_type": "task_request", "task_info": {{"executor_type": "mcp", "parameters": {{"user_intent": "查询北京今天的天气", "context": {{"location": "北京", "query": "今天天气"}}}}}}}}

注意：回复要简洁、自然、口语化。
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
