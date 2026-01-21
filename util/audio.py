import subprocess
import threading
import struct
import wave


class AlsaPlayer:
    """跨平台音频播放器
    
    Linux: 使用 aplay 命令
    Windows: 使用 pyaudio
    """
    
    def __init__(
        self,
        rate: int = 16000,
        channels: int = 1,
        device: str | None = None,
    ):
        """初始化播放器
        
        Args:
            rate: 采样率
            channels: 声道数
            device: ALSA 设备名称 (仅 Linux)
        """
        self.rate = rate
        self.channels = channels
        self.device = device
        self._lock = threading.Lock()
        
        # 检测操作系统
        import platform
        self._platform = platform.system()
        
        if self._platform == "Windows":
            # Windows 平台使用 pyaudio
            try:
                import pyaudio
            except ImportError:
                raise RuntimeError(
                    "Windows 平台需要安装 pyaudio。\n"
                    "请运行: pip install pyaudio 或 uv add pyaudio"
                )
            
            self._pyaudio = pyaudio.PyAudio()
            self._stream = self._pyaudio.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=rate,
                output=True
            )
            self._proc = None
        else:
            # Linux 平台使用 aplay
            cmd = [
                "aplay",
                "-q",
                "-f", "S16_LE",
                "-r", str(rate),
                "-c", str(channels),
            ]
            if device:
                cmd.extend(["-D", device])

            self._proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                bufsize=0,
            )
            self._pyaudio = None
            self._stream = None

    def write(self, pcm: bytes):
        """写入 PCM 数据并播放
        
        Args:
            pcm: PCM 音频数据
        """
        if self._platform == "Windows":
            # Windows: 使用 pyaudio
            with self._lock:
                # 如果需要转换为双声道
                if self.channels == 2 and len(pcm) % 2 == 0:
                    pcm = self._mono_to_stereo(pcm)
                
                self._stream.write(pcm)
        else:
            # Linux: 使用 aplay
            if self._proc.poll() is not None:
                raise RuntimeError("aplay exited unexpectedly")

            with self._lock:
                # 如果是单声道但设备需要双声道，进行转换
                if self.channels == 2 and len(pcm) % 2 == 0:
                    pcm = self._mono_to_stereo(pcm)
                
                self._proc.stdin.write(pcm)
                self._proc.stdin.flush()

    def _mono_to_stereo(self, mono_pcm: bytes) -> bytes:
        """将单声道 PCM 转换为立体声(复制单声道数据到两个声道)
        
        Args:
            mono_pcm: 单声道 PCM 数据(16-bit signed)
            
        Returns:
            立体声 PCM 数据
        """
        stereo_samples = []
        # 每2个字节是一个16-bit样本
        for i in range(0, len(mono_pcm), 2):
            sample = mono_pcm[i:i+2]
            # 左右声道使用相同的数据
            stereo_samples.append(sample)  # 左声道
            stereo_samples.append(sample)  # 右声道
        return b''.join(stereo_samples)
    
    def close(self):
        """关闭播放器"""
        if self._platform == "Windows":
            # Windows: 关闭 pyaudio
            if self._stream:
                self._stream.stop_stream()
                self._stream.close()
            if self._pyaudio:
                self._pyaudio.terminate()
        else:
            # Linux: 关闭 aplay
            if self._proc and self._proc.stdin:
                try:
                    self._proc.stdin.close()
                finally:
                    self._proc.wait()


