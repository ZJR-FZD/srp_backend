# tests/room_agent/test_room_agent_beacon_integration.py
"""Room Agent BLE Beacon集成测试"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
import asyncio

from core.room_agent.room_agent import RoomAgent


@pytest.mark.asyncio
class TestRoomAgentBeaconIntegration:
    """Room Agent BLE Beacon集成测试"""

    @pytest.mark.asyncio
    async def test_room_agent_with_beacon(self, mock_agent_config):
        """测试Room Agent初始化时包含beacon"""
        # 添加beacon配置
        mock_agent_config["beacon"] = {
            "enabled": True,
            "uuid": "012345678-0001-0002-0003-0004-0005",
            "major": 1,
            "minor": 0
            "measured_power": -59,
            "interval": 1
        }

        agent = RoomAgent(
            room_id="test-room",
            agent_config=mock_agent_config
        )

        # 验证beacon advertiser已初始化
        assert agent.beacon_advertiser is not None
        assert agent.beacon_advertiser.config is not None

    @pytest.mark.asyncio
    async def test_start_with_beacon(self, mock_agent_config):
        """测试启动时beacon也启动"""
        # 添加beacon配置（禁用，避免实际蓝牙操作）
        mock_agent_config["beacon"] = {
            "enabled": False,
            "uuid": "012345678-0001-0002-0003-0004-0005",
            "major": 1,
            "minor": 0,
            "measured_power": -59,
            "interval": 1
        }

        agent = RoomAgent(
            room_id="test-room",
            agent_config=mock_agent_config
        )

        # Mock其他组件
        with patch('core.room_agent.room_agent.RoomAgent.mqtt_client') as mock_mqtt:
        with patch('core.room_agent.room_agent.RoomAgent.mdns_advertiser') as mock_mdns:
            mock_mqtt.return_value.is_connected = AsyncMock(return_value=False)
            mock_mdns.return_value.is_running = False

            # Mock beacon advertiser的bluepy
            with patch('core.room_agent.beacon.beacon_advertiser.BLUEPY_AVAILABLE', False):
                with patch('core.room_agent.beacon.beacon_advertiser.Peripheral') as mock_peripheral:
                    mock_peripheral.return_value = Mock()
                    mock_peripheral.return_value.setAdvertisingType = Mock()

                    await agent.start()

                    # 验证beacon advertiser被启动
                    assert agent.beacon_advertiser._running is True

    @pytest.mark.asyncio
    async def test_stop_with_beacon(self, mock_agent_config):
        """测试停止时beacon也停止"""
        # 添加beacon配置
        mock_agent_config["beacon"] = {
            "enabled": True,
            "uuid": "012345678-0001-0002-0003-0004-0005",
            "major": 1,
            "minor": 0,
            "measured_power": -59,
            "interval": 1
        }

        agent = RoomAgent(
            room_id="test-room",
            agent_config=mock_agent_config
        )

        # Mock beacon advertiser的bluepy
        with patch('core.room_agent.beacon.beacon_advertiser.BLUEPY_AVAILABLE', False):
            with patch('core.room_agent.beacon.beacon_advertiser.Peripheral') as mock_peripheral:
                mock_peripheral.return_value = Mock()
                mock_peripheral.return_value.setAdvertisingType = Mock()

                # 启动
                await agent.start()
                assert agent.beacon_advertiser._running is True

                # 停止
                await agent.stop()

                # 验证beacon advertiser被停止
                assert agent.beacon_advertiser._running is False

    @pytest.mark.asyncio
    async def test_beacon_disabled(self, mock_agent_config):
        """测试beacon禁用时不会启动"""
        # 添加beacon配置（禁用）
        mock_agent_config["beacon"] = {
            "enabled": False,
            "uuid": "012345678-0001-0002-0003-0004-0005",
            "major": 1,
            "minor": 0,
            "measured_power": -59,
            "interval": 1
        }

        agent = RoomAgent(
            room_id="test-room",
            agent_config=mock_agent_config
        )

        # Mock其他组件
        with patch('core.room_agent.room_agent.RoomAgent.mqtt_client') as mock_mqtt:
        with patch('core.room_agent.room_agent.RoomAgent.mdns_advertiser') as mock_mdns:
                mock_mqtt.return_value.is_connected = AsyncMock(return_value=False)
                mock_mdns.return_value.is_running = False

                # 启动
                await agent.start()

                # 验证beacon advertiser未被启动（禁用）
                assert agent.beacon_advertiser._running is False
