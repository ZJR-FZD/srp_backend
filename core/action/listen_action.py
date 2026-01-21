"""ListenAction - 语音识别 Action (稳定版)

使用标准 ASR API，先录音再识别
"""

import os
import time
import tempfile
from typing import Dict, Any

from config import DASHSCOPE_INTL_API_KEY
from core.action.base import BaseAction, ActionContext, ActionResult, ActionMetadata

import dashscope
from dashscope.audio.asr import Recognition
from util.audio import AlsaRecorder, save_pcm_as_wav


class ListenAction(BaseAction):
    """语音识别 Action
    
    录制音频并将其转换为文本（使用标准 API）
    """
    
    def __init__(self):
        """初始化 ListenAction"""
        super().__init__()
        self.model = "paraformer-realtime-v1"
        self.sample_rate = 16000
        self.format = "wav"
    
    def get_metadata(self) -> ActionMetadata:
        """获取 Action 元信息"""
        return ActionMetadata(
            name="listen",
            version="1.0.0",
            description="语音识别 Action，录制音频并转换为文本",
            dependencies=["dashscope_api", "audio_device"],
            capabilities=["asr", "audio_recording"],
            author="Robot Agent Team"
        )
    
    def initialize(self, config_dict: Dict[str, Any]) -> None:
        """初始化 ListenAction
        
        Args:
            config_dict: 配置参数
                - api_key: Dashscope API Key
                - model: 识别模型
                - sample_rate: 采样率
                - device: 录音设备
        """
        try:
            print("[ListenAction] Initializing...")
            
            # 更新配置参数
            dashscope.api_key = DASHSCOPE_INTL_API_KEY
            self.model = config_dict.get("model", self.model)
            self.sample_rate = config_dict.get("sample_rate", self.sample_rate)
            self.device = config_dict.get("device", None)
            
            self._initialized = True
            print("[ListenAction] Initialization complete")
            
        except Exception as e:
            print(f"[ListenAction] Initialization failed: {e}")
            raise
    
    async def execute(self, context: ActionContext) -> ActionResult:
        """执行语音识别
        
        Args:
            context: Action 执行上下文
                - input_data: 录音时长(秒)，默认 5 秒
                - config.duration: 录音时长(可选)
                
        Returns:
            ActionResult: 包含识别文本的 ActionResult
        """
        start_time = time.time()
        temp_wav_file = None
        temp_wav_path = None
        
        try:
            print("[ListenAction] Executing...")
            
            if not self._initialized:
                raise RuntimeError("ListenAction not initialized")
            
            # 获取录音时长
            duration = context.input_data if isinstance(context.input_data, (int, float)) else 5
            duration = context.config.get("duration", duration)
            
            print(f"[ListenAction] Recording for {duration} seconds...")
            
            # 录制音频
            audio_data = await self._record_audio(duration)
            
            print(f"[ListenAction] Recorded {len(audio_data)} bytes of audio data")
            
            # 创建临时 WAV 文件用于识别
            temp_wav_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            temp_wav_path = temp_wav_file.name
            temp_wav_file.close()
            
            # 将 PCM 转换为 WAV
            save_pcm_as_wav(audio_data, temp_wav_path, rate=self.sample_rate, channels=1)
            print(f"[ListenAction] Saved audio to: {temp_wav_path}")
            
            # 进行语音识别
            text = await self._recognize_audio(temp_wav_path)
            
            elapsed_time = time.time() - start_time
            print(f"[ListenAction] Execution complete in {elapsed_time:.2f}s")
            print(f"[ListenAction] Recognized text: {text}")
            
            return ActionResult(
                success=True,
                output={
                    "text": text,
                    "duration": duration,
                    "audio_file": temp_wav_path,
                    "segments": [text] if text else []  # 添加 segments 字段
                },
                metadata={
                    "elapsed_time": elapsed_time,
                    "model": self.model,
                    "sample_rate": self.sample_rate
                }
            )
            
        except Exception as e:
            elapsed_time = time.time() - start_time
            print(f"[ListenAction] Execution failed: {e}")
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
                    print(f"[ListenAction] Cleaned up temp file: {temp_wav_path}")
                except Exception as e:
                    print(f"[ListenAction] Failed to clean up temp file: {e}")
    
    async def _record_audio(self, duration: float) -> bytes:
        """录制音频
        
        Args:
            duration: 录音时长(秒)
            
        Returns:
            PCM 音频数据
        """
        import asyncio
        
        print(f"[ListenAction] Starting recording...")
        
        # 创建录音器
        recorder = AlsaRecorder(
            rate=self.sample_rate,
            channels=1,
            device=self.device,
            chunk_size=3200  # 0.1 秒
        )
        
        audio_chunks = []
        
        def record_sync():
            """同步录制函数"""
            try:
                recorder.start()
                
                # 计算需要录制的总字节数
                # 采样率 * 声道数 * 字节数(16-bit = 2) * 时长
                total_bytes = int(self.sample_rate * 1 * 2 * duration)
                bytes_recorded = 0
                
                while bytes_recorded < total_bytes:
                    chunk_size = min(3200, total_bytes - bytes_recorded)
                    chunk = recorder.read(chunk_size)
                    if chunk:
                        audio_chunks.append(chunk)
                        bytes_recorded += len(chunk)
                        
                        # 显示进度
                        if bytes_recorded % (3200 * 10) == 0:
                            progress = (bytes_recorded / total_bytes) * 100
                            print(f"[ListenAction] Recording: {progress:.0f}%")
                
            finally:
                recorder.stop()
        
        # 在线程池中执行同步录制
        await asyncio.get_event_loop().run_in_executor(None, record_sync)
        
        # 合并所有音频块
        audio_data = b''.join(audio_chunks)
        print(f"[ListenAction] Recording complete, {len(audio_data)} bytes")
        
        return audio_data
    
    async def _recognize_audio(self, audio_file_path: str) -> str:
        """识别音频文件
        
        Args:
            audio_file_path: 音频文件路径
            
        Returns:
            识别的文本
        """
        import asyncio
        
        print(f"[ListenAction] Recognizing audio...")
        
        def recognize_sync():
            """同步识别函数"""
            try:
                # 使用标准 ASR API
                recognition = Recognition(
                    model=self.model,
                    format='wav',
                    sample_rate=self.sample_rate,
                    callback=None
                )
                
                # 调用语音识别 API
                result = recognition.call(audio_file_path)
                
                print(f"[ListenAction] API Response - Status: {result.status_code}")
                
                if result.status_code == 200:
                    # 提取识别结果
                    # API 可能返回 'results' 或 'sentence' 格式
                    if result.output:
                        # 尝试 'sentence' 格式（paraformer-realtime-v1）
                        if 'sentence' in result.output:
                            sentences = result.output['sentence']
                            if sentences and len(sentences) > 0:
                                texts = [s.get('text', '') for s in sentences if 'text' in s]
                                final_text = ''.join(texts)
                                print(f"[ListenAction] Recognition result (sentence): {final_text}")
                                return final_text
                        
                        # 尝试 'results' 格式（其他模型）
                        elif 'results' in result.output:
                            results = result.output['results']
                            if results and len(results) > 0:
                                texts = [item.get('text', '') for item in results if 'text' in item]
                                final_text = ''.join(texts)
                                print(f"[ListenAction] Recognition result (results): {final_text}")
                                return final_text
                    
                    print(f"[ListenAction] No recognition results in response")
                    print(f"[ListenAction] Full response: {result.output}")
                    return ""
                else:
                    error_msg = f"Recognition failed with status {result.status_code}"
                    if hasattr(result, 'message'):
                        error_msg += f": {result.message}"
                    raise RuntimeError(error_msg)
                    
            except Exception as e:
                print(f"[ListenAction] Recognition error: {e}")
                raise
        
        # 在线程池中执行同步识别
        text = await asyncio.get_event_loop().run_in_executor(None, recognize_sync)
        
        return text
    
    def cleanup(self) -> None:
        """清理资源"""
        print("[ListenAction] Cleaning up...")
        self._initialized = False
        print("[ListenAction] Cleanup complete")


async def listen_one_time(duration: float = 5.0):
    """单次语音识别测试函数
    
    Args:
        duration: 录音时长(秒)
    """
    # 避免循环依赖
    from core.agent import AgentState
    
    action = ListenAction()
    action.initialize({})
    
    context = ActionContext(
        agent_state=AgentState.IDLE,
        input_data=duration
    )
    
    result = await action.execute(context)
    if result.success:
        print("Listen Success:", result.output)
        return result.output.get("text", "")
    else:
        print("Listen Error:", result.error)
        return ""