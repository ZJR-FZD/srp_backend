# MCP Controller

## 1. 背景与目标

随着 Agent 能力的增强，单一 MCP Server 已无法满足复杂机器人任务在**跨系统、多工具、长时序执行**方面的需求。本模块旨在构建一个 **MCP Controller（控制平面）**，用于统一管理多个 MCP Server，实现工具能力聚合、智能路由以及长任务的可靠执行。

### 设计目标

* 统一管理多个 MCP Server 的连接生命周期
* 聚合并索引各 MCP Server 提供的 Tool 能力
* 基于大模型（Qwen3-max）进行工具选择与路由决策
* 支持长任务、多轮 Tool 调用、失败重试与状态追踪
* 保持控制平面与执行平面的严格解耦，便于扩展与调试

---

## 2. 总体架构

MCP Controller 采用 **控制平面（Control Plane） / 执行平面（Execution Plane）分离架构**。

```
Agent Core (统一任务队列)
    │
    ▼
McpExecutor (任务执行器)
    │
    ▼
MCP Controller (Control Plane)
 ├─ McpManager (Facade)
 ├─ McpRouter (LLM-based Decision Engine)
 ├─ ToolIndex (Tool Capability Snapshot)
    │
    ▼
Connection Manager (Execution Plane)
 ├─ McpConnection (HTTP Stream / SSE)
    │
    ▼
Multiple MCP Servers
```

---

## 3. 模块划分与职责

### 3.1 McpManager（门面类）

#### 核心职责

* 统一入口，协调所有子模块
* 加载配置文件（mcp_server.json）
* 初始化连接池、工具索引、路由器
* 管理生命周期（初始化、关闭）

#### 配置加载

* 读取 mcp_server.json 配置
* 支持自定义 headers（如 Authorization）
* 连接失败容错处理
* 缓存策略配置（TTL、force_refresh_on_init）

#### 已废弃接口

> **重要提示**：以下接口已废弃，任务执行已迁移到统一任务队列架构

* `submit_task()`：已迁移到 McpExecutor
* `get_task_status()`：使用统一任务队列
* `cancel_task()`：使用统一任务队列
* `list_all_tasks()`：使用统一任务队列

#### 单例模式

* 采用 `__new__` 实现单例
* 避免重复初始化

#### 核心接口

```python
class McpManager:
    async def initialize(config_path: str, llm_client: LLMClientProtocol, agent=None)
    async def close()
```

---

### 3.2 McpConnection（连接管理）

#### 核心职责

* 管理单个 MCP Server 的连接生命周期
* 封装 HTTP Stream / SSE 通信协议
* 提供统一的工具调用接口
* 连接状态管理与健康检查

#### 连接状态模型

| 状态 | 说明 |
|------|------|
| DISCONNECTED | 未连接 |
| CONNECTING | 连接中 |
| READY | 已连接可用 |
| ERROR | 连接错误 |

#### HTTP Stream 实现

* 使用 `streamable_http_client`（来自 mcp SDK）
* 支持自定义 `httpx.AsyncClient`
* 自定义 headers 通过 AsyncClient 配置
* 超时策略：连接 10s，常规 30s，SSE 读取 300s

#### 健康检查机制

* 使用 `list_tools()` 作为心跳探测
* 失败阈值：3 次
* 达到阈值后标记为 ERROR

#### 工具调用接口

```python
async def call_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]
# 返回格式：
# {"success": bool, "result": Any} 或 {"success": bool, "error": str}
```

#### 结果序列化

* 将 MCP SDK 的 CallToolResult 对象转换为可序列化字典
* 提取 content、isError、meta 字段

---

### 3.3 ToolIndex（工具索引）

#### 核心职责

* 维护所有 MCP Server 提供的工具能力快照
* 为 Router 提供稳定、可控的工具视图
* 实现智能缓存策略

#### 数据模型

ToolIndexEntry 字段说明：

| 字段 | 类型 | 说明 |
|------|------|------|
| server_id | str | 所属 Server ID |
| tool_name | str | 工具名称 |
| description | str | 工具描述 |
| input_schema | Dict | 输入参数 Schema |
| tags | List[str] | 工具标签（自动提取） |
| blocking | bool | 是否阻塞操作 |
| cost_estimate | str | 成本估算（low/medium/high） |
| last_updated | str | 最后更新时间（ISO 格式） |

