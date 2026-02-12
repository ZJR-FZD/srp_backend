# tests/room_agent/test_mdns_advertiser.py
"""mDNS广播器测试"""
import pytest
from unittest.mock import Mock, patch
import socket

from core.room_agent.mdns.advertiser import MdnsAdvertiser


class TestMdnsAdvertiser:
    """mDNS广播器测试"""

    def test_init(self, mock_mdns_config):
        """测试初始化"""
        advertiser = MdnsAdvertiser(mock_mdns_config)

        assert advertiser.room_id == "test-bedroom"
        assert advertiser.agent_id == "test-room-agent-1"
        assert advertiser.mqtt_port == 1883
        assert advertiser.local_ip is not None
        assert advertiser.service_type == "_room-agent._tcp.local"

    def test_get_local_ip(self, mock_mdns_config):
        """测试获取本地IP"""
        advertiser = MdnsAdvertiser(mock_mdns_config)

        local_ip = advertiser._get_local_ip()

        assert local_ip is not None
        # 应该是有效的IP地址格式
        parts = local_ip.split('.')
        assert len(parts) == 4

    @pytest.mark.asyncio
    async def test_start(self, mock_mdns_config):
        """测试启动mDNS广播"""
        advertiser = MdnsAdvertiser(mock_mdns_config)

        # Mock zeroconf.Zeroconf
        with patch('core.room_agent.mdns.advertiser.Zeroconf') as mock_zeroconf:
            mock_zeroconf.return_value = Mock()

            # 测试启动
            await advertiser.start()

            assert advertiser.zeroconf is not None
            # 验证register_service被调用
            advertiser.zeroconf.register_service.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop(self, mock_mdns_config):
        """测试停止mDNS广播"""
        advertiser = MdnsAdvertiser(mock_mdns_config)

        # Mock zeroconf
        with patch('core.room_agent.mdns.advertiser.Zeroconf') as mock_zeroconf:
            mock_zeroconf.return_value = Mock()
            advertiser.zeroconf = mock_zeroconf.return_value

            # 先启动
            await advertiser.start()

            # 测试停止
            await advertiser.stop()

            # 验证close被调用
            advertiser.zeroconf.close.assert_called_once()

    def test_is_running(self, mock_mdns_config):
        """测试检查是否运行"""
        advertiser = MdnsAdvertiser(mock_mdns_config)

        # 未启动时
        assert advertiser.is_running is False
