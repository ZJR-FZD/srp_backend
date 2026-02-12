# tests/room_agent/test_beacon_config.py
"""BLE Beacon配置测试"""
import pytest
from core.room_agent.beacon.beacon_config import BeaconConfig


class TestBeaconConfig:
    """BeaconConfig测试"""

    def test_from_dict_valid(self):
        """测试从字典创建配置"""
        config_dict = {
            "uuid": "012345678-0001-0002-0003-0004-0005",
            "major": 1,
            "minor": 0,
            "measured_power": -59,
            "interval": 1,
            "enabled": True
        }

        config = BeaconConfig.from_dict(config_dict)

        assert config.uuid == "012345678-0001-0002-0003-0004-0005"
        assert config.major == 1
        assert config.minor == 0
        assert config.measured_power == -59
        assert config.interval == 1
        assert config.enabled is True

    def test_from_dict_default_values(self):
        """测试默认值"""
        config_dict = {
            "enabled": True
        }

        config = BeaconConfig.from_dict(config_dict)

        # 应该生成随机UUID
        assert config.uuid is not None
        assert len(config.uuid) == 36  # UUID v4格式
        assert config.major == 0
        assert config.minor == 0
        assert config.measured_power == -59
        assert config.interval == 1

    def test_invalid_uuid_format(self):
        """测试无效UUID格式"""
        config_dict = {
            "uuid": "invalid-uuid",
            "major": 1,
            "minor": 0
        }

        with pytest.raises(ValueError, match="Invalid UUID format"):
            BeaconConfig.from_dict(config_dict)

    def test_invalid_major_range(self):
        """测试无效Major值"""
        config_dict = {
            "uuid": "012345678-0001-0002-0003-0004-0005",
            "major": 70000,  # 超出范围
            "minor": 0
        }

        with pytest.raises(ValueError, match="Major must be 0-65535"):
            BeaconConfig.from_dict(config_dict)

    def test_invalid_minor_range(self):
        """测试无效Minor值"""
        config_dict = {
            "uuid": "012345678-0001-0002-0003-0004-0005",
            "major": 1,
            "minor": 70000  # 超出范围
        }

        with pytest.raises(ValueError, match="Minor must be 0-65535"):
            BeaconConfig.from_dict(config_dict)

    def test_invalid_measured_power(self):
        """测试无效Measured Power"""
        config_dict = {
            "uuid": "012345678-0001-0002-0003-0004-0005",
            "major": 1,
            "minor": 0,
            "measured_power": -101  # 小于-100
        }

        with pytest.raises(ValueError, match="Measured power must be -100 to 0"):
            BeaconConfig.from_dict(config_dict)

    def test_invalid_interval(self):
        """测试无效Interval"""
        config_dict = {
            "uuid": "012345678-0001-0002-0003-0004-0005",
            "major": 1,
            "minor": 0,
            "interval": 0  # 小于1秒
        }

        with pytest.raises(ValueError, match="Interval must be >= 1 second"):
            BeaconConfig.from_dict(config_dict)

    def test_to_dict(self):
        """测试转换为字典"""
        config = BeaconConfig(
            uuid="012345678-0001-0002-0003-0004-0005",
            major=1,
            minor=0,
            measured_power=-59,
            interval=1,
            enabled=True
        )

        config_dict = config.to_dict()

        assert config_dict["uuid"] == "012345678-0001-0002-0003-0004-0005"
        assert config_dict["major"] == 1
        assert config_dict["minor"] == 0
        assert config_dict["measured_power"] == -59
        assert config_dict["interval"] == 1
        assert config_dict["enabled"] is True

    def test_get_advertising_interval_ms(self):
        """测试获取广播间隔（毫秒）"""
        config = BeaconConfig(
            uuid="012345678-0001-0002-0003-0004-0005",
            major=1,
            minor=0,
            measured_power=-59,
            interval=2  # 2秒
        )

        interval_ms = config.get_advertising_interval_ms()

        assert interval_ms == 2000  # 2秒 = 2000毫秒
