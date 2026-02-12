# core/room_agent/room_agent.py
"""Room Agent主类

继承RobotAgent，添加Room Agent特有能力：
- MQTT客户端连接管理
- mDNS服务广播
- 设备抽象层
"""

import asyncio
import time
from typing import Dict, Any, Optional, List

from core.agent import RobotAgent, AgentState
from core.room_agent.mqtt import MqttClientManager
from core.room_agent.mdns import MdnsAdvertiser
from core.room_agent.devices import DeviceRegistry, DeviceController
from core.room_agent.models import (
    StateMessage,
    DescriptionMessage,
    HeartbeatMessage,
    SystemMetrics,
    DeviceCapability,
)
import config


class RoomAgent(RobotAgent):
    """Room Agent - 房间智能体

    职责：
    - MQTT客户端连接管理
    - mDNS服务广播
    - 设备控制和状态管理
    - 心跳和状态发布
    """

    def __init__(self, room_id: str, agent_config: Dict[str, Any]):
        """初始化Room Agent

        Args:
            room_id: 房间ID
            agent_config: Agent配置
                - agent_id: Agent ID
                - version: Agent版本
                - capabilities: 能力列表
                - mqtt: MQTT配置
                - mdns: mDNS配置
        """
        super().__init__()

        self.room_id = room_id
        self.agent_config = agent_config
        self.agent_id = agent_config.get("agent_id", f"room-agent-{room_id}")
        self.version = agent_config.get("version", "1.0.0")
        self.capabilities = agent_config.get("capabilities", [])

        # 初始化MQTT客户端管理器
        mqtt_config = agent_config.get("mqtt", {})
        self.mqtt_client = MqttClientManager(
            room_id=room_id,
            agent_id=self.agent_id,
            broker_config=mqtt_config.get("broker", {})
        )

        # 初始化mDNS广播器
        mdns_config = agent_config.get("mdns", {})
        self.mdns_advertiser = MdnsAdvertiser({
            "room_id": room_id,
            **mdns_config
        })

        # 初始化设备注册表和控制器
        self.device_registry = DeviceRegistry()
        self.device_controller = DeviceController(self.device_registry)

        # 设备列表（后续实现）
        self.devices: Dict[str, Any] = {}

        # 心跳任务
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._heartbeat_interval = agent_config.get("heartbeat", {}).get("interval", 30)

        # 运行状态
        self._room_agent_running = False

        print(f"[RoomAgent] Initialized (room: {room_id}, agent: {self.agent_id})")

    async def start(self):
        """启动Room Agent"""
        print("[RoomAgent] Starting Room Agent...")

        # 启动父类
        super().start()

        # 注册MQTT消息处理器
        self._register_mqtt_handlers()

        # 连接到MQTT Broker
        mqtt_connected = await self.mqtt_client.connect()
        if not mqtt_connected:
            print("[RoomAgent] WARNING: Failed to connect to MQTT broker")

        # 启动mDNS服务广播
        try:
            await self.mdns_advertiser.start()
        except Exception as e:
            print(f"[RoomAgent] WARNING: Failed to start mDNS advertiser: {e}")

        # 发布能力描述
        await self._publish_description()

        # 启动心跳任务
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        self._room_agent_running = True
        self.set_state(AgentState.RESPONDING)

        print("[RoomAgent] Room Agent started successfully")

    async def stop(self):
        """停止Room Agent"""
        print("[RoomAgent] Stopping Room Agent...")

        self._room_agent_running = False

        # 停止心跳任务
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        # 停止mDNS广播
        await self.mdns_advertiser.stop()

        # 断开MQTT连接
        await self.mqtt_client.disconnect()

        # 停止父类
        await super().stop()

        print("[RoomAgent] Room Agent stopped")

    def _register_mqtt_handlers(self):
        """注册MQTT消息处理器"""
        # Control消息处理器
        async def handle_control(control_msg):
            """处理设备控制消息"""
            print(f"[RoomAgent] Received control command:")
            print(f"  Target Device: {control_msg.target_device}")
            print(f"  Action: {control_msg.action}")
            print(f"  Parameters: {control_msg.parameters}")

            # 使用设备控制器执行动作
            result = await self.device_controller.control_device(
                device_id=control_msg.target_device,
                action=control_msg.action,
                parameters=control_msg.parameters
            )

            if result.get("success"):
                print(f"[RoomAgent] Device control successful: {result.get('result')}")
            else:
                print(f"[RoomAgent] Device control failed: {result.get('error')}")

        # Describe消息处理器
        async def handle_describe(describe_msg):
            """处理能力查询"""
            print(f"[RoomAgent] Received describe request from {describe_msg.source_agent}")
            # 重新发布能力描述
            await self._publish_description()

        self.mqtt_client.register_handler("control", handle_control)
        self.mqtt_client.register_handler("describe", handle_describe)

    async def _publish_description(self):
        """发布Agent能力描述"""
        # 获取所有设备的能力
        device_capabilities = await self.device_controller.list_device_capabilities()

        description = DescriptionMessage(
            message_id=str(time.time_ns()),
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            agent_id=self.agent_id,
            agent_type="room",
            version=self.version,
            devices=device_capabilities,
            capabilities=self.capabilities
        )

        await self.mqtt_client.publish_description(description)
        print("[RoomAgent] Published capabilities description")

    async def _publish_state(self):
        """发布Agent状态"""
        # 获取所有设备状态
        all_devices = await self.device_controller.list_all_devices()
        device_states = []
        for device in all_devices:
            try:
                device_state = await self.device_controller.get_device_state(device.device_id)
                if device_state:
                    device_states.append({
                        "device_id": device_state.device_id,
                        "state": device_state.state,
                        "attributes": device_state.attributes
                    })
            except Exception as e:
                print(f"[RoomAgent] Error getting state for device {device.device_id}: {e}")

        state = StateMessage(
            message_id=str(time.time_ns()),
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            agent_id=self.agent_id,
            devices=device_states,
            agent_status="operational" if self._room_agent_running else "offline"
        )

        await self.mqtt_client.publish_state(state)
        print(f"[RoomAgent] Published state with {len(device_states)} devices")

    async def _heartbeat_loop(self):
        """心跳循环"""
        while self._room_agent_running:
            try:
                # 创建心跳消息
                import psutil
                metrics = SystemMetrics(
                    cpu_usage=psutil.cpu_percent(),
                    memory_usage=psutil.virtual_memory().percent,
                    active_connections=0  # TODO: 获取实际连接数
                )

                heartbeat = HeartbeatMessage(
                    message_id=str(time.time_ns()),
                    timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    agent_id=self.agent_id,
                    status="operational",
                    uptime_seconds=int(time.time() - self._start_time if hasattr(self, '_start_time') else 0),
                    metrics=metrics
                )

                await self.mqtt_client.publish_heartbeat(heartbeat)

            except Exception as e:
                print(f"[RoomAgent] Error in heartbeat loop: {e}")

            await asyncio.sleep(self._heartbeat_interval)


    async def register_mcp_tool_as_device(
        self,
        device_id: str,
        device_type: str,
        tool_name: str,
        mcp_manager,
        device_config: dict = None
    ) -> bool:
        """注册MCP工具为设备

        Args:
            device_id: 设备ID
            device_type: 设备类型
            tool_name: MCP工具名称
            mcp_manager: MCP Manager实例
            device_config: 设备配置

        Returns:
            bool: 是否成功注册
        """
        if device_config is None:
            device_config = {}

        print(f"[RoomAgent] Registering MCP tool '{tool_name}' as device '{device_id}'")

        try:
            success = await self.device_controller.register_mcp_tool(
                device_id=device_id,
                device_type=device_type,
                device_config=device_config,
                mcp_manager=mcp_manager,
                tool_name=tool_name
            )

            if success:
                print(f"[RoomAgent] Successfully registered device '{device_id}'")
                # 重新发布能力描述
                await self._publish_description()
            else:
                print(f"[RoomAgent] Failed to register device '{device_id}'")

            return success

        except Exception as e:
            print(f"[RoomAgent] Error registering MCP device: {e}")
            return False
