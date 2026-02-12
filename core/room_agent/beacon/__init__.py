# core/room_agent/beacon/__init__.py
"""BLE Beacon模块导出"""

from core.room_agent.beacon.beacon_config import BeaconConfig
from core.room_agent.beacon.beacon_advertiser import BeaconAdvertiser

__all__ = ["BeaconConfig", "BeaconAdvertiser"]
