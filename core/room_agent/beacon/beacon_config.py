# core/room_agent/beacon/beacon_config.py
"""BLE Beacon配置管理

管理BLE Beacon的配置参数和验证
"""

import uuid
from typing import Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class BeaconConfig:
    """BLE Beacon配置

    符合HomeSystemAgent.md规范的BLE Beacon配置

    Attributes:
        uuid: System-specific UUID (16 bytes)
        major: Room identifier (0-65535)
        minor: Zone/Position in room (0-65535)
        measured_power: Calibrated RSSI at 1 meter (-59 for standard beacon)
        interval: Broadcast interval in seconds
        enabled: Whether beacon is enabled
    """
    # UUID: 16字节标识符
    uuid: str = field(...)

    # Major值：房间标识符 (0-65535)
    major: int = field(default=0)

    # Minor值：区域内位置 (0-65535)
    minor: int = field(default=0)

    # Measured Power: 1米处的校准RSSI值
    measured_power: int = field(default=-59)

    # 广播间隔（秒）
    interval: int = field(default=1)

    # 是否启用
    enabled: bool = field(default=True)

    def __post_init__(self):
        """初始化后验证"""
        # 验证UUID格式
        try:
            uuid.UUID(self.uuid)
        except ValueError:
            raise ValueError(f"Invalid UUID format: {self.uuid}")

        # 验证Major范围
        if not (0 <= self.major <= 65535):
            raise ValueError(f"Major must be 0-65535, got: {self.major}")

        # 验证Minor范围
        if not (0 <= self.minor <= 65535):
            raise ValueError(f"Minor must be 0-65535, got: {self.minor}")

        # 验证Measured Power范围
        if not (-100 <= self.measured_power <= 0):
            raise ValueError(f"Measured power must be -100 to 0, got: {self.measured_power}")

        # 验证Interval
        if self.interval < 1:
            raise ValueError(f"Interval must be >= 1 second, got: {self.interval}")

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> 'BeaconConfig':
        """从字典创建配置

        Args:
            config: 配置字典

        Returns:
            BeaconConfig: 配置对象
        """
        return cls(
            uuid=config.get("uuid", str(uuid.uuid4())),  # 默认生成随机UUID
            major=config.get("major", 0),
            minor=config.get("minor", 0),
            measured_power=config.get("measured_power", -59),
            interval=config.get("interval", 1),
            enabled=config.get("enabled", True)
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典

        Returns:
            Dict[str, Any]: 配置字典
        """
        return {
            "uuid": self.uuid,
            "major": self.major,
            "minor": self.minor,
            "measured_power": self.measured_power,
            "interval": self.interval,
            "enabled": self.enabled
        }

    def validate_for_hardware(self, platform: str = "linux") -> bool:
        """验证硬件支持

        Args:
            platform: 目标平台

        Returns:
            bool: 是否支持
        """
        # TODO: 检查平台是否支持BLE
        # Jetson Linux (ARM64) 通常支持bluepy
        return True

    def get_advertising_interval_ms(self) -> int:
        """获取广播间隔（毫秒）

        Returns:
            int: 间隔毫秒数
        """
        return self.interval * 1000
