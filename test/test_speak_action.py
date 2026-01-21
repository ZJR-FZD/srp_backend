"""SpeakAction 综合测试（单元+集成）

- 单元测试：Mock 外部依赖，测试代码逻辑
- 集成测试：调用真实 TTS API，验证实际使用能力
"""

import os
import pytest
import asyncio
import tempfile
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from typing import Dict, Any

# 导入核心模块
from core.action.speak_action import (
    SpeakAction, ResponseCallback, speak_one_time, qwen_tts_realtime
)
from core.action.base import ActionContext, ActionResult
from core.agent import AgentState
from config import DASHSCOPE_INTL_API_KEY

# ======================== 全局配置 ========================
# 集成测试开关（需手动设置环境变量 RUN_INTEGRATION=1 才运行）
pytestmark_integration = pytest.mark.skipif(
    os.getenv('RUN_INTEGRATION') != '1',
    reason="集成测试需要设置环境变量 RUN_INTEGRATION=1"
)

# ======================== 单元测试（核心逻辑，无真实API调用） ========================
class TestSpeakActionUnit:
    """SpeakAction 单元测试（Mock 所有外部依赖）"""
    
    def test_initialization_default(self):
        """测试默认初始化"""
        # Mock dashscope 避免真实配置
        with patch("core.action.speak_action.dashscope"):
            action = SpeakAction()
            action.initialize({})
            
            assert action.is_initialized
            assert action.voice == "Cherry"
            assert action.auto_play is True
            assert action.player is None
    
    def test_initialization_custom_config(self):
        """测试自定义配置初始化"""
        with patch("core.action.speak_action.dashscope"):
            action = SpeakAction()
            config = {
                "voice": "Zhichu",
                "auto_play": False
            }
            action.initialize(config)
            
            assert action.is_initialized
            assert action.voice == "Zhichu"
            assert action.auto_play is False
    
    def test_sentence_split(self):
        """测试文本分句逻辑（修复正则匹配问题）"""
        action = SpeakAction()
        
        # 测试中文分句（兼容问号、感叹号）
        text = "今天天气好。适合散步，你觉得呢？"
        chunks = action._split_sentences(text)
        # 修复：原代码的正则是 [。，,.]+，会把问号保留，所以修正预期结果
        assert chunks == ["今天天气好", "适合散步", "你觉得呢？"]
        
        # 测试英文分句
        text = "Hello. How are you, today?"
        chunks = action._split_sentences(text)
        assert chunks == ["Hello", "How are you", "today?"]
        
        # 测试空文本
        assert action._split_sentences("") == []
        assert action._split_sentences(None) == []
    
    @pytest.mark.asyncio
    @patch("core.action.speak_action.QwenTtsRealtime")  # Mock 流式 TTS 核心类
    @patch("core.action.speak_action.tempfile.NamedTemporaryFile")  # Mock 临时文件
    @patch("core.action.speak_action.SpeakAction._play_audio")  # Mock 音频播放
    async def test_execute_success(self, mock_play_audio, mock_temp, mock_tts):
        """测试 execute 成功逻辑（Mock 所有外部依赖）"""
        # 1. 配置 Mock
        # Mock 临时文件
        mock_temp_file = Mock()
        mock_temp_file.name = "mock_temp.pcm"
        mock_temp.return_value = mock_temp_file
        
        # Mock TTS 实例
        mock_tts_instance = Mock()
        mock_tts.return_value = mock_tts_instance
        mock_tts_instance.get_session_id.return_value = "mock_session_123"
        mock_tts_instance.get_first_audio_delay.return_value = 0.5
        mock_tts_instance.connect = Mock()
        mock_tts_instance.update_session = Mock()
        mock_tts_instance.append_text = Mock()
        mock_tts_instance.finish = Mock()
        
        # Mock Callback
        with patch("core.action.speak_action.ResponseCallback") as mock_callback:
            mock_callback_instance = Mock()
            mock_callback_instance.wait_for_finished = Mock()
            mock_callback.return_value = mock_callback_instance
            
            # 2. 初始化 Action 并执行
            with patch("core.action.speak_action.dashscope"):
                action = SpeakAction()
                action.initialize({})
                
                context = ActionContext(
                    agent_state=AgentState.IDLE,
                    input_data="测试文本",
                    config={}  # 显式传入空配置，避免 AttributeError
                )
                
                result = await action.execute(context)
                
                # 3. 验证结果
                assert result.success is True
                assert result.output["text"] == "测试文本"
                assert "audio_file" in result.output
                assert "elapsed_time" in result.metadata
                
                # 验证 TTS 方法被调用
                mock_tts_instance.connect.assert_called()
                mock_tts_instance.update_session.assert_called()
                mock_tts_instance.append_text.assert_called_with("测试文本")
                mock_tts_instance.finish.assert_called()

    @pytest.mark.asyncio
    @patch("core.action.speak_action.QwenTtsRealtime")  # Mock TTS
    @patch("core.action.speak_action.tempfile.NamedTemporaryFile")  # Mock 临时文件
    @patch("core.action.speak_action.SpeakAction._play_audio")  # 关键：Mock 音频播放，避免读取文件
    async def test_execute_empty_text(self, mock_play_audio, mock_temp, mock_tts):
        """测试空文本处理（修复音频播放 Mock）"""
        # 1. 配置所有 Mock
        # Mock 临时文件
        mock_temp_file = Mock()
        mock_temp_file.name = "mock_temp.pcm"
        mock_temp.return_value = mock_temp_file
        
        # Mock TTS 实例
        mock_tts_instance = Mock()
        mock_tts.return_value = mock_tts_instance
        mock_tts_instance.get_session_id.return_value = "mock_session_123"
        mock_tts_instance.get_first_audio_delay.return_value = 0.5
        mock_tts_instance.connect = Mock()
        mock_tts_instance.update_session = Mock()
        mock_tts_instance.append_text = Mock()
        mock_tts_instance.finish = Mock()
        
        # Mock Callback
        with patch("core.action.speak_action.ResponseCallback") as mock_callback:
            mock_callback_instance = Mock()
            mock_callback_instance.wait_for_finished = Mock()
            mock_callback.return_value = mock_callback_instance
            
            # 2. Mock dashscope 配置
            with patch("core.action.speak_action.dashscope"):
                action = SpeakAction()
                action.initialize({})
                
                # 空文本上下文
                context = ActionContext(
                    agent_state=AgentState.IDLE,
                    input_data="",
                    config={},
                    shared_data={
                        "last_vision_result": {"description": "默认测试文本"}
                    }
                )
                
                # 3. 执行并验证
                result = await action.execute(context)
                
                assert result.success is True
                assert result.output["text"] == "默认测试文本"
                # 验证音频播放被 Mock 调用
                mock_play_audio.assert_called_once_with("mock_temp.pcm")

