# core/action/speak_action.py
"""SpeakAction - 语音合成 Action

负责将文本转换为语音输出
"""

import os
import base64
import time
import asyncio
import tempfile
import threading
from typing import Dict, Any

from config import DASHSCOPE_INTL_API_KEY
from core.action.base import BaseAction, ActionContext, ActionResult, ActionMetadata

import dashscope
from dashscope.audio.qwen_tts_realtime import QwenTtsRealtimeCallback, QwenTtsRealtime, AudioFormat
from util.audio import AlsaPlayer

qwen_tts_realtime: QwenTtsRealtime = None

class ResponseCallback(QwenTtsRealtimeCallback):
    """ResponseCallback - Tts响应回调
    """
    def __init__(self, temp_file_path: str):
        self.complete_event = threading.Event()
        self.temp_file_path = temp_file_path
        self.file = open(temp_file_path, 'wb')

    def on_open(self) -> None:
        print('connection opened, init player')

    def on_close(self, close_status_code, close_msg) -> None:
        self.file.close()
        print('connection closed with code: {}, msg: {}, destroy player'.format(close_status_code, close_msg))

    def on_event(self, response: str) -> None:
        try:
            global qwen_tts_realtime
            type = response['type']
            if 'session.created' == type:
                print('start session: {}'.format(response['session']['id']))
            if 'response.audio.delta' == type:
                recv_audio_b64 = response['delta']
                self.file.write(base64.b64decode(recv_audio_b64))
            if 'response.done' == type:
                print(f'response {qwen_tts_realtime.get_last_response_id()} done')
            if 'session.finished' == type:
                print('session finished')
                self.complete_event.set()
        except Exception as e:
            print('[Error] {}'.format(e))
            return

    def wait_for_finished(self):
        self.complete_event.wait()


