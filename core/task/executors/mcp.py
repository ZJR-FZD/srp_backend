# core/task/executors/mcp.py
"""MCP任务执行器"""
from typing import Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass
import json
from core.task.executors.base import BaseTaskExecutor
from core.task.models import UnifiedTask, TaskStatus, TaskType, TaskPlan, PlanStep, PlanStepStatus


@dataclass
class CompletionJudgment:
    """任务完成度判断结果"""
    completed: bool  # 是否完成
    confidence: float  # 完成置信度 0.0-1.0
    reason: str  # 完成原因代码
    analysis: str = ""  # 详细分析说明


class McpExecutor(BaseTaskExecutor):
    """MCP任务执行器
    
    执行MCP工具调用任务，支持多轮决策和自动重试
    整合自task_manager.py的逻辑
    """
    
    def __init__(self, router, connections, task_queue=None,
                 home_context_ttl=60,
                 completion_confidence_threshold=0.7,
                 enable_llm_completion_judge=False,
                 enable_plan_based_mode=True,
                 max_plan_steps=20,
                 max_plan_revisions=3,
                 plan_verification_mode="rule"):
        """初始化MCP执行器
        
        Args:
            router: MCP Router实例
            connections: server_id -> McpConnection的字典
            task_queue: 任务队列（用于创建后续任务）
            home_context_ttl: GetLiveContext缓存有效期（秒），默认60秒
            completion_confidence_threshold: 完成度判断最低置信度，默认0.7（旧模式）
            enable_llm_completion_judge: 是否启用LLM完成度评估，默认False（旧模式）
            enable_plan_based_mode: 是否启用计划驱动模式，默认True
            max_plan_steps: 计划最大步骤数，默认20
            max_plan_revisions: 计划最大修订次数，默认3
            plan_verification_mode: 计划验证模式，"rule"或"llm"，默认"rule"
        """
        super().__init__()
        self.router = router
        self.connections = connections
        self.task_queue = task_queue
        self.home_context_ttl = home_context_ttl
        self.completion_confidence_threshold = completion_confidence_threshold
        self.enable_llm_completion_judge = enable_llm_completion_judge
        # 新增计划驱动模式配置
        self.enable_plan_based_mode = enable_plan_based_mode
        self.max_plan_steps = max_plan_steps
        self.max_plan_revisions = max_plan_revisions
        self.plan_verification_mode = plan_verification_mode
    
    async def validate(self, task: UnifiedTask) -> bool:
        """验证任务参数"""
        if not await super().validate(task):
            return False
        
        # 验证goal
        goal = task.execution_data.get("goal")
        if not goal:
            self._log(task, "No goal provided", "ERROR")
            return False
        
        return True
    
    async def execute(self, task: UnifiedTask) -> None:
        """执行MCP任务
        
        支持两种模式：
        1. 计划驱动模式（默认）：生成执行计划，按步骤执行
        2. 目标驱动模式（兼容）：动态goal生成，完成度判断
        """
        # 模式检测：如果启用计划模式且任务没有plan字段，则使用计划驱动
        if self.enable_plan_based_mode:
            await self._execute_plan_based(task)
        else:
            await self._execute_legacy(task)
    
    async def _execute_plan_based(self, task: UnifiedTask) -> None:
        """计划驱动模式执行
        
        执行流程：
        1. 检查是否已有plan，没有则调用_generate_plan
        2. 检查plan是否全部完成，是则标记任务COMPLETED
        3. 获取当前步骤，调用_analyze_step（输入为步骤描述）
        4. 执行工具，记录结果到步骤
        5. 调用_verify_plan验证计划是否需要修订
        6. 如需修订，调用_revise_plan更新计划
        7. 移动到下一步骤，创建后续任务
        """
        try:
            # 验证参数
            if not await self.validate(task):
                task.transition_to(TaskStatus.FAILED, "Validation failed")
                return
            
            goal = task.execution_data.get("goal")
            user_intent = task.execution_data.get("user_intent", goal)
            
            # 步骤1：检查或生成计划
            if not task.plan:
                self._log(task, "No plan found, generating...")
                task.plan = await self._generate_plan(task, goal, task.context)
            
            # 步骤2：检查计划是否已完成
            if self._is_plan_completed(task.plan):
                self._log(task, "All plan steps completed, task finished")
                task.result = {
                    "success": True,
                    "plan_completed": True,
                    "total_steps": len(task.plan.steps),
                    "revision_count": task.plan.revision_count
                }
                task.transition_to(TaskStatus.COMPLETED, "Plan completed successfully")
                return
            
            # 步骤3：获取当前步骤
            current_step = task.plan.get_current_step()
            if not current_step:
                self._log(task, "No current step available", "ERROR")
                task.transition_to(TaskStatus.FAILED, "Plan execution error: no current step")
                return
            
            # 检查步骤数限制
            if len(task.plan.steps) > self.max_plan_steps:
                self._log(task, f"Plan has too many steps ({len(task.plan.steps)})", "ERROR")
                task.result = {"success": False, "error": "Plan has too many steps"}
                task.transition_to(TaskStatus.FAILED, "Plan has too many steps")
                return
            
            self._log(task, f"Executing step {task.plan.current_step_index + 1}/{len(task.plan.steps)}: {current_step.description}")
            
            # 标记步骤开始
            current_step.status = PlanStepStatus.IN_PROGRESS
            current_step.started_at = datetime.now().timestamp()
            
            # 家居任务上下文预获取
            if self._is_home_automation_task(task):
                self._log(task, "Detected home automation task, ensuring context")
                await self._ensure_home_context(task)
            
            # 步骤4：决策与执行
            step_goal = current_step.description
            decision = await self._analyze_step(task, step_goal, task.plan.current_step_index)
            
            # 检查决策有效性
            if not decision.tool:
                if decision.confidence >= 0.6:
                    # 高置信度，认为步骤完成
                    self._log(task, f"Step completed (no tool needed, confidence={decision.confidence})")
                    current_step.status = PlanStepStatus.COMPLETED
                    current_step.completed_at = datetime.now().timestamp()
                    current_step.execution_result = {"success": True, "reasoning": decision.reasoning}
                else:
                    # 低置信度，步骤失败
                    self._log(task, f"Step failed (cannot find tool, confidence={decision.confidence})", "ERROR")
                    current_step.status = PlanStepStatus.FAILED
                    current_step.completed_at = datetime.now().timestamp()
                    current_step.execution_result = {"success": False, "error": decision.reasoning}
                    
                    # 尝试修订计划
                    if task.plan.revision_count < self.max_plan_revisions:
                        await self._revise_plan(task, f"Cannot find suitable tool: {decision.reasoning}")
                    else:
                        task.result = {"success": False, "error": "Cannot find suitable tool"}
                        task.transition_to(TaskStatus.FAILED, "Cannot find suitable tool")
                        return
                
                # 移动到下一步骤
                task.plan.advance_step()
                task.transition_to(TaskStatus.COMPLETED, f"Step {task.plan.current_step_index} completed")
                
                # 创建后续任务
                await self._create_next_plan_task(task)
                return
            
            # 检查置信度
            if decision.confidence < 0.6:
                self._log(task, f"Low confidence ({decision.confidence})", "ERROR")
                current_step.status = PlanStepStatus.FAILED
                current_step.completed_at = datetime.now().timestamp()
                current_step.execution_result = {"success": False, "error": f"Low confidence: {decision.confidence}"}
                
                # 尝试修订计划
                if task.plan.revision_count < self.max_plan_revisions:
                    await self._revise_plan(task, f"Low confidence decision: {decision.confidence}")
                    task.plan.advance_step()
                    task.transition_to(TaskStatus.COMPLETED, "Step failed, plan revised")
                    await self._create_next_plan_task(task)
                else:
                    task.result = {"success": False, "error": "Low confidence and max revisions reached"}
                    task.transition_to(TaskStatus.FAILED, "Low confidence")
                return
            
            # 执行工具
            tool_result = await self._execute_tool(task, decision)
            
            # 记录历史
            self._record_history(task, decision, tool_result, task.plan.current_step_index)
            
            # 记录执行结果到步骤
            current_step.execution_result = tool_result
            current_step.completed_at = datetime.now().timestamp()
            
            # 步骤5：处理结果
            if tool_result["success"]:
                # 成功
                self._extract_query_result_to_context(task, decision, tool_result)
                current_step.status = PlanStepStatus.COMPLETED
                
                self._log(task, f"Step {task.plan.current_step_index + 1} completed successfully")
                
                # 步骤6：验证计划是否需要修订
                need_revision = await self._verify_plan(task, current_step, tool_result)
                
                if need_revision:
                    self._log(task, "Plan verification failed, revising plan")
                    await self._revise_plan(task, "Execution result does not match expectations")
                
                # 步骤7：移动到下一步骤
                task.plan.advance_step()
                task.transition_to(TaskStatus.COMPLETED, f"Step {task.plan.current_step_index} completed")
                
                # 创建后续任务
                await self._create_next_plan_task(task)
            else:
                # 失败
                current_step.status = PlanStepStatus.FAILED
                self._log(task, f"Step {task.plan.current_step_index + 1} failed: {tool_result.get('error')}", "ERROR")
                
                # 检查是否需要修订计划
                need_revision = await self._verify_plan(task, current_step, tool_result)
                
                if need_revision and task.plan.revision_count < self.max_plan_revisions:
                    await self._revise_plan(task, f"Step failed: {tool_result.get('error')}")
                    task.plan.advance_step()
                    task.transition_to(TaskStatus.COMPLETED, "Step failed, plan revised")
                    await self._create_next_plan_task(task)
                elif task.can_retry():
                    # 重试当前步骤
                    task.increment_retry()
                    current_step.status = PlanStepStatus.PENDING  # 重置为待执行
                    task.transition_to(TaskStatus.RETRYING, f"Retry {task.retry_count}/{task.max_retries}")
                    task.transition_to(TaskStatus.COMPLETED, "Retry task created")
                    await self._create_next_plan_task(task)
                else:
                    # 任务失败
                    task.result = {"success": False, "error": tool_result.get("error")}
                    task.transition_to(TaskStatus.FAILED, "Step failed and cannot retry")
                    
        except Exception as e:
            await self.handle_error(task, e)
    
    async def _create_next_plan_task(self, task: UnifiedTask) -> None:
        """创建后续计划任务
        
        Args:
            task: 当前任务
        """
        if not self.task_queue:
            self._log(task, "Cannot create next task: task_queue not set", "ERROR")
            return
        
        # 创建新任务，继承 plan
        next_task = UnifiedTask(
            task_type=TaskType.MCP_CALL,
            priority=task.priority,
            timeout=task.timeout,
            max_retries=task.max_retries,
            context=task.context.copy(),
            execution_data=task.execution_data.copy(),
            plan=task.plan  # 继承计划
        )
        
        # 继承重试计数
        next_task.retry_count = task.retry_count
        
        await self.task_queue.enqueue(next_task)
        self._log(task, f"Created next plan task {next_task.task_id[:8]}")
    
    
    async def _execute_legacy(self, task: UnifiedTask) -> None:
        """目标驱动模式执行(旧逻辑、用于兼容)
        
        执行流程(单步):
        1. 从任务中获取goal和context
        2. 构建RouterContext、传递history
        3. 调用router.route()获取决策
        4. 如无工具选择且置信度高、标记为COMPLETED
        5. 如有工具选择、调用connection.call_tool()
        6. 记录执行历史
        7. 根据结果动态生成新goal
        8. 如执行失败且可重试、创建新任务
        9. 如执行成功且是中间步骤、创建新任务继续执行
        """
        try:
            # 验证参数
            if not await self.validate(task):
                task.transition_to(TaskStatus.FAILED, "Validation failed")
                return
            
            # 获取参数
            goal = task.execution_data.get("goal")
            current_step = task.execution_data.get("current_step", 0)
            max_steps = task.execution_data.get("max_steps", 10)
            user_intent = task.execution_data.get("user_intent", goal)
            
            self._log(task, f"Executing MCP task: step {current_step}/{max_steps}")
            self._log(task, f"Goal: {goal}")
            
            # 改动8：任务意图识别（仅在首次执行时）
            if current_step == 0 and "task_intent_type" not in task.context:
                task_intent_type = self._classify_task_intent(user_intent)
                task.context["task_intent_type"] = task_intent_type
                self._log(task, f"Task intent classified as: {task_intent_type}")
            
            # 检查步骤限制
            if current_step >= max_steps:
                self._log(task, f"Max steps ({max_steps}) reached", "WARNING")
                task.result = {"success": False, "error": "Max steps reached"}
                task.transition_to(TaskStatus.COMPLETED, "Max steps reached")
                return
            
            # 0. 家居任务上下文预获取（方案一）
            if self._is_home_automation_task(task):
                self._log(task, "Detected home automation task, ensuring context")
                context_updated = await self._ensure_home_context(task)
                if context_updated:
                    # 增强goal以包含设备信息
                    goal = self._enhance_goal_with_devices(task, goal)
                    task.execution_data["goal"] = goal
                    self._log(task, "Goal enhanced with device information")
            
            # 1. 决策阶段
            decision = await self._analyze_step(task, goal, current_step)
            
            # 2. 检查决策有效性
            if not decision.tool:
                if decision.confidence >= 0.6:
                    # 高置信度认为任务已完成
                    self._log(task, f"Task completed (no more tools needed, confidence={decision.confidence})")
                    task.result = {"success": True, "reasoning": decision.reasoning}
                    task.transition_to(TaskStatus.COMPLETED, decision.reasoning or "No more tools needed")
                else:
                    # 低置信度认为无法继续
                    self._log(task, f"Cannot find suitable tool (confidence={decision.confidence})", "ERROR")
                    task.result = {"success": False, "error": f"Cannot find suitable tool: {decision.reasoning}"}
                    task.transition_to(TaskStatus.FAILED, f"Low confidence: {decision.confidence}")
                return
            
            # 检查置信度
            if decision.confidence < 0.6:
                self._log(task, f"Low confidence ({decision.confidence})", "ERROR")
                task.result = {"success": False, "error": f"Low confidence: {decision.confidence}"}
                task.transition_to(TaskStatus.FAILED, f"Low confidence: {decision.confidence}")
                return
            
            # 3. 执行工具调用
            tool_result = await self._execute_tool(task, decision)
            
            # 4. 记录历史
            self._record_history(task, decision, tool_result, current_step)
            
            # 5. 处理结果
            if tool_result["success"]:
                # 成功，将查询结果提取到context
                self._extract_query_result_to_context(task, decision, tool_result)
                
                # 方案三：评估任务完成度
                completion = self._evaluate_completion(task, decision, tool_result)
                self._log(task, f"Completion evaluation: {completion.reason} (confidence={completion.confidence})")
                
                # 判断是否完成
                if completion.completed and completion.confidence >= self.completion_confidence_threshold:
                    # 任务完成
                    self._log(task, f"Task completed: {completion.analysis}")
                    task.result = {
                        "success": True,
                        "completion_reason": completion.reason,
                        "completion_confidence": completion.confidence,
                        "completion_analysis": completion.analysis,
                        "executed_steps": current_step + 1,
                        "tool_result": tool_result
                    }
                    task.transition_to(TaskStatus.COMPLETED, completion.analysis)
                else:
                    # 需要继续执行
                    self._log(task, f"Step {current_step} completed, continuing to next step")
                    
                    # 动态更新goal
                    new_goal = self._update_goal_after_step(task, decision, tool_result, user_intent)
                    
                    task.transition_to(TaskStatus.COMPLETED, f"Step {current_step} completed")
                    
                    # 创建后续任务
                    await self._create_next_task(task, new_goal, current_step + 1, max_steps, user_intent)
            else:
                # 失败，检查重试
                if task.can_retry():
                    task.increment_retry()
                    self._log(task, f"Tool call failed, will retry ({task.retry_count}/{task.max_retries})", "WARNING")
                    
                    # 动态更新goal（包含错误信息）
                    new_goal = self._update_goal_after_step(task, decision, tool_result, user_intent)
                    
                    # 标记为需要重试，并创建新任务
                    task.transition_to(TaskStatus.RETRYING, f"Retry {task.retry_count}/{task.max_retries}")
                    task.transition_to(TaskStatus.COMPLETED, "Retry task created")
                    
                    # 创建重试任务
                    await self._create_next_task(task, new_goal, current_step, max_steps, user_intent, is_retry=True)
                else:
                    # 超过重试次数
                    self._log(task, "Max retries exceeded", "ERROR")
                    task.result = {"success": False, "error": tool_result.get("error")}
                    task.transition_to(TaskStatus.FAILED, "Max retries exceeded")
                    
        except Exception as e:
            await self.handle_error(task, e)
    
    async def _analyze_step(self, task: UnifiedTask, goal: str, current_step: int):
        """分析下一步动作
        
        Args:
            task: 任务对象
            goal: 当前目标
            current_step: 当前步骤
            
        Returns:
            RouterDecision: 路由决策
        """
        # 构建Router上下文
        router_context = {
            "goal": goal,
            "current_step": current_step,
            "history": task.history,
            "environment": task.context
        }
        
        self._log(task, "Analyzing next step with Router")
        decision = await self.router.route(router_context)
        
        if decision.tool:
            self._log(task, f"Router decision: {decision.tool} (confidence={decision.confidence})")
        else:
            self._log(task, f"Router decision: no need tool (confidence={decision.confidence})")
        
        return decision
    
    async def _execute_tool(self, task: UnifiedTask, decision) -> Dict[str, Any]:
        """执行工具调用
        
        Args:
            task: 任务对象
            decision: 路由决策
            
        Returns:
            Dict[str, Any]: 执行结果
        """
        # 获取目标连接
        connection = self.connections.get(decision.server_id)
        if not connection:
            return {"success": False, "error": f"Connection {decision.server_id} not found"}
        
        # 调用工具
        self._log(task, f"Calling tool {decision.tool} on {decision.server_id}")
        result = await connection.call_tool(decision.tool, decision.arguments)
        # 方案二：规范化结果解析
        result = self._normalize_tool_result(result, decision.tool)
        
        if result.get("success"):
            self._log(task, f"Tool call succeeded")
        else:
            self._log(task, f"Tool call failed: {result.get('error')}", "ERROR")
        
        return result
    
    def _record_history(self, task: UnifiedTask, decision, result: Dict[str, Any], current_step: int) -> None:
        """记录执行历史"""
        entry = {
            "step": current_step,
            "timestamp": datetime.now().timestamp(),
            "action": "call_tool",
            "server_id": decision.server_id,
            "tool": decision.tool,
            "arguments": decision.arguments,
            "result": result
        }
        task.history.append(entry)
    
    def _classify_tool_type(self, tool_name: str) -> str:
        """分类工具类型"""
        query_keywords = ["Get", "List", "Query", "Find", "Search", "Fetch", "Describe", "Show"]
        action_keywords = ["Set", "Create", "Update", "Delete", "Turn", "Start", "Stop", "Execute", "Send", "Run", "Call", "Invoke"]
        
        for keyword in query_keywords:
            if keyword in tool_name:
                return "query"
        
        for keyword in action_keywords:
            if keyword in tool_name:
                return "action"
        
        return "hybrid"
    
    def _classify_error_pattern(self, error_info: str) -> str:
        """分类错误模式"""
        error_lower = error_info.lower()
        
        if any(keyword in error_lower for keyword in ["not found", "does not exist", "unknown", "no such"]):
            return "resource_not_found"
        
        if any(keyword in error_lower for keyword in ["invalid", "incorrect", "malformed", "bad request"]):
            return "invalid_parameter"
        
        if any(keyword in error_lower for keyword in ["permission", "forbidden", "unauthorized", "access denied"]):
            return "permission_denied"
        
        if any(keyword in error_lower for keyword in ["not support", "unsupported", "unavailable"]):
            return "tool_unsupported"
        
        if any(keyword in error_lower for keyword in ["timeout", "network", "connection"]):
            return "network_issue"
        
        return "unknown_error"
    
    def _extract_result_summary(self, decision, result: Dict[str, Any]) -> str:
        """提取执行结果摘要"""
        if result.get("success"):
            tool_type = self._classify_tool_type(decision.tool)
            
            if tool_type == "query":
                result_data = result.get("content") or result.get("result", "")
                
                if isinstance(result_data, str) and len(result_data) > 200:
                    summary = f"查询成功，已获取数据（{decision.tool}）: {result_data[:200]}..."
                elif result_data:
                    summary = f"查询成功，已获取数据（{decision.tool}）: {result_data}"
                else:
                    summary = f"查询成功（{decision.tool}）"
                
                return summary
            else:
                return f"操作成功（{decision.tool}）"
        else:
            error_info = result.get("error", "未知错误")
            if isinstance(error_info, dict):
                error_info = error_info.get("content", str(error_info))
            
            if isinstance(error_info, str) and len(error_info) > 150:
                error_info = error_info[:150] + "..."
            
            return f"失败 - {error_info}"
    
    def _extract_query_result_to_context(self, task: UnifiedTask, decision, result: Dict[str, Any]) -> None:
        """将查询类工具的结果提取到任务上下文中"""
        tool_type = self._classify_tool_type(decision.tool)
        
        if tool_type == "query" and result.get("success"):
            result_data = result.get("result") or result.get("content")
            if result_data:
                context_key = f"{decision.tool}_result"
                task.context[context_key] = result_data
                self._log(task, f"Extracted query result to context: {context_key}")
    
    def _update_goal_after_step(self, task: UnifiedTask, decision, result: Dict[str, Any], user_intent: str) -> str:
        """根据执行结果动态更新任务目标（符合用户偏好记忆）"""
        result_summary = self._extract_result_summary(decision, result)
        tool_type = self._classify_tool_type(decision.tool)
        
        if result.get("success"):
            if tool_type == "query":
                # 改动6：针对GetLiveContext等家居上下文查询工具，生成明确的操作指令
                if decision.tool == "GetLiveContext" or "LiveContext" in decision.tool:
                    next_goal = f"""已获取家居设备信息，现在执行用户需求：{user_intent}

根据已获取的设备列表，选择合适的设备执行操作。务必使用实际entity_id和区域名称，禁止使用'当前位置'等模糊描述。"""
                else:
                    next_goal = "根据查询结果执行实际操作"
            else:
                next_goal = "继续执行后续操作（如有）"
        else:
            error_info = result.get("error", "")
            error_pattern = self._classify_error_pattern(str(error_info))
            
            if error_pattern == "resource_not_found":
                next_goal = "重新查询可用资源信息，然后使用正确的标识符重试"
            elif error_pattern == "invalid_parameter":
                next_goal = "分析参数要求，调整参数后重试"
            elif error_pattern == "tool_unsupported":
                next_goal = "选择功能相近的替代工具重试"
            elif error_pattern == "permission_denied":
                next_goal = "权限不足，尝试其他途径或提示用户"
            elif error_pattern == "network_issue":
                next_goal = "等待后重试"
            else:
                next_goal = "分析失败原因并调整执行策略"
        
        new_goal = f"""当前用户需求：{user_intent}
上一轮任务执行结果：{result_summary}
本次执行目标：{next_goal}"""
        
        return new_goal
    
    async def _create_next_task(self, current_task: UnifiedTask, new_goal: str, next_step: int, 
                                max_steps: int, user_intent: str, is_retry: bool = False) -> None:
        """创建后续任务"""
        if not self.task_queue:
            self._log(current_task, "Cannot create next task: task_queue not set", "ERROR")
            return
        
        # 创建新的MCP任务
        next_task = UnifiedTask(
            task_type=TaskType.MCP_CALL,
            priority=current_task.priority,
            timeout=current_task.timeout,
            max_retries=current_task.max_retries,
            context=current_task.context.copy(),
            execution_data={
                "goal": new_goal,
                "current_step": next_step,
                "max_steps": max_steps,
                "user_intent": user_intent
            }
        )
        
        # 继承重试计数（如果是重试任务）
        if is_retry:
            next_task.retry_count = current_task.retry_count
            
            # 改动7：重试时检查错误类型，决定是否强制刷新上下文
            # 从当前任务历史中获取最后一次失败的错误
            if current_task.history:
                last_entry = current_task.history[-1]
                result = last_entry.get("result", {})
                error_info = str(result.get("error", ""))
                error_pattern = self._classify_error_pattern(error_info)
                
                if error_pattern in ["resource_not_found", "invalid_parameter"]:
                    next_task.context["force_refresh_home_context"] = True
                    self._log(current_task, f"Setting force_refresh flag due to {error_pattern}")
        
        await self.task_queue.enqueue(next_task)
        
        if is_retry:
            self._log(current_task, f"Created retry task {next_task.task_id[:8]}")
        else:
            self._log(current_task, f"Created next task {next_task.task_id[:8]} for step {next_step}")
    
    def _classify_task_intent(self, user_intent: str) -> str:
        """分类用户任务意图
        
        Args:
            user_intent: 用户原始意图文本
            
        Returns:
            str: 任务类型 - "query_only" / "action_task" / "unknown"
        """
        # 查询动词
        query_verbs = ["查看", "查询", "显示", "获取", "列出", "看", "看看", 
                       "是多少", "是什么", "有哪些", "告诉我"]
        
        # 操作动词
        action_verbs = ["打开", "关闭", "设置", "调节", "控制", "开启", "关掉",
                        "关上", "启动", "停止", "发送", "创建", "删除", "修改",
                        "拉上", "拉开", "调整", "增加", "减少"]
        
        has_query = any(verb in user_intent for verb in query_verbs)
        has_action = any(verb in user_intent for verb in action_verbs)
        
        if has_action:
            # 包含操作动词，视为操作任务
            return "action_task"
        elif has_query:
            # 仅包含查询动词，视为纯查询任务
            return "query_only"
        else:
            # 无法判断，默认为操作任务（保守策略）
            return "unknown"
    
    # ================== 家居任务上下文预获取 ==================
    
    def _is_home_automation_task(self, task: UnifiedTask) -> bool:
        """判断是否为家居控制任务
        
        识别规则：
        0. 任务类型明确标记为home_automation
        1. 用户意图包含家居动作词 + 家居实体词
        2. 工具历史中出现Home Assistant相关工具
        3. 上下文标记home_automation=true
        
        Args:
            task: 任务对象
            
        Returns:
            bool: 是否为家居任务
        """
        # 改动1：规则0 - 检查任务类型明确标记
        if task.context.get("task_type") == "home_automation":
            return True
        
        # 规则1：检查上下文标记
        if task.context.get("home_automation"):
            return True
        
        # 规则2：检查工具历史
        hass_tools = ["HassGetLiveContext", "HassTurnOn", "HassTurnOff", 
                      "HassSetPosition", "HassGetState", "HassListEntities",
                      "HassSetTemperature", "HassSetBrightness"]
        for entry in task.history:
            if entry.get("action") == "call_tool":
                tool_name = entry.get("tool", "")
                if any(hass_tool in tool_name for hass_tool in hass_tools):
                    return True
        
        # 改动1：规则3 - 扩展关键词匹配
        user_intent = task.execution_data.get("user_intent", "")
        if not user_intent:
            user_intent = task.execution_data.get("goal", "")
        
        # 动作词（扩展）
        action_keywords = ["打开", "关闭", "调节", "设置", "控制", 
                          "开启", "关掉", "关上", "启动", "停止",
                          "拉上", "拉开", "调整", "增加", "减少"]
        # 家居实体词（扩展）
        entity_keywords = ["灯", "空调", "设备", "风扇", "温度", "亮度", 
                          "暖气", "加湿器",
                          "窗帘", "门窗", "百叶窗", "床帘",
                          "电视", "插座"]
        
        has_action = any(keyword in user_intent for keyword in action_keywords)
        has_entity = any(keyword in user_intent for keyword in entity_keywords)
        
        return has_action and has_entity
    
    async def _ensure_home_context(self, task: UnifiedTask) -> bool:
        """确保家居上下文已获取
        
        检查是否需要调用GetLiveContext：
        - 首次执行或缓存过期
        - 上一轮操作失败且错误提示设备不存在
        - 强制刷新标志被设置
        
        Args:
            task: 任务对象
            
        Returns:
            bool: 是否更新了上下文
        """
        current_time = datetime.now().timestamp()
        
        # 改动2：检查强制刷新标志
        force_refresh = task.context.get("force_refresh_home_context", False)
        if force_refresh:
            self._log(task, "Force refresh flag set, refreshing home context")
            # 清除标志，避免重复刷新
            task.context["force_refresh_home_context"] = False
        else:
            # 改动2：检查是否已有缓存且未过期
            home_context = task.context.get("home_live_context")
            if home_context and isinstance(home_context, dict):
                cached_time = home_context.get("timestamp", 0)
                if current_time - cached_time < self.home_context_ttl:
                    self._log(task, "Using cached home context")
                    return False
            
            # 改动2：如果上下文不存在，直接获取（首次执行）
            if not home_context:
                self._log(task, "Home context not found, fetching for the first time")
            
            # 检查是否因设备不存在错误需要刷新
            need_refresh = False
            if task.history:
                last_entry = task.history[-1]
                if last_entry.get("action") == "call_tool":
                    result = last_entry.get("result", {})
                    if not result.get("success"):
                        error_msg = str(result.get("error", "")).lower()
                        if any(keyword in error_msg for keyword in ["not found", "does not exist", "unknown"]):
                            need_refresh = True
                            self._log(task, "Device not found error detected, refreshing context")
            
            # 如果缓存存在且未过期，且没有错误，则不需要刷新
            if home_context and not need_refresh:
                return False
        
        # 调用GetLiveContext
        try:
            self._log(task, "Calling GetLiveContext to fetch device information")
            
            # 查找包含GetLiveContext的server
            get_live_context_server = None
            for server_id, connection in self.connections.items():
                # 假设我们可以通过connection检查工具
                # 这里简化处理，假设有home-assistant server
                if "home" in server_id.lower() or "hass" in server_id.lower():
                    get_live_context_server = server_id
                    break
            
            if not get_live_context_server:
                self._log(task, "GetLiveContext server not found, skipping context fetch", "WARNING")
                return False
            
            connection = self.connections[get_live_context_server]
            result = await connection.call_tool("GetLiveContext", {})
            
            if not result.get("success"):
                self._log(task, f"GetLiveContext failed: {result.get('error')}", "WARNING")
                return False
            
            # 解析设备信息
            raw_data = result.get("content") or result.get("result", "")
            devices_info = self._parse_live_context(raw_data)
            
            print(f"devices_info: {devices_info}")
            
            # 注入到context
            task.context["home_live_context"] = {
                "timestamp": current_time,
                "devices": devices_info.get("devices", []),
                "areas": devices_info.get("areas", []),
                "raw_data": raw_data
            }
            task.context["home_automation"] = True
            
            self._log(task, f"Home context updated: {len(devices_info.get('devices', []))} devices found")
            return True
            
        except Exception as e:
            self._log(task, f"Error fetching home context: {e}", "WARNING")
            return False
    
    def _parse_live_context(self, raw_data: Any) -> Dict[str, Any]:
        """解析GetLiveContext返回的设备信息
        
        Args:
            raw_data: GetLiveContext返回的原始数据
            
        Returns:
            Dict: 包含devices和areas的字典
        """
        devices = []
        areas = set()
        
        try:
            import json
            import re
            
            # 步骤1: 提取文本内容
            text_content = None
            
            # 情况1: raw_data是字典，可能包含content字段
            if isinstance(raw_data, dict):
                # 检查是否有content字段（MCP SDK格式）
                if "content" in raw_data:
                    content_list = raw_data["content"]
                    if isinstance(content_list, list) and len(content_list) > 0:
                        first_item = content_list[0]
                        # 如果是字典，提取text字段
                        if isinstance(first_item, dict) and "text" in first_item:
                            text_content = first_item["text"]
                        # 如果是对象，尝试访问text属性
                        elif hasattr(first_item, "text"):
                            text_content = first_item.text
                # 如果没有content字段，尝试直接作为entities列表处理（兼容旧格式）
                elif "entities" in raw_data or "devices" in raw_data:
                    return self._parse_entities_dict(raw_data)
            # 情况2: raw_data本身就是字符串
            elif isinstance(raw_data, str):
                text_content = raw_data
            
            # 如果没有找到文本内容，返回空结果
            if not text_content:
                print(f"[McpExecutor] No text content found in raw_data")
                return {"devices": [], "areas": []}
            
            # 步骤2: 解析嵌套的JSON（如果text_content是JSON字符串）
            try:
                parsed_json = json.loads(text_content)
                if isinstance(parsed_json, dict):
                    # 提取result字段（Home Assistant格式）
                    if "result" in parsed_json:
                        text_content = parsed_json["result"]
                    # 或者直接包含entities
                    elif "entities" in parsed_json or "devices" in parsed_json:
                        return self._parse_entities_dict(parsed_json)
            except (json.JSONDecodeError, TypeError):
                # 不是JSON，继续作为纯文本处理
                pass
            
            # 步骤3: 解析YAML格式的设备列表
            # 使用正则表达式提取每个设备块
            device_pattern = r'-\s+names:\s+([^\n]+)\n\s+domain:\s+(\w+)\n\s+state:\s+([^\n]+)(?:\n\s+areas:\s+([^\n]+))?(?:\n\s+attributes:([^-]*))?'
            matches = re.finditer(device_pattern, text_content, re.MULTILINE)
            
            for match in matches:
                names_str = match.group(1).strip()
                domain = match.group(2).strip()
                state = match.group(3).strip().strip("'\"")
                areas_str = match.group(4).strip() if match.group(4) else ""
                attributes_str = match.group(5) if match.group(5) else ""
                
                # 解析names（可能是逗号分隔的多个名称）
                names_list = [n.strip() for n in names_str.split(',')]
                friendly_name = names_list[0] if names_list else ""
                
                # 生成entity_id（使用第一个名称）
                # 优先使用英文名称作为entity_id的一部分
                entity_name = None
                for name in names_list:
                    # 检查是否为纯英文
                    if re.match(r'^[a-zA-Z0-9_-]+$', name):
                        entity_name = name.lower().replace(' ', '_').replace('-', '_')
                        break
                if not entity_name:
                    # 如果没有英文名，使用第一个名称
                    entity_name = friendly_name.lower().replace(' ', '_')
                
                entity_id = f"{domain}.{entity_name}"
                
                # 解析areas（可能是逗号分隔的多个区域）
                device_areas = [a.strip() for a in areas_str.split(',')] if areas_str else []
                primary_area = device_areas[0] if device_areas else ""
                
                # 解析attributes中的current_position（用于窗帘等）
                current_position = None
                if attributes_str:
                    position_match = re.search(r"current_position:\s*'?([^'\n]+)'?", attributes_str)
                    if position_match:
                        current_position = position_match.group(1).strip()
                
                # 构建设备对象
                device = {
                    "entity_id": entity_id,
                    "friendly_name": friendly_name,
                    "area": primary_area,
                    "state": state,
                    "device_type": domain
                }
                
                # 如果有position信息，添加到设备对象
                if current_position is not None:
                    device["position"] = current_position
                
                devices.append(device)
                
                # 收集所有区域
                for area in device_areas:
                    if area:
                        areas.add(area)
            
            print(f"[McpExecutor] Parsed {len(devices)} devices from live context")
            
        except Exception as e:
            print(f"[McpExecutor] Error parsing live context: {e}")
            import traceback
            traceback.print_exc()
        
        return {
            "devices": devices,
            "areas": list(areas)
        }
    
    def _parse_entities_dict(self, data: dict) -> Dict[str, Any]:
        """解析标准的entities字典格式（兼容方法）
        
        Args:
            data: 包含entities或devices字段的字典
            
        Returns:
            Dict: 包含devices和areas的字典
        """
        devices = []
        areas = set()
        
        entities = data.get("entities", data.get("devices", []))
        if isinstance(entities, list):
            for entity in entities:
                if isinstance(entity, dict):
                    device = {
                        "entity_id": entity.get("entity_id", ""),
                        "friendly_name": entity.get("friendly_name", entity.get("name", "")),
                        "area": entity.get("area", entity.get("area_name", "")),
                        "state": entity.get("state", ""),
                        "device_type": entity.get("device_type", entity.get("entity_id", "").split(".")[0] if "." in entity.get("entity_id", "") else "")
                    }
                    devices.append(device)
                    if device["area"]:
                        areas.add(device["area"])
        
        return {
            "devices": devices,
            "areas": list(areas)
        }

    
    def _enhance_goal_with_devices(self, task: UnifiedTask, original_goal: str) -> str:
        """将设备信息注入到goal中
        
        Args:
            task: 任务对象
            original_goal: 原始goal
            
        Returns:
            str: 增强后的goal
        """
        home_context = task.context.get("home_live_context")
        if not home_context:
            return original_goal
        
        devices = home_context.get("devices", [])
        if not devices:
            return original_goal
        
        # 构建设备信息摘要（最多显示10个设备）
        device_summary = []
        for device in devices[:10]:
            entity_id = device.get("entity_id", "")
            friendly_name = device.get("friendly_name", "")
            area = device.get("area", "")
            state = device.get("state", "")
            device_type = device.get("device_type", "")
            
            summary = f"- entity_id: {entity_id}"
            if friendly_name:
                summary += f"（友好名称：{friendly_name}"
                if area:
                    summary += f"，区域：{area}"
                if state:
                    summary += f"，当前状态：{state}"
                # 改动3：窗帘设备的position信息
                if device_type == "cover" and "position" in device:
                    position = device.get("position", "")
                    summary += f"，位置：{position}"
                summary += "）"
            
            device_summary.append(summary)
        
        # 改动3：添加参数使用规范
        enhanced_goal = f"""{original_goal}

【可用设备信息】
{chr(10).join(device_summary)}

【参数使用规范】
1. 必须使用设备列表中的实际entity_id，不得使用用户输入的模糊名称
2. 如需area参数，必须使用设备信息中的实际区域名（如"实验室"），禁止使用"当前位置"等占位符
3. 如需name参数，优先使用entity_id，其次使用友好名称
4. 窗帘类设备的position取值：0表示完全打开，100表示完全关闭

【执行目标】
根据用户描述"{original_goal}"，从设备列表中匹配最合适的设备，调用相应工具完成操作。"""
        
        return enhanced_goal
    
    # ================== 工具结果精准解析 ==================
    
    def _normalize_tool_result(self, result: Dict[str, Any], tool_name: str) -> Dict[str, Any]:
        """规范化工具执行结果，识别isError字段
        
        解析通义千问等LLM返回的isError字段，转换为统一的success/error格式。
        
        Args:
            result: 原始工具执行结果
            tool_name: 工具名称
            
        Returns:
            Dict: 规范化后的结果
        """
        try:
            # 如果已经是失败状态，直接返回
            if not result.get("success"):
                return result
            
            # 改动4：检查result字段中的isError（使用对象属性访问）
            result_data = result.get("result")
            if result_data:
                # 检查是否为CallToolResult对象
                if hasattr(result_data, 'isError') and result_data.isError:
                    error_msg = self._extract_error_message(result_data)
                    return {
                        "success": False,
                        "error": error_msg,
                        "raw_result": result
                    }
                # 如果是字典，检查isError键
                elif isinstance(result_data, dict) and result_data.get("isError"):
                    error_msg = self._extract_error_message(result_data)
                    return {
                        "success": False,
                        "error": error_msg,
                        "raw_result": result
                    }
            
            # 没有检测到isError，返回原结果
            return result
            
        except Exception as e:
            # 解析异常，返回原结果
            print(f"[McpExecutor] Error normalizing tool result: {e}")
            return result
    
    def _extract_error_message(self, error_data: Any) -> str:
        """从错误数据中提取错误消息
        
        Args:
            error_data: 包含isError的数据（可能是对象或字典）
            
        Returns:
            str: 错误消息
        """
        # 处理CallToolResult对象或字典    
        # 方式1: 如果是字典格式（已序列化的CallToolResult）
        if isinstance(error_data, dict):
            content = error_data.get('content')
            if content:
                if isinstance(content, list) and len(content) > 0:
                    first_content = content[0]
                    # 检查是否是TextContent对象
                    if hasattr(first_content, 'text'):
                        return first_content.text
                    # 或者是字典格式的TextContent
                    elif isinstance(first_content, dict) and 'text' in first_content:
                        text = first_content['text']
                        return text
        
        # 方式2: 如果是对象格式（未序列化的CallToolResult）
        if hasattr(error_data, 'content'):
            # 从Content对象中提取text
            content_list = error_data.content
            if content_list and len(content_list) > 0:
                first_content = content_list[0]
                if hasattr(first_content, 'text'):
                    return first_content.text
        
        # 方式3: 备用处理 - 尝试其他字段（向后兼容）
        if isinstance(error_data, dict):
            # 优先级1: message字段
            if "message" in error_data:
                return str(error_data["message"])
            
            # 优先级2: error字段
            if "error" in error_data:
                error_value = error_data["error"]
                if isinstance(error_value, str):
                    return error_value
                elif isinstance(error_value, dict):
                    return error_value.get("message", str(error_value))
            
            # 优先级3: 将整个字典转为字符串（截取前200字符）
            try:
                import json
                error_str = json.dumps(error_data, ensure_ascii=False, default=str)
                if len(error_str) > 200:
                    return error_str[:200] + "..."
                return error_str
            except:
                pass
        
        # 优先级4: 通用提示
        return "工具执行失败，但未返回详细错误信息"
    
    # ================== 任务完成度智能评估 ==================
    
    def _evaluate_completion(self, task: UnifiedTask, decision, result: Dict[str, Any]) -> CompletionJudgment:
        """评估任务是否完成
        
        基于三条规则：
        1. 查询类工具场景判断（区分纯查询与准备查询）
        2. 目标工具匹配完成
        3. 操作类工具状态验证完成
        
        Args:
            task: 任务对象
            decision: 路由决策
            result: 工具执行结果
            
        Returns:
            CompletionJudgment: 完成度判断结果
        """
        try:
            tool_name = decision.tool
            tool_type = self._classify_tool_type(tool_name)
            
            # 改动5：规则1 - 查询类工具场景判断（区分纯查询与准备查询）
            if tool_type == "query":
                task_intent_type = task.context.get("task_intent_type", "unknown")
                
                if task_intent_type == "query_only":
                    # 纯查询任务，查询完成即任务完成
                    return CompletionJudgment(
                        completed=True,
                        confidence=0.95,
                        reason="query_task_completed",
                        analysis=f"纯查询任务完成，工具{tool_name}已成功获取数据"
                    )
                else:
                    # 操作任务的准备阶段查询，需要继续执行
                    return CompletionJudgment(
                        completed=False,
                        confidence=0.5,
                        reason="query_for_preparation",
                        analysis=f"查询工具{tool_name}执行成功，但这是为后续操作准备数据，任务未完成"
                    )
            
            # 规则2：目标工具匹配完成
            user_requested_tool = task.context.get("user_requested_tool")
            if user_requested_tool and tool_name == user_requested_tool:
                return CompletionJudgment(
                    completed=True,
                    confidence=0.95,
                    reason="target_tool_executed",
                    analysis=f"目标工具{tool_name}已成功执行"
                )
            
            # 规则3：操作类工具状态验证
            if tool_type == "action":
                # 检查返回结果中是否包含状态验证
                content = result.get("content") or result.get("result", {})
                
                # 对于家居控制工具，检查状态
                if "Turn" in tool_name or "Set" in tool_name:
                    state = None
                    if isinstance(content, dict):
                        state = content.get("state")
                    
                    if state:
                        # 有状态验证，高置信度完成
                        expected_state = self._infer_expected_state(tool_name)
                        if expected_state and state == expected_state:
                            return CompletionJudgment(
                                completed=True,
                                confidence=0.95,
                                reason="state_verified",
                                analysis=f"操作工具{tool_name}执行成功，状态已验证为{state}"
                            )
                        else:
                            return CompletionJudgment(
                                completed=True,
                                confidence=0.85,
                                reason="action_completed",
                                analysis=f"操作工具{tool_name}执行成功，当前状态为{state}"
                            )
                    else:
                        # 无状态验证，中等置信度
                        return CompletionJudgment(
                            completed=True,
                            confidence=0.7,
                            reason="action_completed_no_state",
                            analysis=f"操作工具{tool_name}执行成功，但未返回状态验证"
                        )
            
            # 默认：中等置信度，认为可能需要继续
            return CompletionJudgment(
                completed=False,
                confidence=0.5,
                reason="may_need_more_steps",
                analysis=f"工具{tool_name}执行成功，但可能需要后续操作"
            )
            
        except Exception as e:
            # 评估失败，默认未完成
            print(f"[McpExecutor] Error evaluating completion: {e}")
            return CompletionJudgment(
                completed=False,
                confidence=0.0,
                reason="evaluation_error",
                analysis=f"完成度评估失败: {str(e)}"
            )
    
    # ================== 计划驱动模式方法 ==================
    
    async def _generate_plan(self, task: UnifiedTask, goal: str, context: Dict[str, Any]) -> TaskPlan:
        """生成任务执行计划
        
        调用LLM生成完整的执行步骤列表
        
        Args:
            task: 任务对象
            goal: 用户目标
            context: 环境上下文
            
        Returns:
            TaskPlan: 生成的执行计划
        """
        try:
            self._log(task, "Generating execution plan...")
            
            # 获取可用工具列表（从 Router 获取）
            available_tools = await self._get_available_tools()
            
            # 构建 Prompt
            plan_prompt = self._build_plan_generation_prompt(goal, context, available_tools)
            
            # 调用 Router 的 LLM 生成计划
            # 这里假设 router 有 generate_plan 方法，如果没有则需要直接调用 LLM
            if hasattr(self.router, 'generate_plan'):
                plan_data = await self.router.generate_plan(plan_prompt)
            else:
                # 备用方案：直接调用 LLM 客户端
                plan_data = await self._call_llm_for_plan(plan_prompt)
            
            # 解析计划数据
            plan = self._parse_plan_data(plan_data)
            
            # 验证计划
            if len(plan.steps) == 0:
                self._log(task, "Generated plan has no steps, creating default plan", "WARNING")
                # 创建默认计划
                plan.steps.append(PlanStep(
                    description=goal,
                    expected_tool=None
                ))
            
            if len(plan.steps) > self.max_plan_steps:
                self._log(task, f"Plan has too many steps ({len(plan.steps)}), truncating to {self.max_plan_steps}", "WARNING")
                plan.steps = plan.steps[:self.max_plan_steps]
            
            self._log(task, f"Plan generated with {len(plan.steps)} steps")
            
            # 记录到历史
            task.history.append({
                "timestamp": datetime.now().timestamp(),
                "event": "plan_generated",
                "steps": [step.to_dict() for step in plan.steps]
            })
            
            return plan
            
        except Exception as e:
            self._log(task, f"Error generating plan: {e}", "ERROR")
            # 返回默认计划
            plan = TaskPlan()
            plan.steps.append(PlanStep(
                description=goal,
                expected_tool=None
            ))
            return plan
    
    def _build_plan_generation_prompt(self, goal: str, context: Dict[str, Any], available_tools: list) -> str:
        """构建计划生成的 Prompt
        
        Args:
            goal: 用户目标
            context: 环境上下文
            available_tools: 可用工具列表
            
        Returns:
            str: Prompt 文本
        """
        tools_summary = "\n".join([f"- {tool.get('name', 'Unknown')}: {tool.get('description', '')}" for tool in available_tools[:20]])
        
        prompt = f"""你是一个任务规划助手。根据用户目标和可用工具，生成一个详细的执行计划。

**用户目标**：
{goal}

**可用工具**：
{tools_summary}

**计划要求**：
1. 生成 3-8 个执行步骤
2. 步骤应按逻辑顺序排列（如：先查询后操作）
3. 每个步骤包含：
   - description: 步骤描述（自然语言）
   - expected_tool: 预期使用的工具名称（可选）
4. 步骤粒度适中，避免过细或过粗

**输出格式** (必须为 JSON)：
```json
{{
  "steps": [
    {{
      "description": "步骤1描述",
      "expected_tool": "工具名称或null"
    }},
    {{
      "description": "步骤2描述",
      "expected_tool": "工具名称或null"
    }}
  ]
}}
```

请生成计划：
"""
        return prompt
    
    async def _get_available_tools(self) -> list:
        """获取可用工具列表
        
        Returns:
            list: 工具列表
        """
        try:
            # 尝试从 router 获取工具列表
            if hasattr(self.router, 'get_available_tools'):
                return await self.router.get_available_tools()
            
            # 备用：从 connections 收集工具
            tools = []
            for server_id, connection in self.connections.items():
                if hasattr(connection, 'list_tools'):
                    server_tools = await connection.list_tools()
                    if server_tools:
                        for tool in server_tools:
                            tools.append({
                                "name": tool.get("name", ""),
                                "description": tool.get("description", ""),
                                "server_id": server_id
                            })
            return tools
        except Exception as e:
            print(f"[McpExecutor] Error getting available tools: {e}")
            return []
    
    async def _call_llm_for_plan(self, prompt: str) -> Dict[str, Any]:
        """调用 LLM 生成计划
        
        Args:
            prompt: Prompt 文本
            
        Returns:
            Dict[str, Any]: LLM 返回的计划数据
        """
        try:
            # 尝试从 router 获取 LLM 客户端
            if hasattr(self.router, 'llm_client'):
                response = await self.router.llm_client.chat_completion(
                    model="gpt-4",
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"}
                )
                content = response.get("choices", [{}])[0].get("message", {}).get("content", "{}")
                return json.loads(content)
            else:
                # 如果没有 LLM 客户端，返回空计划
                return {"steps": []}
        except Exception as e:
            print(f"[McpExecutor] Error calling LLM for plan: {e}")
            return {"steps": []}
    
    def _parse_plan_data(self, plan_data: Dict[str, Any]) -> TaskPlan:
        """解析计划数据
        
        Args:
            plan_data: LLM 返回的计划数据
            
        Returns:
            TaskPlan: 解析后的计划对象
        """
        plan = TaskPlan()
        
        steps_data = plan_data.get("steps", [])
        for step_data in steps_data:
            step = PlanStep(
                description=step_data.get("description", ""),
                expected_tool=step_data.get("expected_tool")
            )
            plan.steps.append(step)
        
        return plan
    
    async def _verify_plan(self, task: UnifiedTask, current_step: PlanStep, execution_result: Dict[str, Any]) -> bool:
        """验证计划是否需要修订
        
        Args:
            task: 任务对象
            current_step: 当前执行的步骤
            execution_result: 执行结果
            
        Returns:
            bool: 是否需要修订计划
        """
        try:
            # 规则验证模式
            if self.plan_verification_mode == "rule":
                return self._rule_based_verification(task, current_step, execution_result)
            # LLM 验证模式
            elif self.plan_verification_mode == "llm":
                return await self._llm_based_verification(task, current_step, execution_result)
            else:
                return False
        except Exception as e:
            self._log(task, f"Error verifying plan: {e}", "WARNING")
            return False
    
    def _rule_based_verification(self, task: UnifiedTask, current_step: PlanStep, execution_result: Dict[str, Any]) -> bool:
        """基于规则的计划验证
        
        Args:
            task: 任务对象
            current_step: 当前执行的步骤
            execution_result: 执行结果
            
        Returns:
            bool: 是否需要修订计划
        """
        # 规割1：如果已达到最大修订次数，不再修订
        if task.plan and task.plan.revision_count >= self.max_plan_revisions:
            self._log(task, "Max plan revisions reached, no more revisions")
            return False
        
        # 规割2：如果执行失败且错误为资源未找到，需要修订
        if not execution_result.get("success"):
            error_info = str(execution_result.get("error", "")).lower()
            if any(keyword in error_info for keyword in ["not found", "does not exist", "unknown"]):
                self._log(task, "Resource not found error detected, plan revision needed")
                return True
        
        # 默认不需要修订
        return False
    
    async def _llm_based_verification(self, task: UnifiedTask, current_step: PlanStep, execution_result: Dict[str, Any]) -> bool:
        """基于 LLM 的计划验证
        
        Args:
            task: 任务对象
            current_step: 当前执行的步骤
            execution_result: 执行结果
            
        Returns:
            bool: 是否需要修订计划
        """
        # TODO: 实现 LLM 验证逻辑
        # 这里需要调用 LLM 分析执行结果是否符合计划预期
        return False
    
    async def _revise_plan(self, task: UnifiedTask, reason: str) -> None:
        """修订执行计划
        
        Args:
            task: 任务对象
            reason: 修订原因
        """
        try:
            self._log(task, f"Revising plan, reason: {reason}")
            
            if not task.plan:
                self._log(task, "No plan to revise", "WARNING")
                return
            
            # 记录修订前的计划
            old_plan = task.plan.to_dict()
            
            # 获取当前进度和剩余步骤
            current_index = task.plan.current_step_index
            remaining_steps = task.plan.steps[current_index:]
            
            # 构建修订 Prompt
            revision_prompt = self._build_plan_revision_prompt(
                task.execution_data.get("user_intent", task.execution_data.get("goal", "")),
                task.plan,
                reason,
                task.context
            )
            
            # 调用 LLM 生成新计划
            if hasattr(self.router, 'revise_plan'):
                new_plan_data = await self.router.revise_plan(revision_prompt)
            else:
                new_plan_data = await self._call_llm_for_plan(revision_prompt)
            
            # 解析新计划
            new_steps_data = new_plan_data.get("steps", [])
            
            # 标记受影响的步骤为 SKIPPED
            for step in remaining_steps:
                if step.status == PlanStepStatus.PENDING:
                    step.status = PlanStepStatus.SKIPPED
                    step.skip_reason = f"Plan revised: {reason}"
            
            # 添加新步骤
            for step_data in new_steps_data:
                new_step = PlanStep(
                    description=step_data.get("description", ""),
                    expected_tool=step_data.get("expected_tool")
                )
                task.plan.steps.append(new_step)
            
            # 增加修订计数
            task.plan.increment_revision()
            
            # 记录修订历史
            task.history.append({
                "timestamp": datetime.now().timestamp(),
                "event": "plan_revised",
                "reason": reason,
                "old_plan": old_plan,
                "new_plan": task.plan.to_dict(),
                "revision_count": task.plan.revision_count
            })
            
            self._log(task, f"Plan revised (revision #{task.plan.revision_count}), {len(new_steps_data)} new steps added")
            
        except Exception as e:
            self._log(task, f"Error revising plan: {e}", "ERROR")
    
    def _build_plan_revision_prompt(self, user_intent: str, current_plan: TaskPlan, reason: str, context: Dict[str, Any]) -> str:
        """构建计划修订的 Prompt
        
        Args:
            user_intent: 用户原始意图
            current_plan: 当前计划
            reason: 修订原因
            context: 环境上下文
            
        Returns:
            str: Prompt 文本
        """
        completed_steps = [
            f"- {step.description} [{step.status.value}]"
            for step in current_plan.steps[:current_plan.current_step_index]
        ]
        
        prompt = f"""你是一个任务规划助手。原有计划需要修订，请生成新的执行步骤。

**用户原始意图**：
{user_intent}

**已完成的步骤**：
{chr(10).join(completed_steps) if completed_steps else "无"}

**修订原因**：
{reason}

**要求**：
1. 生成剩余的执行步骤（考虑已完成的步骤）
2. 步骤数量在 1-5 个
3. 步骤应解决修订原因中提到的问题

**输出格式** (必须为 JSON)：
```json
{{
  "steps": [
    {{
      "description": "步骤描述",
      "expected_tool": "工具名称或null"
    }}
  ]
}}
```

请生成修订后的计划：
"""
        return prompt
    
    def _is_plan_completed(self, plan: Optional[TaskPlan]) -> bool:
        """检查计划是否全部完成
        
        Args:
            plan: 任务计划
            
        Returns:
            bool: 是否全部完成
        """
        if not plan:
            return False
        return plan.is_completed()