#### 缓存策略

智能同步决策流程：

1. 检查是否强制刷新（force_refresh_on_init）
2. 检查缓存文件是否存在
3. 检查缓存是否在 TTL 有效期内
4. 检查缓存是否包含工具数据

**同步规则**：

* 所有 Server 连接失败但有缓存：使用过期缓存
* 至少一个 Server 连接成功：保存新缓存
* 无缓存且所有 Server 失败：工具索引为空

#### 标签自动提取

* 基于 description 文本的关键词匹配
* 支持的标签：notification、emergency、navigation、perception

#### 查询接口

```python
def get_all_tools() -> List[ToolIndexEntry]
def get_tools_by_tag(tag: str) -> List[ToolIndexEntry]
def get_server_by_tool(tool_name: str) -> Optional[str]
def get_tool_entry(tool_name: str) -> Optional[ToolIndexEntry]
```

#### 缓存文件格式

```json
{
  "version": "1.0.0",
  "last_sync": "2026-01-07T10:00:00Z",
  "servers": [
    {
      "server_id": "ros2_mcp",
      "tools": [
        {
          "tool_name": "navigate_to",
          "description": "Navigate robot to target position",
          "input_schema": { "x": "float", "y": "float" },
          "tags": ["navigation", "robot"],
          "blocking": true,
          "cost_estimate": "high"
        }
      ]
    }
  ]
}
```

---

### 3.4 McpRouter（路由决策引擎）

#### 核心定位

Router 是 **决策模块**，而非执行模块。

#### 核心职责

* 基于 LLM 进行工具选择决策
* 不执行工具调用（职责分离）
* 不处理重试与错误恢复

#### 输入（RouterContext）

| 字段 | 类型 | 说明 |
|------|------|------|
| goal | str | 当前目标描述 |
| current_step | int | 当前步骤索引 |
| history | List[Dict] | 执行历史（最近 3 条） |
| environment | Dict[str, Any] | 环境上下文数据 |

#### 输出（RouterDecision）

| 字段 | 类型 | 说明 |
|------|------|------|
| server_id | Optional[str] | 目标 Server ID |
| tool | Optional[str] | 工具名称 |
| arguments | Dict[str, Any] | 工具参数 |
| confidence | float | 决策置信度（0.0-1.0） |
| reasoning | str | 决策理由 |

#### 决策机制

* 使用 LLM Function Calling 机制
* 系统提示词包含参数映射规则
* 特殊支持 Home Assistant 设备映射逻辑
* 默认置信度：0.8（LLM 选择工具时）

#### Home Assistant 设备映射逻辑

* 从 Environment 中读取设备列表
* 将用户友好名称映射到 entity_id
* 支持区域匹配、名称相似度、状态筛选
* 窗帘位置值：0（关闭）- 100（完全打开）

#### 无工具选择场景

* LLM 认为任务完成
* LLM 认为无合适工具
* 返回 confidence 0.3，tool 为 None

#### 技术说明

* 使用 Qwen3-max 作为分析引擎
* Router 不直接调用 MCP Server
* Router 不处理重试与错误恢复

---

### 3.5 LLMClientProtocol（依赖解耦协议）

#### 设计目的

* 实现与具体 LLM Client 的解耦
* 支持多种 LLM 实现接入
* 便于测试和扩展

#### 协议接口

**chat_completion**：
* 用途：文本对话/推理
* 参数：messages, temperature, max_tokens
* 返回：str（生成文本）

**function_call_completion**：
* 用途：工具选择决策
* 参数：messages, tools
* 返回：响应对象（包含 tool_calls 或 content）

#### 协议实现要求

* 任何符合协议的 LLM Client 都可注入
* Router 仅依赖协议接口，不依赖具体实现

```python
class LLMClientProtocol(Protocol):
    async def chat_completion(messages, temperature, max_tokens, **kwargs) -> str
    async def function_call_completion(messages, tools, **kwargs) -> Any
```

---

## 4. 执行流程说明

### 4.1 初始化流程

```
1. 创建 McpManager 实例（单例）
2. 调用 initialize(config_path, llm_client)
3. 加载 mcp_server.json 配置
4. 建立所有 MCP Server 连接
5. 加载或同步 Tool Index
6. 初始化 Router
7. 标记为已初始化
```

