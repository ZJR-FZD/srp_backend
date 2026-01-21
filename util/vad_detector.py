"""VAD (Voice Activity Detection) 检测器

使用 WebRTC VAD 检测语音活动
"""

import struct
from typing import Optional


class VADDetector:
    """语音活动检测器
    
    基于 WebRTC VAD 实现，用于实时检测音频中的语音活动
    """
    
    def __init__(
        self,
        sample_rate: int = 16000,
        aggressiveness: int = 2,
        frame_duration_ms: int = 30
    ):
        """初始化 VAD 检测器
        
        Args:
            sample_rate: 采样率，支持 8000/16000/32000/48000 Hz
            aggressiveness: 激进度 0-3
                0: 质量优先（可能误判噪音为语音）
                1: 低激进度
                2: 中等（推荐）
                3: 高激进度（减少误判，但可能漏掉弱音）
            frame_duration_ms: 帧时长，支持 10/20/30 ms
        """
        # 验证参数
        if sample_rate not in [8000, 16000, 32000, 48000]:
            raise ValueError(f"Unsupported sample rate: {sample_rate}")
        
        if aggressiveness not in [0, 1, 2, 3]:
            raise ValueError(f"Aggressiveness must be 0-3, got {aggressiveness}")
        
        if frame_duration_ms not in [10, 20, 30]:
            raise ValueError(f"Frame duration must be 10/20/30 ms, got {frame_duration_ms}")
        
        self.sample_rate = sample_rate
        self.aggressiveness = aggressiveness
        self.frame_duration_ms = frame_duration_ms
        
        # 计算每帧的样本数和字节数
        self.frame_samples = int(sample_rate * frame_duration_ms / 1000)
        self.frame_bytes = self.frame_samples * 2  # 16-bit = 2 bytes
        
        # 尝试导入 webrtcvad
        try:
            import webrtcvad
            self.vad = webrtcvad.Vad(aggressiveness)
            self.backend = "webrtcvad"
            print(f"[VADDetector] Initialized with WebRTC VAD")
            print(f"[VADDetector] Sample rate: {sample_rate}Hz, Aggressiveness: {aggressiveness}")
            print(f"[VADDetector] Frame duration: {frame_duration_ms}ms, Frame bytes: {self.frame_bytes}")
        except ImportError:
            print("[VADDetector] Warning: webrtcvad not installed, using energy-based fallback")
            self.vad = None
            self.backend = "energy"
            # 能量阈值（简单的能量检测作为后备）
            self.energy_threshold = 500
    
    def is_speech(self, audio_frame: bytes) -> bool:
        """检测音频帧是否包含语音
        
        Args:
            audio_frame: PCM 音频数据（16-bit, 单声道）
                        长度必须等于 frame_bytes
        
        Returns:
            True: 检测到语音
            False: 静音或噪音
        """
        # 验证帧长度
        if len(audio_frame) != self.frame_bytes:
            # 如果长度不匹配，尝试调整
            if len(audio_frame) < self.frame_bytes:
                # 填充静音
                audio_frame = audio_frame + b'\x00' * (self.frame_bytes - len(audio_frame))
            else:
                # 截断
                audio_frame = audio_frame[:self.frame_bytes]
        
        if self.backend == "webrtcvad":
            try:
                return self.vad.is_speech(audio_frame, self.sample_rate)
            except Exception as e:
                print(f"[VADDetector] Error in is_speech: {e}")
                # 降级到能量检测
                return self._energy_based_detection(audio_frame)
        else:
            return self._energy_based_detection(audio_frame)
    
    def _energy_based_detection(self, audio_frame: bytes) -> bool:
        """基于能量的简单语音检测（后备方案）
        
        Args:
            audio_frame: PCM 音频数据
            
        Returns:
            True: 能量超过阈值
            False: 能量低于阈值
        """
        # 将字节转换为 16-bit 整数
        samples = struct.unpack(f'{len(audio_frame) // 2}h', audio_frame)
        
        # 计算能量（RMS）
        energy = sum(s * s for s in samples) / len(samples)
        rms = energy ** 0.5
        
        return rms > self.energy_threshold
    
    def set_aggressiveness(self, aggressiveness: int):
        """动态调整激进度
        
        Args:
            aggressiveness: 0-3
        """
        if aggressiveness not in [0, 1, 2, 3]:
            raise ValueError(f"Aggressiveness must be 0-3, got {aggressiveness}")
        
        self.aggressiveness = aggressiveness
        
        if self.backend == "webrtcvad":
            self.vad.set_mode(aggressiveness)
            print(f"[VADDetector] Aggressiveness updated to {aggressiveness}")
    
    def get_frame_size(self) -> int:
        """获取每帧需要的字节数
        
        Returns:
            帧字节数
        """
        return self.frame_bytes
    
    def process_audio_buffer(self, audio_buffer: bytes) -> list[tuple[bool, bytes]]:
        """处理音频缓冲区，分帧检测
        
        Args:
            audio_buffer: 完整的音频缓冲区
            
        Returns:
            列表，每个元素为 (is_speech, frame_data)
        """
        results = []
        
        # 按帧切分
        num_frames = len(audio_buffer) // self.frame_bytes
        
        for i in range(num_frames):
            start = i * self.frame_bytes
            end = start + self.frame_bytes
            frame = audio_buffer[start:end]
            
            is_speech = self.is_speech(frame)
            results.append((is_speech, frame))
        
        return results
    
    def get_config(self) -> dict:
        """获取当前配置
        
        Returns:
            配置字典
        """
        return {
            "backend": self.backend,
            "sample_rate": self.sample_rate,
            "aggressiveness": self.aggressiveness,
            "frame_duration_ms": self.frame_duration_ms,
            "frame_bytes": self.frame_bytes,
            "frame_samples": self.frame_samples
        }


# 便捷函数
def create_vad(
    sample_rate: int = 16000,
    aggressiveness: int = 2,
    frame_duration_ms: int = 30
) -> VADDetector:
    """创建 VAD 检测器的便捷函数
    
    Args:
        sample_rate: 采样率
        aggressiveness: 激进度 0-3
        frame_duration_ms: 帧时长 10/20/30 ms
        
    Returns:
        VADDetector 实例
    """
    return VADDetector(sample_rate, aggressiveness, frame_duration_ms)


if __name__ == "__main__":
    # 测试代码
    print("=== VADDetector 测试 ===\n")
    
    # 创建检测器
    vad = create_vad(sample_rate=16000, aggressiveness=2)
    
    print("\n配置信息:")
    config = vad.get_config()
    for key, value in config.items():
        print(f"  {key}: {value}")
    
    # 测试静音帧
    print("\n测试静音帧:")
    silence_frame = b'\x00' * vad.get_frame_size()
    is_speech = vad.is_speech(silence_frame)
    print(f"  静音检测结果: {is_speech} (应该是 False)")
    
    # 测试噪音帧
    print("\n测试噪音帧:")
    import random
    noise_frame = bytes([random.randint(0, 255) for _ in range(vad.get_frame_size())])
    is_speech = vad.is_speech(noise_frame)
    print(f"  噪音检测结果: {is_speech}")
    
    print("\n✅ VADDetector 测试完成")