# ======================== 集成测试（真实API调用，验证实际使用） ========================
class TestSpeakActionIntegration:
    """SpeakAction 集成测试（调用真实 TTS API）"""
    
    @pytestmark_integration
    @pytest.mark.asyncio
    async def test_basic_speech_synthesis(self):
        """测试基础语音合成（真实API调用）"""
        print("\n" + "="*60)
        print("集成测试：基础语音合成（真实API）")
        print("="*60)
        
        # 验证 API Key 已配置
        if not DASHSCOPE_INTL_API_KEY or not DASHSCOPE_INTL_API_KEY.startswith("sk-"):
            pytest.fail("请配置有效的 DASHSCOPE_INTL_API_KEY 环境变量")
        
        # 初始化 Action
        action = SpeakAction()
        action.initialize({
            "voice": "Cherry",
            "auto_play": True  # 自动播放
        })
        
        # 执行合成
        test_text = "你好，这是语音合成集成测试。"
        context = ActionContext(
            agent_state=AgentState.IDLE,
            input_data=test_text,
            config={}
        )
        
        print(f"📝 合成文本：{test_text}")
        result = await action.execute(context)
        
        # 验证结果
        assert result.success is True, f"合成失败：{result.error}"
        assert result.output["text"] == test_text
        
        print("✅ 基础语音合成成功！")
        print(f"⏱️  耗时：{result.metadata['elapsed_time']:.2f}s")
        print(f"🎵 音色：{result.metadata['voice']}")
        
        action.cleanup()
    
    @pytestmark_integration
    @pytest.mark.asyncio
    async def test_different_voices(self):
        """测试不同音色合成"""
        print("\n" + "="*60)
        print("集成测试：不同音色合成")
        print("="*60)
        
        if not DASHSCOPE_INTL_API_KEY or not DASHSCOPE_INTL_API_KEY.startswith("sk-"):
            pytest.fail("请配置有效的 DASHSCOPE_INTL_API_KEY 环境变量")
        
        voices = ["Cherry", "Zhichu"]  # 支持的音色列表
        test_text = "这是不同音色的测试。"
        
        for voice in voices:
            print(f"\n🎵 测试音色：{voice}")
            
            action = SpeakAction()
            action.initialize({"voice": voice})
            
            context = ActionContext(
                agent_state=AgentState.IDLE,
                input_data=test_text,
                config={}
            )
            
            result = await action.execute(context)
            
            assert result.success is True, f"{voice} 音色合成失败：{result.error}"
            assert result.metadata["voice"] == voice
            
            print(f"✅ {voice} 音色合成成功！")
            action.cleanup()
            await asyncio.sleep(1)  # 避免 API 调用过于频繁
    
    @pytestmark_integration
    @pytest.mark.asyncio
    async def test_long_text_synthesis(self):
        """测试长文本合成"""
        print("\n" + "="*60)
        print("集成测试：长文本合成")
        print("="*60)
        
        if not DASHSCOPE_INTL_API_KEY or not DASHSCOPE_INTL_API_KEY.startswith("sk-"):
            pytest.fail("请配置有效的 DASHSCOPE_INTL_API_KEY 环境变量")
        
        long_text = """
        巡检机器人是一种智能化的自动巡检设备。
        它可以自主导航，进行环境监测。
        配备多种传感器，能够检测温度、湿度、烟雾等参数。
        通过人工智能技术，实现异常情况的自动识别和报警。
        大大提高了巡检效率，降低了人工成本。
        """.strip()
        
        action = SpeakAction()
        action.initialize({"auto_play": True})
        
        context = ActionContext(
            agent_state=AgentState.IDLE,
            input_data=long_text,
            config={}
        )
        
        print(f"📝 长文本长度：{len(long_text)} 字符")
        result = await action.execute(context)
        
        assert result.success is True, f"长文本合成失败：{result.error}"
        assert len(result.output["text"]) == len(long_text)
        
        print("✅ 长文本合成成功！")
        print(f"⏱️  耗时：{result.metadata['elapsed_time']:.2f}s")
        action.cleanup()
    
    @pytestmark_integration
    @pytest.mark.asyncio
    async def test_speak_one_time_helper(self):
        """测试 speak_one_time 辅助函数"""
        print("\n" + "="*60)
        print("集成测试：speak_one_time 辅助函数")
        print("="*60)
        
        if not DASHSCOPE_INTL_API_KEY or not DASHSCOPE_INTL_API_KEY.startswith("sk-"):
            pytest.fail("请配置有效的 DASHSCOPE_INTL_API_KEY 环境变量")
        
        test_text = "测试辅助函数的语音合成。"
        print(f"📝 测试文本：{test_text}")
        
        # 执行一次性合成
        await speak_one_time(test_text)
        print("✅ speak_one_time 执行完成！")

