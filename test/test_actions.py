# test/test_actions.py
"""测试 Action 机制"""

import pytest
import asyncio
from core.action import (
    BaseAction,
    ActionContext,
    ActionResult,
    ActionMetadata,
    WatchAction,
    SpeakAction,
    AlertAction,
)
from core.agent import RobotAgent, AgentState


class TestActionBase:
    """测试 Action 基类"""
    
    def test_action_metadata(self):
        """测试 ActionMetadata 数据结构"""
        metadata = ActionMetadata(
            name="test_action",
            version="1.0.0",
            description="Test action",
            dependencies=["dep1"],
            capabilities=["cap1"]
        )
        
        assert metadata.name == "test_action"
        assert metadata.version == "1.0.0"
        assert "dep1" in metadata.dependencies
        assert "cap1" in metadata.capabilities
    
    def test_action_context(self):
        """测试 ActionContext 数据结构"""
        context = ActionContext(
            agent_state=AgentState.IDLE,
            input_data="test input",
            shared_data={"key": "value"},
            config={"param": "value"}
        )
        
        assert context.agent_state == AgentState.IDLE
        assert context.input_data == "test input"
        assert context.shared_data["key"] == "value"
        assert context.config["param"] == "value"
    
    def test_action_result(self):
        """测试 ActionResult 数据结构"""
        result = ActionResult(
            success=True,
            output={"result": "data"},
            metadata={"time": 1.0}
        )
        
        assert result.success is True
        assert result.output["result"] == "data"
        assert result.metadata["time"] == 1.0

class TestSpeakAction:
    """测试 SpeakAction"""
    
    def test_speak_action_metadata(self):
        """测试 SpeakAction 元信息"""
        action = SpeakAction()
        metadata = action.get_metadata()
        
        assert metadata.name == "speak"
        assert "tts" in metadata.capabilities
    
    def test_speak_action_initialization(self):
        """测试 SpeakAction 初始化"""
        action = SpeakAction()
        action.initialize({})
        
        assert action.is_initialized
    
    @pytest.mark.asyncio
    async def test_speak_action_execute_mock(self):
        """测试 SpeakAction 执行（Mock 模式）"""
        action = SpeakAction()
        action.initialize({})
        
        context = ActionContext(
            agent_state=AgentState.IDLE,
            input_data="测试文本"
        )
        
        result = await action.execute(context)
        
        # Mock 模式应该成功
        assert result.success
        assert "audio_bytes" in result.output
        assert result.output["text"] == "测试文本"

class TestRobotAgentActions:
    """测试 RobotAgent 的 Action 机制"""
    
    def test_agent_initialization(self):
        """测试 Agent 初始化"""
        agent = RobotAgent()
        
        assert agent.state == AgentState.IDLE
        assert isinstance(agent.actions, dict)
        assert len(agent.actions) == 0
    
    def test_register_action(self):
        """测试注册 Action"""
        agent = RobotAgent()
        action = WatchAction()
        
        agent.register_action("watch", action, {})
        
        assert "watch" in agent.actions
        assert "watch" in agent.action_metadata
        assert agent.actions["watch"].is_initialized
    
    def test_unregister_action(self):
        """测试注销 Action"""
        agent = RobotAgent()
        action = WatchAction()
        
        agent.register_action("watch", action, {})
        agent.unregister_action("watch")
        
        assert "watch" not in agent.actions
        assert "watch" not in agent.action_metadata
    
    @pytest.mark.asyncio
    async def test_execute_action(self):
        """测试执行 Action"""
        agent = RobotAgent()
        action = WatchAction()
        
        agent.register_action("watch", action, {})
        
        result = await agent.execute_action("watch")
        
        assert result.success
        assert result.output is not None
    
    @pytest.mark.asyncio
    async def test_execute_action_not_found(self):
        """测试执行不存在的 Action"""
        agent = RobotAgent()
        
        result = await agent.execute_action("nonexistent")
        
        assert not result.success
        assert result.error is not None
    
    @pytest.mark.asyncio
    async def test_execute_action_chain(self):
        """测试执行 Action 链"""
        agent = RobotAgent()
        
        # 注册多个 Actions
        agent.register_action("speak", SpeakAction(), {})
        
        # 执行 Action 链
        results = await agent.execute_action_chain(["speak"])

        assert len(results) == 1
        assert results[0].success  # speak action

    @pytest.mark.asyncio
    async def test_shared_context(self):
        """测试共享上下文传递"""
        agent = RobotAgent()
        
        # 注册 watch action
        agent.register_action("watch", WatchAction(), {})
        
        # 执行 watch action
        result = await agent.execute_action("watch")
        
        # 检查共享上下文是否被更新
        assert "last_vision_result" in agent.shared_context
        assert agent.shared_context["last_vision_result"] == result.output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
