"""ListenAction 集成测试 - 真实录音和识别

这个测试会使用真实的麦克风和 ASR 服务
需要设置环境变量 RUN_INTEGRATION=1 才会运行
"""

import os
import pytest
import asyncio

from core.action.listen_action import ListenAction, listen_one_time
from core.action.base import ActionContext
from core.agent import AgentState


# 只在设置了 RUN_INTEGRATION 环境变量时运行
pytestmark = pytest.mark.skipif(
    os.getenv('RUN_INTEGRATION') != '1',
    reason="集成测试需要设置环境变量 RUN_INTEGRATION=1"
)


class TestListenActionIntegration:
    """ListenAction 集成测试"""
    
    @pytest.mark.asyncio
    async def test_real_recording_short(self):
        """测试真实录音 - 短时间（3秒）
        
        运行此测试时，请在 3 秒内说一句话，例如：
        "你好，这是一个测试"
        """
        print("\n" + "="*60)
        print("集成测试：真实录音 3 秒")
        print("请在听到提示后开始说话...")
        print("="*60)
        
        action = ListenAction()
        action.initialize({
            "sample_rate": 16000,
            # "device": "hw:0,0"  # 如果需要指定录音设备，取消注释
        })
        
        context = ActionContext(
            agent_state=AgentState.IDLE,
            input_data=3.0  # 录音 3 秒
        )
        
        print("\n🎤 开始录音，请说话...")
        result = await action.execute(context)
        
        # 验证结果
        assert result.success is True, f"录音失败: {result.error}"
        
        recognized_text = result.output.get("text", "")
        print(f"\n✅ 识别结果: {recognized_text}")
        print(f"⏱️  耗时: {result.metadata['elapsed_time']:.2f}s")
        print(f"📊 句子片段: {result.output.get('segments', [])}")
        
        # 验证识别到了内容（至少不是空的）
        assert len(recognized_text) > 0, "未识别到任何内容，请检查麦克风"
        
        action.cleanup()
    
    @pytest.mark.asyncio
    async def test_real_recording_medium(self):
        """测试真实录音 - 中等时间（5秒）
        
        运行此测试时，可以说一段较长的话，例如：
        "今天天气很好，我正在测试语音识别功能"
        """
        print("\n" + "="*60)
        print("集成测试：真实录音 5 秒")
        print("请在听到提示后说一段话...")
        print("="*60)
        
        action = ListenAction()
        action.initialize({})
        
        context = ActionContext(
            agent_state=AgentState.IDLE,
            input_data=5.0  # 录音 5 秒
        )
        
        print("\n🎤 开始录音，请说话...")
        result = await action.execute(context)
        
        assert result.success is True, f"录音失败: {result.error}"
        
        recognized_text = result.output.get("text", "")
        print(f"\n✅ 识别结果: {recognized_text}")
        print(f"⏱️  耗时: {result.metadata['elapsed_time']:.2f}s")
        
        assert len(recognized_text) > 0, "未识别到任何内容"
        
        action.cleanup()
    
    @pytest.mark.asyncio
    async def test_listen_one_time_helper(self):
        """测试 listen_one_time 辅助函数
        
        这是一个快捷测试函数，运行时请说话
        """
        print("\n" + "="*60)
        print("集成测试：使用 listen_one_time 函数")
        print("请在 3 秒内说话...")
        print("="*60)
        
        print("\n🎤 开始录音...")
        text = await listen_one_time(duration=3.0)
        
        print(f"\n✅ 识别结果: {text}")
        
        assert isinstance(text, str), "返回值应该是字符串"
        assert len(text) > 0, "未识别到任何内容"
    
    @pytest.mark.asyncio
    async def test_silent_audio(self):
        """测试静音情况
        
        运行此测试时，保持安静，不要说话
        """
        print("\n" + "="*60)
        print("集成测试：静音测试")
        print("请保持安静，不要说话...")
        print("="*60)
        
        action = ListenAction()
        action.initialize({})
        
        context = ActionContext(
            agent_state=AgentState.IDLE,
            input_data=3.0
        )
        
        print("\n🤫 录音中，请保持安静...")
        result = await action.execute(context)
        
        assert result.success is True, f"录音失败: {result.error}"
        
        recognized_text = result.output.get("text", "")
        print(f"\n✅ 识别结果: '{recognized_text}' (应该为空或很少)")
        
        # 静音情况下，识别结果应该很短或为空
        print(f"📏 文本长度: {len(recognized_text)} 字符")
        
        action.cleanup()
    
    @pytest.mark.asyncio
    async def test_multiple_sentences(self):
        """测试多句话识别
        
        运行此测试时，说多句话，例如：
        "第一句话。第二句话。第三句话。"
        """
        print("\n" + "="*60)
        print("集成测试：多句话识别（10秒）")
        print("请说多句话，中间可以停顿...")
        print("="*60)
        
        action = ListenAction()
        action.initialize({})
        
        context = ActionContext(
            agent_state=AgentState.IDLE,
            input_data=10.0  # 录音 10 秒
        )
        
        print("\n🎤 开始录音，请说多句话...")
        result = await action.execute(context)
        
        assert result.success is True, f"录音失败: {result.error}"
        
        recognized_text = result.output.get("text", "")
        segments = result.output.get("segments", [])
        
        print(f"\n✅ 完整识别结果: {recognized_text}")
        print(f"📝 句子片段数量: {len(segments)}")
        for i, segment in enumerate(segments, 1):
            print(f"   {i}. {segment}")
        
        assert len(recognized_text) > 0, "未识别到任何内容"
        
        action.cleanup()
    
    @pytest.mark.asyncio
    async def test_with_custom_device(self):
        """测试使用自定义录音设备
        
        如果你有多个麦克风，可以测试指定设备
        """
        print("\n" + "="*60)
        print("集成测试：自定义录音设备")
        print("="*60)
        
        # 列出可用的 ALSA 设备（仅在 Linux 上有效）
        try:
            import subprocess
            result = subprocess.run(['arecord', '-l'], capture_output=True, text=True)
            print("\n可用的录音设备:")
            print(result.stdout)
        except:
            print("\n无法列出设备（可能不在 Linux 系统上）")
        
        action = ListenAction()
        action.initialize({
            "device": None  # 使用默认设备，如果需要指定设备，改为 "hw:0,0" 等
        })
        
        context = ActionContext(
            agent_state=AgentState.IDLE,
            input_data=3.0
        )
        
        print("\n🎤 开始录音...")
        result = await action.execute(context)
        
        assert result.success is True, f"录音失败: {result.error}"
        
        print(f"\n✅ 识别结果: {result.output.get('text', '')}")
        
        action.cleanup()


