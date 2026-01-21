"""ListenActionVAD - 基于 VAD 的智能语音识别 Action

使用 VAD 自动检测语音开始和结束，无需固定录音时长
"""

import os
import time
import tempfile
from typing import Dict, Any, Optional

from config import DASHSCOPE_INTL_API_KEY
from core.action.base import BaseAction, ActionContext, ActionResult, ActionMetadata

import dashscope
from dashscope.audio.asr import Recognition
from util.audio import AlsaRecorder, save_pcm_as_wav, create_speech_segmenter


class ListenActionVAD(BaseAction):
    """基于 VAD 的智能语音识别 Action
    
    改进点：
    - 自动检测语音开始和结束（无需固定时长）
    - 降低延迟（说完话后 0.5 秒即可触发识别）
    - 支持灵活配置（快速响应 vs 长语音）
    - 保持相同的 ASR 模型和 API
    
    对比原版 ListenAction：
    - 原版：固定录音 5 秒，延迟高
    - VAD 版：智能检测，延迟低 1-2 秒
    """
    
    def __init__(self):
        """初始化 ListenActionVAD"""
        super().__init__()
        self.model = "paraformer-realtime-v1"
        self.sample_rate = 16000
        self.format = "wav"
        
        # VAD 配置
        self.vad_aggressiveness = 2  # 0-3, 2 是平衡值
        self.min_speech_duration_ms = 500   # 最短语音 0.5 秒
        self.max_speech_duration_ms = 15000 # 最长语音 15 秒
        self.silence_duration_ms = 500      # 静音 0.5 秒判定结束
        
        self.speech_segmenter = None
    
    def get_metadata(self) -> ActionMetadata:
        """获取 Action 元信息"""
        return ActionMetadata(
            name="listen_vad",
            version="1.0.0",
            description="基于 VAD 的智能语音识别 Action，自动检测语音开始和结束",
            dependencies=["dashscope_api", "audio_device", "webrtcvad"],
            capabilities=["asr", "vad", "smart_recording"],
            author="Robot Agent Team"
        )
    
    def initialize(self, config_dict: Dict[str, Any]) -> None:
        """初始化 ListenActionVAD
        
        Args:
            config_dict: 配置参数
                - api_key: Dashscope API Key
                - model: 识别模型
                - sample_rate: 采样率
                - device: 录音设备
                - vad_aggressiveness: VAD 激进度 0-3
                - min_speech_ms: 最短语音时长
                - max_speech_ms: 最长语音时长
                - silence_ms: 静音判定时长
        """
        try:
            print("[ListenActionVAD] Initializing...")
            
            # 更新配置参数
            dashscope.api_key = DASHSCOPE_INTL_API_KEY
            self.model = config_dict.get("model", self.model)
            self.sample_rate = config_dict.get("sample_rate", self.sample_rate)
            self.device = config_dict.get("device", None)
            
            # VAD 配置
            self.vad_aggressiveness = config_dict.get("vad_aggressiveness", self.vad_aggressiveness)
            self.min_speech_duration_ms = config_dict.get("min_speech_ms", self.min_speech_duration_ms)
            self.max_speech_duration_ms = config_dict.get("max_speech_ms", self.max_speech_duration_ms)
            self.silence_duration_ms = config_dict.get("silence_ms", self.silence_duration_ms)
            
            # 创建语音分段器
            self.speech_segmenter = create_speech_segmenter(
                sample_rate=self.sample_rate,
                vad_aggressiveness=self.vad_aggressiveness,
                min_speech_ms=self.min_speech_duration_ms,
                max_speech_ms=self.max_speech_duration_ms,
                silence_ms=self.silence_duration_ms
            )
            
            self._initialized = True
            print("[ListenActionVAD] Initialization complete")
            print(f"  VAD Aggressiveness: {self.vad_aggressiveness}")
            print(f"  Min speech: {self.min_speech_duration_ms}ms")
            print(f"  Max speech: {self.max_speech_duration_ms}ms")
            print(f"  Silence threshold: {self.silence_duration_ms}ms")
            
        except Exception as e:
            print(f"[ListenActionVAD] Initialization failed: {e}")
            raise
    
    async def execute(self, context: ActionContext) -> ActionResult:
        """执行智能语音识别
        
        Args:
            context: Action 执行上下文
                - input_data: 可选的超时时长（秒），默认 20 秒
                - config.timeout: 最大监听时长（可选）
                
        Returns:
            ActionResult: 包含识别文本的 ActionResult
        """
        start_time = time.time()
        temp_wav_file = None
        temp_wav_path = None
        
        try:
            print("[ListenActionVAD] Executing...")
            
            if not self._initialized:
                raise RuntimeError("ListenActionVAD not initialized")
            
            # 获取超时配置
            timeout = context.input_data if isinstance(context.input_data, (int, float)) else 20.0
            timeout = context.config.get("timeout", timeout)
            
            print(f"[ListenActionVAD] Listening (timeout: {timeout}s)...")
            print("  Waiting for speech...")
            
            # 使用 VAD 录制音频
            audio_data = await self._record_with_vad(timeout)
            
            if not audio_data:
                print("[ListenActionVAD] No speech detected")
                return ActionResult(
                    success=True,
                    output={
                        "text": "",
                        "duration": 0,
                        "segments": []
                    },
                    metadata={
                        "elapsed_time": time.time() - start_time,
                        "no_speech_detected": True
                    }
                )
            
            print(f"[ListenActionVAD] Recorded {len(audio_data)} bytes of audio data")
            
            # 创建临时 WAV 文件用于识别
            temp_wav_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            temp_wav_path = temp_wav_file.name
            temp_wav_file.close()
            
            # 将 PCM 转换为 WAV
            save_pcm_as_wav(audio_data, temp_wav_path, rate=self.sample_rate, channels=1)
            print(f"[ListenActionVAD] Saved audio to: {temp_wav_path}")
            
            # 进行语音识别（使用相同的 ASR API）
            text = await self._recognize_audio(temp_wav_path)
            
            elapsed_time = time.time() - start_time
            actual_duration = len(audio_data) / (self.sample_rate * 2)
            
            print(f"[ListenActionVAD] Execution complete in {elapsed_time:.2f}s")
            print(f"  Actual speech duration: {actual_duration:.2f}s")
            print(f"  Recognized text: {text}")
            
            return ActionResult(
                success=True,
                output={
                    "text": text,
                    "duration": actual_duration,
                    "audio_file": temp_wav_path,
                    "segments": [text] if text else []
                },
                metadata={
                    "elapsed_time": elapsed_time,
                    "actual_speech_duration": actual_duration,
                    "model": self.model,
                    "sample_rate": self.sample_rate,
                    "vad_enabled": True
                }
            )
            
        except Exception as e:
            elapsed_time = time.time() - start_time
            print(f"[ListenActionVAD] Execution failed: {e}")
            import traceback
            traceback.print_exc()
            return ActionResult(
                success=False,
                error=e,
                metadata={"elapsed_time": elapsed_time}
            )
        finally:
            # 清理临时文件
            if temp_wav_path and os.path.exists(temp_wav_path):
                try:
                    os.unlink(temp_wav_path)
                    print(f"[ListenActionVAD] Cleaned up temp file: {temp_wav_path}")
                except Exception as e:
                    print(f"[ListenActionVAD] Failed to clean up temp file: {e}")
    
    async def _record_with_vad(self, timeout: float) -> Optional[bytes]:
        """使用 VAD 录制音频
        
        Args:
            timeout: 最大监听时长（秒）
            
        Returns:
            PCM 音频数据，如果超时或无语音则返回 None
        """
        print(f"[ListenActionVAD] Starting VAD-based recording...")
        
        # 创建录音器
        recorder = AlsaRecorder(
            rate=self.sample_rate,
            channels=1,
            device=self.device
        )
        
        # 使用语音分段器监听
        audio_data = await self.speech_segmenter.listen_for_speech(
            recorder=recorder,
            timeout=timeout
        )
        
        return audio_data
    
    async def _recognize_audio(self, audio_file_path: str) -> str:
        """识别音频文件（与原版相同的实现）
        
        Args:
            audio_file_path: 音频文件路径
            
        Returns:
            识别的文本
        """
        import asyncio
        
        print(f"[ListenActionVAD] Recognizing audio...")
        
        def recognize_sync():
            """同步识别函数"""
            try:
                # 使用标准 ASR API（与原版相同）
                recognition = Recognition(
                    model=self.model,
                    format='wav',
                    sample_rate=self.sample_rate,
                    callback=None
                )
                
                # 调用语音识别 API
                result = recognition.call(audio_file_path)
                
                print(f"[ListenActionVAD] API Response - Status: {result.status_code}")
                
                if result.status_code == 200:
                    # 提取识别结果
                    if result.output:
                        # 尝试 'sentence' 格式（paraformer-realtime-v1）
                        if 'sentence' in result.output:
                            sentences = result.output['sentence']
                            if sentences and len(sentences) > 0:
                                texts = [s.get('text', '') for s in sentences if 'text' in s]
                                final_text = ''.join(texts)
                                print(f"[ListenActionVAD] Recognition result: {final_text}")
                                return final_text
                        
                        # 尝试 'results' 格式
                        elif 'results' in result.output:
                            results = result.output['results']
                            if results and len(results) > 0:
                                texts = [item.get('text', '') for item in results if 'text' in item]
                                final_text = ''.join(texts)
                                print(f"[ListenActionVAD] Recognition result: {final_text}")
                                return final_text
                    
                    print(f"[ListenActionVAD] No recognition results in response")
                    return ""
                else:
                    error_msg = f"Recognition failed with status {result.status_code}"
                    if hasattr(result, 'message'):
                        error_msg += f": {result.message}"
                    raise RuntimeError(error_msg)
                    
            except Exception as e:
                print(f"[ListenActionVAD] Recognition error: {e}")
                raise
        
        # 在线程池中执行同步识别
        text = await asyncio.get_event_loop().run_in_executor(None, recognize_sync)
        
        return text
    
    def cleanup(self) -> None:
        """清理资源"""
        print("[ListenActionVAD] Cleaning up...")
        self._initialized = False
        print("[ListenActionVAD] Cleanup complete")


