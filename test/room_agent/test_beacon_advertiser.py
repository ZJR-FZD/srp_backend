# tests/room_agent/test_beacon_advertiser.py
"""BLE Beacon广播器测试"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
import asyncio

from core.room_agent.beacon.beacon_config import BeaconConfig
from core.room_agent.beacon.beacon_advertiser import BeaconAdvertiser


@pytest.mark.asyncio
class TestBeaconAdvertiser:
    """BeaconAdvertiser测试"""

    @pytest.mark.asyncio
    async def test_init(self):
        """测试初始化"""
        config = BeaconConfig(
            uuid="012345678-0001-0002-0003-0004-0005",
            major=1,
            minor=0,
            measured_power=-59,
            interval=1,
            enabled=False  # 测试时不启用
        )

        advertiser = BeaconAdvertiser(config)

        assert advertiser.config == config
        assert advertiser._running is False

    @pytest.mark.asyncio
    async def test_start_success(self):
        """测试成功启动"""
        config = BeaconConfig(
            uuid="012345678-0001-0002-0003-0004-0005",
            major=1,
            minor=0,
            measured_power=-59,
            interval=1,
            enabled=True
        )

        advertiser = BeaconAdvertiser(config)

        # Mock bluepy
        with patch('core.room_agent.beacon.beacon_advertiser.BLUEPY_AVAILABLE', False):
            with patch('core.room_agent.beacon.beacon_advertiser.Peripheral') as mock_peripheral:
                # Mock方法
                mock_peripheral.return_value = Mock()
                mock_peripheral.return_value.setAdvertisingType = Mock()

                await advertiser.start()

                # 验证
                assert advertiser._running is True
                advertiser.peripheral.start_advertising.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_disabled(self):
        """测试启动已禁用的beacon"""
        config = BeaconConfig(
            uuid="012345678-0001-0002-0003-0004-0005",
            major=1,
            minor=0,
            measured_power=-59,
            interval=1,
            enabled=False  # 禁用
        )

        advertiser = BeaconAdvertiser(config)
        await advertiser.start()

        # 不应该启动
        assert advertiser._running is False

    @pytest.mark.asyncio
    async def test_stop(self):
        """测试停止"""
        config = BeaconConfig(
            uuid="012345678-0001-0002-0003-0004-0005",
            major=1,
            minor=0,
            measured_power=-59,
            interval=1,
            enabled=False
        )

        advertiser = BeaconAdvertiser(config)

        # Mock bluepy
        with patch('core.room_agent.beacon.beacon_advertiser.BLUEPY_AVAILABLE', False):
            with patch('core.room_agent.beacon.beacon_advertiser.Peripheral') as mock_peripheral:
                mock_peripheral.return_value = Mock()

                # 先启动
                advertiser.peripheral = mock_peripheral.return_value
                advertiser._running = True

                # 测试停止
                await advertiser.stop()

                # 验证
                assert advertiser._running is False
                mock_peripheral.stop_advertising.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_config(self):
        """测试更新配置"""
        config1 = BeaconConfig(
            uuid="012345678-0001-0002-0003-0004-0005",
            major=1,
            minor=0,
            measured_power=-59,
            interval=1,
            enabled=True
        )

        advertiser = BeaconAdvertiser(config1)

        # Mock bluepy
        with patch('core.room_agent.beacon.beacon_advertiser.BLUEPY_AVAILABLE', False):
            with patch('core.room_agent.beacon.beacon_advertiser.Peripheral') as mock_peripheral:
                mock_peripheral.return_value = Mock()
                mock_peripheral.return_value.setAdvertisingType = Mock()

                await advertiser.start()

                # 更新配置
                config2 = BeaconConfig(
                    uuid=config1.uuid,
                    major=config1.major,
                    minor=config1.minor + 1,  # 修改minor
                    measured_power=config1.measured_power,
                    interval=config1.interval,
                    enabled=True
                )

                await advertiser.update_config(config2)

                # 验证配置已更新
                assert advertiser.config.minor == 1

    @pytest.mark.asyncio
    async def test_is_running(self):
        """测试运行状态"""
        config = BeaconConfig(
            uuid="012345678-0001-0002-0003-0004-0005",
            major=1,
            minor=0,
            measured_power=-59,
            interval=1,
            enabled=True
        )

        advertiser = BeaconAdvertiser(config)

        # 未启动时
        assert advertiser.is_running() is False

        # Mock bluepy并启动
        with patch('core.room_agent.beacon.beacon_advertiser.BLUEPY_AVAILABLE', False):
            with patch('core.room_agent.beacon.beacon_advertiser.Peripheral') as mock_peripheral:
                mock_peripheral.return_value = Mock()
                mock_peripheral.return_value.setAdvertisingType = Mock()

                await advertiser.start()

                # 现在应该是运行
                assert advertiser.is_running() is True

    @pytest.mark.asyncio
    async def test_beacon_info(self):
        """测试获取beacon信息"""
        config = BeaconConfig(
            uuid="012345678-0001-0002-0003-0004-0005",
            major=1,
            minor=0,
            measured_power=-59,
            interval=1,
            enabled=True
        )

        advertiser = BeaconAdvertiser(config)

        info = advertiser.beacon_info

        assert info["uuid"] == config.uuid
        assert info["major"] == 1
        assert info["minor"] == 0
        assert info["measured_power"] == -59
        assert info["interval_seconds"] == 1
        assert info["enabled"] is True
        assert info["running"] == config._running
        assert "bluepy_available"] in info