class TestListenActionRobustness:
    """ListenAction 健壮性测试"""
    
    @pytest.mark.asyncio
    async def test_rapid_consecutive_calls(self):
        """测试快速连续调用
        
        模拟实际使用场景中的连续语音识别
        """
        print("\n" + "="*60)
        print("集成测试：连续3次录音（每次2秒）")
        print("请连续说话...")
        print("="*60)
        
        action = ListenAction()
        action.initialize({})
        
        results = []
        
        for i in range(3):
            print(f"\n🎤 第 {i+1} 次录音，请说话...")
            
            context = ActionContext(
                agent_state=AgentState.IDLE,
                input_data=2.0
            )
            
            result = await action.execute(context)
            assert result.success is True, f"第 {i+1} 次录音失败"
            
            text = result.output.get("text", "")
            results.append(text)
            print(f"   识别: {text}")
            
            # 短暂延迟
            await asyncio.sleep(0.5)
        
        print(f"\n✅ 全部完成！识别了 {len(results)} 段话")
        for i, text in enumerate(results, 1):
            print(f"   {i}. {text}")
        
        action.cleanup()


if __name__ == "__main__":
    # 提示用户如何运行
    print("""
╔════════════════════════════════════════════════════════════╗
║          ListenAction 集成测试使用说明                      ║
╚════════════════════════════════════════════════════════════╝

这些测试需要真实的麦克风和网络连接。

运行方式：
  1. 设置环境变量：
     Windows: set RUN_INTEGRATION=1
     Linux/Mac: export RUN_INTEGRATION=1
  
  2. 运行测试：
     uv run pytest test/test_listen_action_integration.py -v -s
  
  3. 运行特定测试：
     uv run pytest test/test_listen_action_integration.py::TestListenActionIntegration::test_real_recording_short -v -s

测试项目：
  ✓ test_real_recording_short - 3秒短录音
  ✓ test_real_recording_medium - 5秒中等录音  
  ✓ test_listen_one_time_helper - 测试辅助函数
  ✓ test_silent_audio - 静音测试
  ✓ test_multiple_sentences - 多句话识别
  ✓ test_with_custom_device - 自定义设备
  ✓ test_rapid_consecutive_calls - 连续录音

注意事项：
  - 确保麦克风可用
  - 确保有网络连接（调用 Dashscope API）
  - 确保环境变量 DASHSCOPE_INTL_API_KEY 已设置
  - 在安静的环境中测试效果更好
    """)
    
    pytest.main([__file__, "-v", "-s"])