class AlsaRecorder:
    """跨平台音频录制器
    
    Linux: 使用 arecord 命令
    Windows: 使用 pyaudio
    """
    
    def __init__(
        self,
        rate: int = 16000,
        channels: int = 1,
        device: str | None = None,
        chunk_size: int = 1024,
    ):
        """初始化录制器
        
        Args:
            rate: 采样率
            channels: 声道数
            device: ALSA 设备名称 (仅 Linux)
            chunk_size: 每次读取的字节数
        """
        self.rate = rate
        self.channels = channels
        self.device = device
        self.chunk_size = chunk_size
        self._proc = None
        self._lock = threading.Lock()
        self._recording = False
        
        # 检测操作系统
        import platform
        self._platform = platform.system()
        
        # Windows 平台需要的额外属性
        if self._platform == "Windows":
            self._pyaudio = None
            self._stream = None
            self._audio_buffer = []
    
    def start(self):
        """开始录制"""
        if self._recording:
            raise RuntimeError("Already recording")
        
        if self._platform == "Windows":
            self._start_windows()
        else:
            self._start_linux()
        
        self._recording = True
        print(f"[AlsaRecorder] Started recording at {self.rate}Hz, {self.channels} channel(s) on {self._platform}")
    
    def _start_linux(self):
        """Linux 平台：使用 arecord"""
        cmd = [
            "arecord",
            "-q",
            "-f", "S16_LE",
            "-r", str(self.rate),
            "-c", str(self.channels),
            "-t", "raw",  # 输出原始 PCM 数据
        ]
        if self.device:
            cmd.extend(["-D", self.device])
        
        self._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0,
        )
    
    def _start_windows(self):
        """Windows 平台：使用 pyaudio"""
        try:
            import pyaudio
        except ImportError:
            raise RuntimeError(
                "Windows 平台需要安装 pyaudio。\n"
                "请运行: pip install pyaudio\n"
                "或: uv add pyaudio"
            )
        
        self._pyaudio = pyaudio.PyAudio()
        self._audio_buffer = []
        
        # 打开音频流
        self._stream = self._pyaudio.open(
            format=pyaudio.paInt16,  # 16-bit
            channels=self.channels,
            rate=self.rate,
            input=True,
            frames_per_buffer=self.chunk_size
        )
    
    def read(self, size: int | None = None) -> bytes:
        """读取音频数据
        
        Args:
            size: 要读取的字节数,如果为 None 则使用 chunk_size
            
        Returns:
            PCM 音频数据
        """
        if not self._recording:
            raise RuntimeError("Not recording")
        
        if self._platform == "Windows":
            return self._read_windows(size)
        else:
            return self._read_linux(size)
    
    def _read_linux(self, size: int | None = None) -> bytes:
        """Linux 平台读取"""
        if self._proc.poll() is not None:
            raise RuntimeError("arecord exited unexpectedly")
        
        read_size = size if size is not None else self.chunk_size
        
        with self._lock:
            data = self._proc.stdout.read(read_size)
            return data
    
    def _read_windows(self, size: int | None = None) -> bytes:
        """Windows 平台读取"""
        read_size = size if size is not None else self.chunk_size
        
        with self._lock:
            # 计算需要读取的帧数
            frames = read_size // (2 * self.channels)  # 2 bytes per sample
            
            # 从流中读取
            data = self._stream.read(frames, exception_on_overflow=False)
            return data
    
    def stop(self):
        """停止录制"""
        if not self._recording:
            return
        
        with self._lock:
            if self._platform == "Windows":
                self._stop_windows()
            else:
                self._stop_linux()
            
            self._recording = False
            print("[AlsaRecorder] Stopped recording")
    
    def _stop_linux(self):
        """Linux 平台停止"""
        if self._proc:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait()
            self._proc = None
    
    def _stop_windows(self):
        """Windows 平台停止"""
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None
        
        if self._pyaudio:
            self._pyaudio.terminate()
            self._pyaudio = None
    
    def is_recording(self) -> bool:
        """检查是否正在录制"""
        return self._recording
    
    def __enter__(self):
        """上下文管理器入口"""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        self.stop()


def save_pcm_as_wav(pcm_data: bytes, wav_path: str, rate: int = 16000, channels: int = 1):
    """将 PCM 数据保存为 WAV 文件
    
    Args:
        pcm_data: PCM 音频数据
        wav_path: 输出 WAV 文件路径
        rate: 采样率
        channels: 声道数
    """
    with wave.open(wav_path, 'wb') as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(2)  # 16-bit = 2 bytes
        wav_file.setframerate(rate)
        wav_file.writeframes(pcm_data)

"""语音分段器

基于 VAD 检测结果，智能分割语音片段
"""

import asyncio
import time
from enum import Enum
from typing import Optional
from util.vad_detector import VADDetector
from util.audio import AlsaRecorder


class SegmentState(Enum):
    """语音分段状态"""
    IDLE = "idle"           # 空闲，等待语音
    DETECTING = "detecting" # 检测到语音，累积中
    SPEAKING = "speaking"   # 确认正在说话
    ENDING = "ending"       # 检测到静音，判断是否结束


