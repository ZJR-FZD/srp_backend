# tests/conftest.py
"""Pytest配置和共享fixtures"""
import pytest
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def event_loop():
    """创建事件循环fixture"""
    import asyncio
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_mqtt_config():
    """MQTT配置fixture"""
    return {
        "host": "localhost",
        "port": 1883,
        "username": None,
        "password": None
    }


@pytest.fixture
def mock_mdns_config():
    """mDNS配置fixture"""
    return {
        "room_id": "test-bedroom",
        "agent_id": "test-room-agent-1",
        "mqtt_port": 1883,
        "mqtt_ws_port": 9001,
        "version": "1.0.0",
        "capabilities": ["device_control", "scene_activation"]
    }


@pytest.fixture
def mock_agent_config():
    """Room Agent配置fixture"""
    return {
        "agent": {
            "id": "test-room-agent-1",
            "room_id": "test-bedroom",
            "version": "1.0.0",
            "capabilities": ["device_control", "scene_activation"]
        },
        "mqtt": {
            "broker": {
                "host": "localhost",
                "port": 1883
            }
        },
        "mdns": {
            "room_id": "test-bedroom",
            "agent_id": "test-room-agent-1",
            "mqtt_port": 1883,
            "mqtt_ws_port": 9001
        },
        "heartbeat": {
            "interval": 30
        }
    }