class SpeakAction(BaseAction):
    """语音合成 Action
    
    将文本转换为语音并播放
    """
    
    def __init__(self):
        """初始化 SpeakAction"""
        super().__init__()
        self.voice = "Cherry"
        self.auto_play = True
        self.player = None  # 延迟创建，避免不必要的资源占用
        self.callback = None
        self.temp_pcm_file = None
    
    def get_metadata(self) -> ActionMetadata:
        """获取 Action 元信息"""
        return ActionMetadata(
            name="speak",
            version="1.0.0",
            description="语音合成 Action，用于将文本转换为语音",
            dependencies=["dashscope_api", "audio_device"],
            capabilities=["tts", "audio_playback"],
            author="Robot Agent Team"
        )
    
    def initialize(self, config_dict: Dict[str, Any]) -> None:
        """初始化 SpeakAction
        
        Args:
            config_dict: 配置参数
                - api_key: Dashscope API Key
                - voice: 音色类型
                - auto_play: 是否自动播放
                - stream: 是否流式传输（暂时不做）
        """
        try:
            print("[SpeakAction] Initializing...")
            
            # 更新配置参数
            dashscope.api_key = DASHSCOPE_INTL_API_KEY
            self.voice = config_dict.get("voice", self.voice)
            self.auto_play = config_dict.get("auto_play", self.auto_play)
            # self.stream = config_dict.get("stream", False)

            
            self._initialized = True
            print("[SpeakAction] Initialization complete")
            
        except Exception as e:
            print(f"[SpeakAction] Initialization failed: {e}")
            raise
    
    async def execute(self, context: ActionContext) -> ActionResult:
        """执行语音合成
        
        Args:
            context: Action 执行上下文
                - input_data: 要转换为语音的文本
                - config.voice: 音色选择（可选）
                
        Returns:
            ActionResult: 包含音频数据的 ActionResult
        """
        start_time = time.time()
        
        try:
            print("[SpeakAction] Executing...")
            
            if not self._initialized:
                raise RuntimeError("SpeakAction not initialized")
            
            # 获取要转换的文本
            text = context.input_data
            if not text or not isinstance(text, str):
                # 尝试从共享数据中获取默认文本
                vision_result = context.shared_data.get("last_vision_result", {})
                text = vision_result.get("description", "没听清您说的话，请重复")
            
            print(f"[SpeakAction] Text to speak: {text}")
            
            # 获取音色配置
            voice = context.config.get("voice", self.voice)
            
            # 进行句子分割
            text_chunks = self._split_sentences(text)
            
            # 创建临时 PCM 文件
            self.temp_pcm_file = tempfile.NamedTemporaryFile(suffix=".pcm", delete=False)
            temp_pcm_path = self.temp_pcm_file.name
            self.temp_pcm_file.close()  # 先关闭，让 callback 打开写入
            
            print(f"[SpeakAction] Using temp PCM file: {temp_pcm_path}")
            
            # 创建 callback 和 TTS 实例
            self.callback = ResponseCallback(temp_pcm_path)
            global qwen_tts_realtime
            # 这里要用国际版的接口
            qwen_tts_realtime = QwenTtsRealtime(
                model='qwen3-tts-flash-realtime', 
                callback=self.callback,
                url='wss://dashscope.aliyuncs.com/api-ws/v1/realtime'
                # url='wss://dashscope-intl.aliyuncs.com/api-ws/v1/realtime'
            )
            
            qwen_tts_realtime.connect()
            
            qwen_tts_realtime.update_session(
                voice=voice,
                response_format=AudioFormat.PCM_24000HZ_MONO_16BIT,
                mode='server_commit'        
            )
            
            print("[SpeakAction] Session updated")

            # 流式语音合成
            for text_chunk in text_chunks:
                print(f'send text: {text_chunk}')
                qwen_tts_realtime.append_text(text_chunk)
                time.sleep(0.1)
            qwen_tts_realtime.finish()
            self.callback.wait_for_finished()
            print('[Metric] session: {}, first audio delay: {}'.format(
                qwen_tts_realtime.get_session_id(), 
                qwen_tts_realtime.get_first_audio_delay(),
            ))
            
            # 播放音频
            if self.auto_play:
                await self._play_audio(temp_pcm_path)
            
            
            elapsed_time = time.time() - start_time
            print(f"[SpeakAction] Execution complete in {elapsed_time:.2f}s")
            
            return ActionResult(
                success=True,
                output={
                    "text": text,
                    "audio_file": temp_pcm_path
                },
                metadata={
                    "elapsed_time": elapsed_time,
                    "voice": voice
                }
            )
            
        except Exception as e:
            elapsed_time = time.time() - start_time
            print(f"[SpeakAction] Execution failed: {e}")
            return ActionResult(
                success=False,
                error=e,
                metadata={"elapsed_time": elapsed_time}
            )
        finally:
            # 清理临时文件
            if self.temp_pcm_file and os.path.exists(temp_pcm_path):
                try:
                    os.unlink(temp_pcm_path)
                    print(f"[SpeakAction] Cleaned up temp file: {temp_pcm_path}")
                except Exception as e:
                    print(f"[SpeakAction] Failed to clean up temp file: {e}")
    
    async def _play_audio(self, pcm_file_path: str) -> None:
        """
        使用 AlsaPlayer 播放 PCM 音频文件
        
        Args:
            pcm_file_path: PCM 文件路径（24kHz, 单声道, 16bit）
        """
        player = None
        try:
            print(f"[SpeakAction] Playing audio from: {pcm_file_path}")
            
            # 读取 PCM 文件
            with open(pcm_file_path, 'rb') as f:
                pcm_data = f.read()
            
            print(f"[SpeakAction] Playing {len(pcm_data)} bytes of PCM data...")
            
            # 创建播放器（TTS 输出是单声道，但声卡需要双声道）
            import platform
            if platform.system() == "Windows":
                player = AlsaPlayer(rate=24000, channels=2)
            else:
                player = AlsaPlayer(rate=24000, channels=2, device="hw:0,0")
            
            # 使用 AlsaPlayer 播放（在线程中同步播放）
            def play_sync():
                try:
                    player.write(pcm_data)
                except Exception as e:
                    print(f"[SpeakAction] Player error: {e}")
            
            # 在线程池中执行同步播放
            await asyncio.get_event_loop().run_in_executor(None, play_sync)
            
            print("[SpeakAction] Audio playback complete")
            
        except Exception as e:
            print(f"[SpeakAction] Failed to play audio: {e}")
            raise
        finally:
            # 确保关闭播放器
            if player:
                try:
                    player.close()
                except Exception as e:
                    print(f"[SpeakAction] Failed to close player: {e}")
    
    def _split_sentences(self, text: str) -> list[str]:
        """将文本进行句子分割"""
        if not text:
            return []
        
        # 按照中文句号、中文逗号、英文句号、英文逗号分割
        import re
        sentences = re.split(r'[。，,.]+', text)
        
        # 过滤掉空字符串并去除首尾空白
        sentences = [s.strip() for s in sentences if s.strip()]
        
        return sentences
    
    def cleanup(self) -> None:
        """清理资源"""
        print("[SpeakAction] Cleaning up...")
        
        # 关闭播放器（如果存在）
        if self.player:
            try:
                self.player.close()
            except Exception as e:
                print(f"[SpeakAction] Failed to close player: {e}")
        
        self._initialized = False
        print("[SpeakAction] Cleanup complete")


async def speak_one_time(text: str):
        # 避免循环依赖
        from core.agent import AgentState
        
        action = SpeakAction()
        action.initialize({})
        
        context = ActionContext(
            agent_state=AgentState.IDLE,
            input_data=text
        )
        
        result = await action.execute(context)
        if(result.success):
            print("Speak Success:", result.output)
        else:
            print("Speak Error:", result.error)