class SpeechSegmenter:
    """语音分段器
    
    使用 VAD 检测自动分割语音片段
    """
    
    def __init__(
        self,
        vad_detector: VADDetector,
        min_speech_duration_ms: int = 200,
        max_speech_duration_ms: int = 15000,
        silence_duration_ms: int = 300,
        pre_speech_padding_ms: int = 300,
        post_speech_padding_ms: int = 300,
        sample_rate: int = 16000
    ):
        """初始化语音分段器
        
        Args:
            vad_detector: VAD 检测器实例
            min_speech_duration_ms: 最短语音时长（ms），过滤噪音
            max_speech_duration_ms: 最长语音时长（ms），防止无限录音
            silence_duration_ms: 判定结束的静音时长（ms）
            pre_speech_padding_ms: 前置填充时长（ms），防止切头
            post_speech_padding_ms: 后置填充时长（ms），防止切尾
            sample_rate: 采样率
        """
        self.vad = vad_detector
        self.min_speech_duration_ms = min_speech_duration_ms
        self.max_speech_duration_ms = max_speech_duration_ms
        self.silence_duration_ms = silence_duration_ms
        self.pre_speech_padding_ms = pre_speech_padding_ms
        self.post_speech_padding_ms = post_speech_padding_ms
        self.sample_rate = sample_rate
        
        # 计算各种阈值（以帧数计）
        frame_duration_ms = vad_detector.frame_duration_ms
        self.min_speech_frames = min_speech_duration_ms // frame_duration_ms
        self.max_speech_frames = max_speech_duration_ms // frame_duration_ms
        self.silence_frames = silence_duration_ms // frame_duration_ms
        self.pre_padding_frames = pre_speech_padding_ms // frame_duration_ms
        self.post_padding_frames = post_speech_padding_ms // frame_duration_ms
        
        print(f"[SpeechSegmenter] Initialized")
        print(f"  Min speech: {min_speech_duration_ms}ms ({self.min_speech_frames} frames)")
        print(f"  Max speech: {max_speech_duration_ms}ms ({self.max_speech_frames} frames)")
        print(f"  Silence threshold: {silence_duration_ms}ms ({self.silence_frames} frames)")
        print(f"  Padding: pre={pre_speech_padding_ms}ms, post={post_speech_padding_ms}ms")
    
    async def listen_for_speech(
        self,
        recorder: AlsaRecorder,
        timeout: Optional[float] = None
    ) -> Optional[bytes]:
        """持续监听，返回一段完整的语音
        
        Args:
            recorder: 音频录制器
            timeout: 超时时间（秒），None 表示无超时
            
        Returns:
            完整的语音音频数据，如果超时或无语音则返回 None
        """
        print("[SpeechSegmenter] Starting to listen for speech...")
        
        state = SegmentState.IDLE
        speech_buffer = []  # 语音缓冲区
        pre_buffer = []     # 前置缓冲区（环形）
        speech_frames = 0   # 语音帧计数
        silence_frames = 0  # 静音帧计数
        total_frames = 0    # 总帧数
        
        start_time = time.time()
        frame_size = self.vad.get_frame_size()
        
        # 在线程池中执行录音循环
        def record_loop():
            nonlocal state, speech_buffer, pre_buffer, speech_frames, silence_frames, total_frames
            
            try:
                recorder.start()
                
                while True:
                    # 检查超时
                    if timeout and (time.time() - start_time) > timeout:
                        print(f"[SpeechSegmenter] Timeout after {timeout}s")
                        return None
                    
                    # 读取一帧
                    frame = recorder.read(frame_size)
                    if not frame or len(frame) == 0:
                        continue
                    
                    total_frames += 1
                    
                    # VAD 检测
                    is_speech = self.vad.is_speech(frame)
                    
                    # 状态机处理
                    if state == SegmentState.IDLE:
                        # 维护前置缓冲区（环形队列）
                        pre_buffer.append(frame)
                        if len(pre_buffer) > self.pre_padding_frames:
                            pre_buffer.pop(0)
                        
                        # 检测到语音 → 进入 DETECTING
                        if is_speech:
                            print(f"[SpeechSegmenter] Speech detected at frame {total_frames}")
                            state = SegmentState.DETECTING
                            # 添加前置缓冲区
                            speech_buffer.extend(pre_buffer)
                            speech_buffer.append(frame)
                            speech_frames = 1
                            silence_frames = 0
                    
                    elif state == SegmentState.DETECTING:
                        speech_buffer.append(frame)
                        
                        if is_speech:
                            speech_frames += 1
                            silence_frames = 0
                            
                            # 累积足够长 → 确认是语音
                            if speech_frames >= self.min_speech_frames:
                                print(f"[SpeechSegmenter] Speech confirmed at frame {total_frames}")
                                state = SegmentState.SPEAKING
                        else:
                            silence_frames += 1
                            
                            # 太快就静音 → 可能是噪音，回到 IDLE
                            if silence_frames >= self.silence_frames:
                                print(f"[SpeechSegmenter] False alarm, back to IDLE")
                                state = SegmentState.IDLE
                                speech_buffer.clear()
                                speech_frames = 0
                                silence_frames = 0
                    
                    elif state == SegmentState.SPEAKING:
                        speech_buffer.append(frame)
                        
                        if is_speech:
                            speech_frames += 1
                            silence_frames = 0
                            
                            # 超过最大长度 → 强制结束
                            if speech_frames >= self.max_speech_frames:
                                print(f"[SpeechSegmenter] Max duration reached, ending")
                                return b''.join(speech_buffer)
                        else:
                            silence_frames += 1
                            
                            # 检测到静音 → 进入 ENDING
                            if silence_frames >= 1:
                                print(f"[SpeechSegmenter] Silence detected, entering ENDING")
                                state = SegmentState.ENDING
                    
                    elif state == SegmentState.ENDING:
                        speech_buffer.append(frame)
                        
                        if is_speech:
                            # 又开始说话 → 回到 SPEAKING
                            print(f"[SpeechSegmenter] Speech resumed, back to SPEAKING")
                            state = SegmentState.SPEAKING
                            speech_frames += 1
                            silence_frames = 0
                        else:
                            silence_frames += 1
                            
                            # 静音足够长 → 结束
                            if silence_frames >= self.silence_frames:
                                print(f"[SpeechSegmenter] Speech ended at frame {total_frames}")
                                print(f"  Total speech frames: {speech_frames}")
                                print(f"  Duration: {speech_frames * self.vad.frame_duration_ms}ms")
                                
                                # 添加后置填充（如果有）
                                post_padding_count = 0
                                while post_padding_count < self.post_padding_frames:
                                    post_frame = recorder.read(frame_size)
                                    if post_frame:
                                        speech_buffer.append(post_frame)
                                        post_padding_count += 1
                                    else:
                                        break
                                
                                return b''.join(speech_buffer)
                
            finally:
                if recorder.is_recording():
                    recorder.stop()
        
        # 在线程池中执行
        result = await asyncio.get_event_loop().run_in_executor(None, record_loop)
        
        if result:
            print(f"[SpeechSegmenter] Captured {len(result)} bytes of speech")
        else:
            print(f"[SpeechSegmenter] No speech detected")
        
        return result
    
    def get_config(self) -> dict:
        """获取当前配置
        
        Returns:
            配置字典
        """
        return {
            "min_speech_duration_ms": self.min_speech_duration_ms,
            "max_speech_duration_ms": self.max_speech_duration_ms,
            "silence_duration_ms": self.silence_duration_ms,
            "pre_speech_padding_ms": self.pre_speech_padding_ms,
            "post_speech_padding_ms": self.post_speech_padding_ms,
            "sample_rate": self.sample_rate,
            "min_speech_frames": self.min_speech_frames,
            "max_speech_frames": self.max_speech_frames,
            "silence_frames": self.silence_frames
        }


# 便捷函数
def create_speech_segmenter(
    sample_rate: int = 16000,
    vad_aggressiveness: int = 2,
    min_speech_ms: int = 500,
    max_speech_ms: int = 15000,
    silence_ms: int = 500
) -> SpeechSegmenter:
    """创建语音分段器的便捷函数
    
    Args:
        sample_rate: 采样率
        vad_aggressiveness: VAD 激进度
        min_speech_ms: 最短语音时长
        max_speech_ms: 最长语音时长
        silence_ms: 静音判定时长
        
    Returns:
        SpeechSegmenter 实例
    """
    from util.vad_detector import create_vad
    
    vad = create_vad(
        sample_rate=sample_rate,
        aggressiveness=vad_aggressiveness,
        frame_duration_ms=30
    )
    
    return SpeechSegmenter(
        vad_detector=vad,
        min_speech_duration_ms=min_speech_ms,
        max_speech_duration_ms=max_speech_ms,
        silence_duration_ms=silence_ms,
        sample_rate=sample_rate
    )