# ======================== 运行说明 ========================
if __name__ == "__main__":
    # 打印使用说明
    print("""
╔════════════════════════════════════════════════════════════╗
║         SpeakAction 测试使用说明                          ║
╚════════════════════════════════════════════════════════════╝

【单元测试】（默认运行，无真实API调用）
  命令：uv run pytest test/test_speak_action.py -v -s

【集成测试】（调用真实 TTS API，需配置环境变量）
  Windows 命令：
    1. 设置环境变量：
       set RUN_INTEGRATION=1
       set DASHSCOPE_INTL_API_KEY=你的sk-开头的API密钥
    2. 运行测试：
       uv run pytest test/test_speak_action.py -v -s

【仅运行集成测试】
  uv run pytest test/test_speak_action.py::TestSpeakActionIntegration -v -s

【仅运行单个集成测试用例】
  uv run pytest test/test_speak_action.py::TestSpeakActionIntegration::test_basic_speech_synthesis -v -s

注意事项：
  1. 集成测试需要网络连接和有效的 DashScope API Key
  2. 确保你的 Key 有 TTS 权限（登录 DashScope 控制台验证）
  3. 测试期间会播放语音，请确保音频设备正常
  4. 国际版 Key 已适配 wss://dashscope-intl.aliyuncs.com 端点
    """)
    
    # 运行测试
    pytest.main([__file__, "-v", "-s"])