### 4.2 任务执行流程（McpExecutor）

> **重要提示**：任务执行已迁移到 `core/task/executors/mcp.py` 中的 McpExecutor

#### 计划驱动模式（默认）

```
1. 检查任务是否有执行计划（TaskPlan）
2. 无计划：调用 LLM 生成计划
3. 有计划：检查是否全部完成
4. 获取当前步骤（PlanStep）
5. 调用 Router.route() 获取决策
6. 通过 McpConnection.call_tool() 执行
7. 记录结果到步骤
8. 验证计划是否需要修订
9. 移动到下一步骤
10. 创建后续任务（通过任务队列）
```

#### 目标驱动模式（兼容模式）

```
1. 从任务中提取 goal 和 context
2. 调用 Router.route() 获取决策
3. 通过 McpConnection.call_tool() 执行
4. 记录执行历史
5. 评估任务完成度
6. 动态生成下一步 goal
7. 创建后续任务（通过任务队列）
```

### 4.3 工具调用流程

```
1. Router 生成 RouterDecision
2. 从 connections 字典获取 McpConnection
3. 调用 connection.call_tool(tool_name, arguments)
4. 等待 MCP Server 响应
5. 序列化 CallToolResult
6. 返回标准化结果字典
```

---

## 5. 配置文件格式

### 5.1 mcp_server.json

配置文件结构：

```json
{
  "mcp_servers": [
    {
      "id": "server_id",
      "url": "http://server.example.com/mcp",
      "timeout": 60,
      "headers": {
        "Authorization": "Bearer token_value"
      }
    }
  ],
  "cache_ttl_seconds": 3600,
  "force_refresh_on_init": false
}
```

字段说明：

| 字段 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| mcp_servers | Array | MCP Server 配置列表 | 必填 |
| id | str | Server 唯一标识 | 必填 |
| url | str | HTTP 端点 URL | 必填 |
| timeout | int | 工具调用超时（秒） | 60 |
| headers | Dict | 自定义 HTTP Headers | {} |
| cache_ttl_seconds | int | 工具索引缓存有效期 | 3600 |
| force_refresh_on_init | bool | 初始化时强制刷新 | false |

---

## 6. 使用示例

### 6.1 初始化

```python
# 创建 LLM Client 实例（实现 LLMClientProtocol）
from core.client.openai_client import OpenAIClient
llm_client = OpenAIClient()

# 创建 McpManager 实例
from core.mcp_control import McpManager
manager = McpManager()

# 初始化
await manager.initialize(
    config_path="core/mcp_control/mcp_server.json",
    llm_client=llm_client
)
```

### 6.2 提交任务（通过统一任务队列）

```python
from core.task.models import UnifiedTask, TaskType

# 创建 MCP 任务
task = UnifiedTask(
    task_type=TaskType.MCP_CALL,
    execution_data={
        "goal": "打开客厅的灯",
        "user_intent": "打开客厅的灯"
    },
    context={}
)

# 提交到任务队列
await agent.task_queue.enqueue(task)

# McpExecutor 自动处理任务
# - 调用 Router 决策
# - 执行工具调用
# - 管理多轮执行
```

### 6.3 关闭连接

```python
# 关闭所有 MCP Server 连接
await manager.close()
```

---

## 7. 控制平面与执行平面分离原则

| 层级 | 内容 | 是否使用 LLM |
|------|------|-------------|
| 控制平面 | McpRouter（决策）、ToolIndex（索引） | 是（仅 Router） |
| 执行平面 | McpConnection（连接）、HTTP Stream Client | 否 |
| 任务编排 | McpExecutor（统一任务队列） | 是（计划生成、完成度判断） |

该分离设计保证：

* 系统行为可预测
* 任务可恢复、可回放
* MCP Server 故障不影响整体控制逻辑

---

## 8. 未来扩展

### 8.1 原有扩展方向

* 引入 Task 持久化（SQLite / Redis）实现断点恢复
* 引入 Tool Capability Tagging 与成本模型
* 支持多 Router（规则 + LLM 混合）
* 支持跨 MCP Server 的 Plan 编排

### 8.2 新增扩展方向

* 连接池动态扩缩容
* 工具索引增量同步
* Router 决策缓存与优化
* 连接健康检查定时任务
* 工具调用性能监控

