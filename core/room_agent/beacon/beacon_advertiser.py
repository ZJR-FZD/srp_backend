# core/room_agent/beacon/beacon_advertiser.py
"""BLE Beacon广播器

使用bluepy库实现BLE Beacon广播功能
"""

import asyncio
import time
from typing import Optional, Dict, Any
from datetime import datetime

try:
    from bluepy.peripheral import Peripheral, Advertisement
    from bluepy.btle import BTLE
    BLUEPY_AVAILABLE = True
except ImportError:
    BLUEPY_AVAILABLE = False

from core.room_agent.beacon.beacon_config import BeaconConfig
import config


class BeaconAdvertiser:
    """BLE Beacon广播器

    职责：
    - BLE Beacon广播
    - 支持启动/停止/更新
    """

    def __init__(self, beacon_config: BeaconConfig):
        """初始化BLE Beacon广播器

        Args:
            beacon_config: Beacon配置对象
        """
        if not BLUEPY_AVAILABLE:
            raise RuntimeError("bluepy library not installed. Install with: pip install bluepy")

        self.config = beacon_config
        self.peripheral: Optional[Peripheral] = None
        self.advertisement: Optional[Advertisement] = None
        self._running = False

        # 日志
        print(f"[BeaconAdvertiser] Initialized for room {self.config.major}")
        print(f"  UUID: {self.config.uuid}")
        print(f"  Major: {self.config.major} (room)")
        print(f"  Minor: {self.config.minor} (zone)")

    async def _get_local_mac(self) -> str:
        """获取本地蓝牙适配器MAC地址

        Returns:
            str: MAC地址（XX:XX:XX:XX:XX格式）
        """
        # TODO: 获取实际的蓝牙适配器MAC
        # 这里使用mock地址，实际部署时需要替换
        return "00:11:22:33:44:55"

    async def start(self) -> bool:
        """开始BLE Beacon广播

        Returns:
            bool: 是否成功启动
        """
        if not self.config.enabled:
            print("[BeaconAdvertiser] Beacon is disabled in config")
            return False

        if self._running:
            print("[BeaconAdvertiser] Already running")
            return True

        try:
            print("[BeaconAdvertiser] Starting BLE Beacon advertising...")

            # 获取本地MAC地址
            mac_address = await self._get_local_mac()

            # 创建外设
            self.peripheral = Periferal(deviceAddr=mac_address, interface=0)

            # 设置广播类型为BLE
            self.peripheral.set_advertising_type(
                advType=0,  # BLE Advertising
            )

            # 创建广播数据
            self.advertisement = Advertisement(
                serviceUuid=self.config.uuid,
                major=self.config.major,
                minor=self.config.minor,
            )

            # 设置校准RSSI值
            self.advertisement.txPower = self.config.measured_power

            # 设置广播间隔
            interval_ms = self.config.get_advertising_interval_ms()
            self.peripheral.setAdvertisingInterval(
                minInterval=interval_ms,
                maxInterval=interval_ms,
            )

            print(f"[BeaconAdvertiser] Configured advertising:")
            print(f"  MAC: {mac_address}")
            print(f"  Service UUID: {self.config.uuid}")
            print(f"  Major: {self.config.major} (room)")
            print(f"  Minor: {self.config.minor} (zone)")
            print(f"  Measured Power: {self.config.measured_power} dBm")
            print(f"  Interval: {interval_ms}ms ({interval_ms/1000}s)")

            # 启动广播
            self.peripheral.start_advertising(
                advertisement=self.advertisement,
            respType=0,  # BLE Response Type
            )

            self._running = True
            print("[BeaconAdvertiser] BLE Beacon advertising started successfully")

            return True

        except Exception as e:
            print(f"[BeaconAdvertiser] Failed to start: {e}")
            raise

    async def stop(self) -> None:
        """停止BLE Beacon广播"""
        if not self._running:
            print("[BeaconAdvertiser] Not running")
            return

        print("[BeaconAdvertiser] Stopping BLE Beacon advertising...")

        self._running = False

        if self.peripheral:
            try:
                self.peripheral.stop_advertising()
                print("[BeaconAdvertiser] BLE Beacon advertising stopped")
            except Exception as e:
                print(f"[BeaconAdvertiser] Error stopping advertising: {e}")

    async def update_config(self, new_config: BeaconConfig) -> None:
        """更新Beacon配置

        Args:
            new_config: 新的配置
        """
        was_running = self._running

        # 如果正在运行，先停止
        if was_running:
            await self.stop()

        # 更新配置
        self.config = new_config

        # 如果之前是启用的，重新启动
        if was_running and new_config.enabled:
            await self.start()

    def is_running(self) -> bool:
        """检查是否正在运行

        Returns:
            bool: 是否正在广播
        """
        return self._running

    @property
    def beacon_info(self) -> Dict[str, Any]:
        """获取Beacon信息（用于显示）

        Returns:
            Dict[str, Any]: Beacon信息
        """
        return {
            "uuid": self.config.uuid,
            "major": self.config.major,
            "minor": self.config.minor,
            "measured_power": self.config.measured_power,
            "interval_seconds": self.config.interval,
            "enabled": self.config.enabled,
            "running": self._running,
            "bluepy_available": BLUEPY_AVAILABLE
        }