# 便捷函数
async def listen_with_vad(
    timeout: float = 20.0,
    vad_aggressiveness: int = 2,
    silence_ms: int = 500
):
    """使用 VAD 进行单次语音识别的便捷函数
    
    Args:
        timeout: 最大监听时长（秒）
        vad_aggressiveness: VAD 激进度 0-3
        silence_ms: 静音判定时长（毫秒）
        
    Returns:
        识别的文本
    """
    from core.agent import AgentState
    
    action = ListenActionVAD()
    action.initialize({
        "vad_aggressiveness": vad_aggressiveness,
        "silence_ms": silence_ms
    })
    
    context = ActionContext(
        agent_state=AgentState.IDLE,
        input_data=timeout
    )
    
    result = await action.execute(context)
    
    if result.success:
        print("Listen VAD Success:", result.output)
        return result.output.get("text", "")
    else:
        print("Listen VAD Error:", result.error)
        return ""


# 预设配置
class VADPresets:
    """VAD 预设配置"""
    
    # 快速响应（适合简短问答）
    QUICK_RESPONSE = {
        "vad_aggressiveness": 3,      # 高激进度
        "min_speech_ms": 300,
        "max_speech_ms": 10000,
        "silence_ms": 300             # 快速触发
    }
    
    # 标准模式（平衡）
    STANDARD = {
        "vad_aggressiveness": 2,
        "min_speech_ms": 500,
        "max_speech_ms": 15000,
        "silence_ms": 500
    }
    
    # 长语音模式（适合长篇陈述）
    LONG_SPEECH = {
        "vad_aggressiveness": 1,      # 低激进度，容忍停顿
        "min_speech_ms": 500,
        "max_speech_ms": 30000,
        "silence_ms": 1000            # 更长容忍
    }


if __name__ == "__main__":
    import asyncio
    
    async def test():
        print("=== ListenActionVAD 测试 ===\n")
        
        # 使用标准模式
        print("使用标准模式...")
        text = await listen_with_vad(
            timeout=20.0,
            vad_aggressiveness=2,
            silence_ms=500
        )
        
        print(f"\n识别结果: {text}")
    
    asyncio.run(test())