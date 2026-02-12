# core/room_agent/mdns/advertiser.py
"""mDNS服务广播器

使用zeroconf库注册和广播Room Agent服务
"""

import socket
from typing import Dict, Any, Optional

from zeroconf import ServiceInfo, Zeroconf

import config


class MdnsAdvertiser:
    """mDNS服务广播器

    职责：
    - 注册_room-agent._tcp.local服务
    - 广播TXT记录（room_id, mqtt_port等）
    """

    def __init__(self, config: Dict[str, Any]):
        """初始化mDNS广播器

        Args:
            config: 配置字典
                - room_id: 房间ID
                - agent_id: Agent ID
                - mqtt_port: MQTT端口
                - mqtt_ws_port: MQTT WebSocket端口（可选）
                - version: Agent版本
                - capabilities: Agent能力列表
        """
        self.room_id = config.get("room_id", "default-room")
        self.agent_id = config.get("agent_id", "room-agent-default")
        self.mqtt_port = config.get("mqtt_port", 1883)
        self.mqtt_ws_port = config.get("mqtt_ws_port")
        self.version = config.get("version", "1.0.0")
        self.capabilities = config.get("capabilities", [])

        # mDNS配置
        self.service_type = "_room-agent._tcp.local"
        self.service_name = f"{self.room_id}-room-agent"

        # Zeroconf实例
        self.zeroconf: Optional[Zeroconf] = None

        # 获取本地IP地址
        self.local_ip = self._get_local_ip()

        print(f"[MdnsAdvertiser] Initialized for {self.service_name} (room: {self.room_id})")

    def _get_local_ip(self) -> str:
        """获取本地IP地址

        Returns:
            str: 本地IP地址
        """
        try:
            # 创建一个UDP socket连接到公共DNS服务器
            # 这会返回本地的IP地址
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.settimeout(0)
                try:
                    # 连接到8.8.8.8（Google DNS）不会实际发送数据
                    s.connect(('8.8.8.8', 80))
                    local_ip = s.getsockname()[0]
                except:
                    # 如果失败，使用127.0.0.1
                    local_ip = '127.0.0.1'
        except Exception:
            local_ip = '127.0.0.1'

        return local_ip

    async def start(self):
        """开始广播mDNS服务"""
        try:
            # 构建TXT记录
            txt_records = {
                b"room_id": self.room_id.encode('utf-8'),
                b"mqtt_port": str(self.mqtt_port).encode('utf-8'),
                b"agent_id": self.agent_id.encode('utf-8'),
                b"version": self.version.encode('utf-8'),
            }

            # 添加可选的WebSocket端口
            if self.mqtt_ws_port:
                txt_records[b"mqtt_ws_port"] = str(self.mqtt_ws_port).encode('utf-8')

            # 添加能力列表（如果提供）
            if self.capabilities:
                capabilities_str = ','.join(self.capabilities)
                txt_records[b"capabilities"] = capabilities_str.encode('utf-8')

            # 创建ServiceInfo
            info = ServiceInfo(
                type_=self.service_type,
                name=f"{self.service_name}.{self.service_type}",
                addresses=[socket.inet_aton(self.local_ip)],
                port=self.mqtt_port,
                properties=txt_records
            )

            # 创建Zeroconf并注册服务
            self.zeroconf = Zeroconf()
            self.zeroconf.register_service(info, ttl=60)  # TTL 60秒

            print(f"[MdnsAdvertiser] Started mDNS advertising:")
            print(f"  - Service: {self.service_name}")
            print(f"  - Type: {self.service_type}")
            print(f"  - IP: {self.local_ip}:{self.mqtt_port}")
            print(f"  - TXT Records:")
            for key, value in txt_records.items():
                print(f"    {key.decode()}: {value.decode()}")

        except Exception as e:
            print(f"[MdnsAdvertiser] Failed to start: {e}")
            raise

    async def stop(self):
        """停止mDNS广播"""
        if self.zeroconf:
            try:
                self.zeroconf.close()
                print("[MdnsAdvertiser] Stopped mDNS advertising")
            except Exception as e:
                print(f"[MdnsAdvertiser] Error stopping: {e}")

    @property
    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self.zeroconf is not None
