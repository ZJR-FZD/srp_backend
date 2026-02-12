# HomeSystemAgent A2A (Agent-to-Agent) Specification

## 1. System Overview

### 1.1 Vision Statement
Build a spatially scoped, decentralized multi-agent communication architecture for smart home environments, where BLE enables proximity-based space binding, mDNS supports in-space agent discovery, and MQTT provides structured semantic interaction among agents.

### 1.2 System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Smart Home Space                                │
│                                                                          │
│  ┌─────────────┐         ┌─────────────┐         ┌─────────────┐       │
│  │   Personal  │         │   Room      │         │   Robot     │       │
│  │   Agent     │◄────────┤   Agent     │◄────────┤   Agent     │       │
│  │  (Watch/    │  MQTT   │  (Edge      │  MQTT   │  (Mobile    │       │
│  │   Phone)    │         │   Device)   │         │   Device)   │       │
│  └──────┬──────┘         └──────┬──────┘         └─────────────┘       │
│         │                        │                                       │
│         │ BLE Beacon             │ MQTT Broker                           │
│         │                        │ (Local)                               │
│         ▼                        ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    Space Layer                                   │    │
│  │  BLE Beacon ───────► Spatial Binding ───────► mDNS Discovery     │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

## 2. Agent Types & Roles

### 2.1 Personal Agent (随身 Agent)

**Deployment**: Smart watch, smartphone, wearable devices

**Responsibilities**:
- User intent parsing and natural language understanding
- Spatial localization via BLE beacon scanning
- Triggering interactions with current space agents
- User interface and feedback presentation

**Key Capabilities**:
```yaml
capabilities:
  - beacon_scanning:
      rssi_threshold: -70
      hysteresis: 5
      scan_interval: 1s
  - intent_recognition:
      wake_word: true
      voice_command: true
  - mqtt_client:
      qos: 1
      keep_alive: 60s
      auto_reconnect: true
```

### 2.2 Room Agent (房间 Agent)

**Deployment**: Edge devices (Jetson, Raspberry Pi, smart home hub)

**Responsibilities**:
- Spatial semantic management
- Device abstraction and control
- MQTT Broker management (space-scoped)
- Agent discovery coordination

**Key Capabilities**:
```yaml
capabilities:
  - mqtt_broker:
      port: 1883
      ws_port: 9001
      max_connections: 100
      qos: [0, 1, 2]
  - device_management:
      supported_protocols: [HTTP, MQTT, CoAP, Zigbee]
      device_discovery: true
  - mdns_advertiser:
      service_type: _room-agent._tcp.local
      txt_records:
        - room_id
        - mqtt_port
        - agent_id
```

### 2.3 Robot Agent (机器人 Agent)

**Deployment**: Mobile robots, vacuum cleaners, delivery robots

**Responsibilities**:
- Task execution within room space
- State reporting via MQTT
- Navigation and obstacle avoidance (if applicable)

**Key Capabilities**:
```yaml
capabilities:
  - mqtt_client:
      subscriptions:
        - "room/{room_id}/robot/{robot_id}/control"
      publications:
        - "room/{room_id}/robot/{robot_id}/state"
        - "room/{room_id}/robot/{robot_id}/telemetry"
  - task_execution:
      task_types: [cleaning, delivery, patrol]
      status_reporting: true
```

## 3. Communication Protocol Stack

### 3.1 Layer 1: Spatial Awareness (空间感知层)

**Purpose**: Answer "Which room am I in?"

**Technology**: BLE Beacon

**Beacon Specification**:
```yaml
beacon_format:
  uuid: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"  # System-specific UUID
  major: 0-65535                                 # Room identifier
  minor: 0-65535                                 # Zone/Position in room
  measured_power: -59                            # Calibrated RSSI at 1m
```

**Spatial Binding Algorithm**:
```python
# Pseudo-code for spatial determination
def determine_current_space(beacons):
    """
    Input: List of detected beacons with RSSI values
    Output: Current space ID

    Algorithm:
    1. Filter beacons with RSSI > threshold (e.g., -70dBm)
    2. Select beacon with highest RSSI
    3. Apply hysteresis to prevent rapid switching:
       - Only switch if new beacon RSSI > current beacon RSSI + hysteresis
    """
    filtered = [b for b in beacons if b.rssi > RSSI_THRESHOLD]
    if not filtered:
        return UNKNOWN_SPACE

    candidate = max(filtered, key=lambda b: b.rssi)

    if current_space:
        if candidate.rssi > current_beacon.rssi + HYSTERESIS:
            return candidate.space_id
        else:
            return current_space
    else:
        return candidate.space_id
```

**Key Parameters**:
| Parameter | Value | Description |
|-----------|-------|-------------|
| RSSI Threshold | -70 dBm | Minimum signal to consider beacon valid |
| Hysteresis | 5 dB | Margin to prevent oscillation |
| Scan Interval | 1 second | Frequency of beacon scans |

### 3.2 Layer 2: In-Space Discovery (空间内发现层)

**Purpose**: Answer "Which agents are in this space?"

**Technology**: mDNS (Multicast DNS)

**Service Advertisement**:
```
Service Type: _room-agent._tcp.local
Instance Name: bedroom-room-agent-1._room-agent._tcp.local

TXT Records:
  - room_id=bedroom
  - mqtt_port=1883
  - mqtt_ws_port=9001
  - agent_id=room-agent-1
  - version=1.0.0
  - capabilities=light,curtain,climate
```

**Discovery Flow**:
```python
# Personal Agent discovery logic
async def discover_room_agent(room_id):
    """
    1. Query mDNS for _room-agent._tcp.local services
    2. Filter by room_id in TXT records
    3. Return MQTT broker connection details
    """
    services = await mdns.browse('_room-agent._tcp.local')

    for service in services:
        if service.txt.get('room_id') == room_id:
            return {
                'host': service.address,
                'mqtt_port': int(service.txt.get('mqtt_port', 1883)),
                'agent_id': service.txt.get('agent_id'),
                'capabilities': service.txt.get('capabilities', '').split(',')
            }

    raise RoomAgentNotFound(f"No Room Agent found for {room_id}")
```

### 3.3 Layer 3: Agent Communication (智能体通信层)

**Purpose**: Answer "How do agents exchange semantic information?"

**Technology**: MQTT (Message Queuing Telemetry Transport)

**Broker Topology**:
- **Decentralized**: Each room has its own MQTT broker
- **Space-scoped**: No cross-room communication by default
- **Local network**: Brokers run on LAN, not accessible from internet

**Topic Hierarchy**:
```
room/{room_id}/
├── agent/{agent_id}/
│   ├── control/          # Command topic
│   ├── state/            # State publication topic
│   ├── describe/         # Agent capability query
│   ├── description/      # Agent capability response
│   └── heartbeat/        # Liveness indicator
├── robot/{robot_id}/
│   ├── control/
│   ├── state/
│   └── telemetry/
└── system/
    ├── discovery/
    └── error/
```

**QoS Strategy**:
| Topic Type | QoS Level | Rationale |
|------------|-----------|-----------|
| control | 1 (At least once) | Commands must not be lost |
| state | 0 (At most once) | Latest state is sufficient |
| describe | 1 (At least once) | Must receive response |
| heartbeat | 0 (At most once) | Periodic updates, latest sufficient |
| telemetry | 0 (At most once) | High-frequency data |

## 4. Message Formats

### 4.1 Control Message

**Topic**: `room/{room_id}/agent/{agent_id}/control`

**Format**:
```json
{
  "message_id": "uuid-v4",
  "timestamp": "2024-01-15T10:30:00Z",
  "source_agent": "personal-agent-user1",
  "target_device": "light_1",
  "action": "on",
  "parameters": {
    "brightness": 80,
    "color_temp": 4000
  },
  "correlation_id": "optional-correlation-id"
}
```

### 4.2 State Message

**Topic**: `room/{room_id}/agent/{agent_id}/state`

**Format**:
```json
{
  "message_id": "uuid-v4",
  "timestamp": "2024-01-15T10:30:01Z",
  "agent_id": "room-agent-1",
  "devices": [
    {
      "device_id": "light_1",
      "state": "on",
      "attributes": {
        "brightness": 80,
        "color_temp": 4000
      }
    }
  ],
  "agent_status": "operational"
}
```

### 4.3 Describe Request

**Topic**: `room/{room_id}/agent/{agent_id}/describe`

**Format**:
```json
{
  "message_id": "uuid-v4",
  "timestamp": "2024-01-15T10:30:00Z",
  "source_agent": "personal-agent-user1",
  "query_type": "capabilities"
}
```

### 4.4 Description Response

**Topic**: `room/{room_id}/agent/{agent_id}/description`

**Format**:
```json
{
  "message_id": "uuid-v4",
  "timestamp": "2024-01-15T10:30:01Z",
  "agent_id": "room-agent-1",
  "agent_type": "room",
  "version": "1.0.0",
  "devices": [
    {
      "id": "light_1",
      "name": "Main Ceiling Light",
      "type": "light",
      "actions": ["on", "off", "set_brightness", "set_color_temp"],
      "state_attributes": ["brightness", "color_temp", "power_state"]
    },
    {
      "id": "curtain",
      "name": "Window Curtain",
      "type": "curtain",
      "actions": ["open", "close", "set_position"],
      "state_attributes": ["position", "state"]
    }
  ],
  "capabilities": ["device_control", "scene_activation"]
}
```

### 4.5 Heartbeat Message

**Topic**: `room/{room_id}/agent/{agent_id}/heartbeat`

**Format**:
```json
{
  "message_id": "uuid-v4",
  "timestamp": "2024-01-15T10:30:00Z",
  "agent_id": "room-agent-1",
  "status": "operational",
  "uptime_seconds": 3600,
  "metrics": {
    "cpu_usage": 25.5,
    "memory_usage": 45.2,
    "active_connections": 3
  }
}
```

## 5. Complete Communication Flow

### 5.1 Full Sequence Diagram

```
Personal Agent                    Room Agent                     Robot Agent
     │                                 │                               │
     │◄────── BLE Beacon (RSSI) ───────┤                               │
     │                                 │                               │
     │  [Determine: Space=Bedroom]     │                               │
     │                                 │                               │
     │──── mDNS Query ─────────────────►│                               │
     │                                 │                               │
     │◄──── mDNS Response ──────────────┤                               │
     │  (IP: 192.168.1.100, Port:1883) │                               │
     │                                 │                               │
     │──── MQTT CONNECT ───────────────►│                               │
     │                                 │                               │
     │◄──── CONNACK ────────────────────┤                               │
     │                                 │                               │
     │──── Publish: /describe ─────────►│                               │
     │                                 │                               │
     │◄──── Publish: /description ─────┤                               │
     │  (Available devices/capabilities)                               │
     │                                 │                               │
     │──── Publish: /control ─────────►│                               │
     │  (Action: "curtain.close")      │                               │
     │                                 │                               │
     │                                 │──── Publish: /control ──────►│
     │                                 │  (Task assignment)           │
     │                                 │                               │
     │◄──── Publish: /state ───────────┤◄─── Publish: /state ─────────┤
     │  (State updates)                │  (Task status)               │
     │                                 │                               │
```

### 5.2 Phase-by-Phase Breakdown

#### Phase 1: Spatial Binding (Connectionless)
```
Time: T0 to T1
Duration: Near-instantaneous

Events:
1. Beacon broadcasts (UUID, Major, Minor) continuously
2. Personal Agent scans beacons periodically
3. RSSI-based room determination with hysteresis

Output: current_space = "bedroom"
```

#### Phase 2: Agent Discovery
```
Time: T1 to T1 + ~100ms
Duration: < 1 second

Events:
1. Personal Agent sends mDNS query
2. Room Agent responds with connection details

Output: mqtt_broker = { host: "192.168.1.100", port: 1883 }
```

#### Phase 3: Connection Establishment
```
Time: T1 + 100ms to T1 + ~500ms
Duration: < 1 second

Events:
1. Personal Agent connects to MQTT broker
2. Subscribe to relevant topics
3. Publish describe request

Output: Connection established, capabilities known
```

#### Phase 4: Semantic Communication
```
Time: T1 + 500ms onwards
Duration: Ongoing

Events:
1. User triggers command
2. Personal Agent publishes control message
3. Room Agent processes and controls devices
4. State updates published

Output: Device state changes, user notified
```

## 6. Error Handling & Edge Cases

### 6.1 Beacon Unavailability
**Scenario**: No beacons detected or RSSI too weak

**Handling**:
```python
if no_beacons_detected:
    # Enter degraded mode
    status = "unknown_space"
    # Fallback to last known space (if recent)
    if last_known_space_timestamp < 5_minutes:
        current_space = last_known_space
        status = "estimated_space"
    else:
        current_space = None
        # Notify user: "Location unknown, please confirm room"
```

### 6.2 Room Agent Unreachable
**Scenario**: mDNS fails to find Room Agent

**Handling**:
```python
if room_agent_not_found:
    # Retry strategy
    retry_count = 0
    while retry_count < MAX_RETRIES:
        await asyncio.sleep(RETRY_DELAY)
        agent = await discover_room_agent(room_id)
        if agent:
            break
        retry_count += 1

    # Fallback options
    if not agent:
        # Option 1: Use cached connection details (if < 1 hour old)
        if cached_agent and cache_is_fresh:
            agent = cached_agent
            log.warning("Using cached Room Agent details")
        # Option 2: Direct IP configuration
        elif fallback_ip_configured:
            agent = fallback_config
            log.warning("Using fallback IP configuration")
        else:
            notify_user("Room Agent not found. Some features unavailable.")
```

### 6.3 MQTT Connection Lost
**Scenario**: Connection to MQTT broker drops

**Handling**:
```python
# Auto-reconnect with exponential backoff
reconnect_delay = 1  # Start with 1 second
max_delay = 60       # Cap at 60 seconds

while not connected:
    try:
        await mqtt_client.connect(broker_url)
        connected = True
        reconnect_delay = 1  # Reset on success
    except ConnectionError:
        await asyncio.sleep(reconnect_delay)
        reconnect_delay = min(reconnect_delay * 2, max_delay)
        log.warning(f"Reconnect failed, retrying in {reconnect_delay}s")
```

### 6.4 Device Control Failure
**Scenario**: Command sent but device doesn't respond

**Handling**:
```json
{
  "message_id": "uuid-v4",
  "timestamp": "2024-01-15T10:30:05Z",
  "status": "failed",
  "error_code": "DEVICE_TIMEOUT",
  "error_message": "Device light_1 did not respond within 5s",
  "retry_suggested": true
}
```

## 7. Security Considerations

### 7.1 Authentication

**MQTT Authentication**:
```yaml
authentication:
  mechanism: "username_password"  # or client_certificates
  username_prefix: "agent_"
  password_format: "token_based"  # JWT or shared secret
  token_expiry: 86400  # 24 hours
```

### 7.2 Authorization

**Topic ACL**:
```yaml
access_control:
  personal_agent:
    can_publish:
      - "room/{room_id}/agent/*/control"
      - "room/{room_id}/agent/*/describe"
    can_subscribe:
      - "room/{room_id}/agent/*/state"
      - "room/{room_id}/agent/*/description"

  robot_agent:
    can_publish:
      - "room/{room_id}/robot/+/state"
      - "room/{room_id}/robot/+/telemetry"
    can_subscribe:
      - "room/{room_id}/robot/{self_id}/control"
```

### 7.3 Encryption

**Transport Security**:
```yaml
encryption:
  mqtt:
    tls_enabled: true  # Production
    tls_version: "1.3"
    certificate_validation: true
```

**⚠️ TO BE DEFINED**: Certificate management strategy (self-signed vs PKI)

### 7.4 Local Network Isolation

**Network Design**:
- MQTT brokers bind to LAN interface only (e.g., `192.168.x.x`)
- No port forwarding to internet
- VPN required for remote access (if needed)

## 8. Performance Requirements

### 8.1 Latency Targets

| Operation | Target Latency | Maximum Acceptable |
|-----------|----------------|-------------------|
| Spatial detection | < 1s | 3s |
| mDNS discovery | < 100ms | 500ms |
| MQTT connect | < 200ms | 1s |
| Control command | < 50ms (end-to-end) | 200ms |
| State update | < 100ms | 500ms |

### 8.2 Reliability Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| MQTT delivery success rate | > 99.9% | QoS 1/2 messages |
| mDNS discovery success | > 99% | In stable LAN |
| Beacon detection accuracy | > 95% | Correct room identification |

### 8.3 Scalability Targets

| Metric | Target per Room | System-wide |
|--------|-----------------|-------------|
| Personal Agents | 10 | N/A (space-scoped) |
| Robot Agents | 5 | N/A |
| Devices per Room | 50 | N/A |
| MQTT Messages/sec | 100 | N/A |

## 9. State Management & Persistence

### 9.1 Room Agent State

**Persisted State**:
```yaml
room_agent_state:
  room_id: "bedroom"
  agent_id: "room-agent-1"
  registered_devices:
    - device_id: "light_1"
      last_seen: "2024-01-15T10:30:00Z"
      config: {...}
  active_agents:
    - agent_id: "personal-agent-user1"
      last_heartbeat: "2024-01-15T10:30:00Z"
  scenes:
    - name: "morning"
      devices_states: {...}
```

**⚠️ TO BE DEFINED**:
- State storage backend (SQLite? PostgreSQL?)
- State sync strategy (if multiple Room Agent instances)

### 9.2 Personal Agent State

**Persisted State**:
```yaml
personal_agent_state:
  user_id: "user1"
  current_space: "bedroom"
  space_history:
    - space: "bedroom"
      timestamp: "2024-01-15T10:30:00Z"
  known_room_agents:
    - room_id: "bedroom"
      agent_id: "room-agent-1"
      connection_params: {...}
      last_seen: "2024-01-15T10:29:00Z"
```

## 10. Configuration Management

### 10.1 Room Agent Configuration

**Config File**: `config/room_agent.yaml`
```yaml
agent:
  id: "room-agent-1"
  room_id: "bedroom"
  version: "1.0.0"

beacon:
  uuid: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
  major: 1  # Room identifier

mqtt:
  broker:
    port: 1883
    ws_port: 9001
    max_connections: 100
  qos_default: 1

mdns:
  service_name: "bedroom-room-agent"
  service_type: "_room-agent._tcp.local"

devices:
  - id: "light_1"
    type: "philips_hue"
    address: "192.168.1.201"
  - id: "curtain"
    type: "somfy"
    address: "192.168.1.202"

security:
  auth_enabled: true
  tls_enabled: false  # Development only
```

### 10.2 Personal Agent Configuration

**Config File**: `config/personal_agent.yaml`
```yaml
agent:
  id: "personal-agent-user1"
  user_id: "user1"
  version: "1.0.0"

beacon:
  scan_interval: 1
  rssi_threshold: -70
  hysteresis: 5

mqtt:
  qos: 1
  keep_alive: 60
  auto_reconnect: true
  reconnect_delay: 1

voice:
  wake_word: "小狐狸"
  language: "zh-CN"
```

## 11. Testing Strategy

### 11.1 Unit Testing

**Coverage Targets**:
- Spatial detection algorithm: 100%
- Message serialization/deserialization: 100%
- Topic routing logic: 90%+

### 11.2 Integration Testing

**Test Scenarios**:
1. Full flow: Beacon → mDNS → MQTT → Control
2. Multiple Personal Agents in same room
3. Room Agent failure and recovery
4. Network interruption handling

### 11.3 Hardware-in-the-Loop

**Required Tests**:
- Real BLE beacon detection accuracy
- mDNS discovery across different network configurations
- MQTT performance with target message rates

## 12. Deployment & Operations

### 12.1 Monitoring

**Metrics to Collect**:
```yaml
room_agent_metrics:
  - mqtt_messages_received_per_second
  - mqtt_messages_sent_per_second
  - active_connections
  - average_message_latency
  - device_control_success_rate
  - cpu_usage
  - memory_usage
```

**Health Checks**:
```yaml
health_check:
  mqtt_broker:
    endpoint: "/health/mqtt"
    expected_response: "healthy"
  device_connectivity:
    endpoint: "/health/devices"
    check_interval: 60s
```

### 12.2 Logging

**Log Levels**:
- `DEBUG`: Detailed beacon RSSI values
- `INFO`: Connection events, state changes
- `WARNING`: Retries, degraded mode activation
- `ERROR`: Connection failures, device control failures

**Log Format**: JSON structured logging
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "agent_id": "room-agent-1",
  "event": "mqtt_client_connected",
  "client_id": "personal-agent-user1",
  "remote_ip": "192.168.1.50"
}
```

## 13. Extensibility Points

### 13.1 Adding New Device Types

**Steps**:
1. Define device schema in `Room Agent` config
2. Implement device adapter (if needed)
3. Add device to `/description` response
4. Test control and state reporting

### 13.2 Cross-Room Communication

**⚠️ TO BE DEFINED**: Requirements for cross-room scenarios

**Potential Approaches**:
- Room-to-room MQTT bridge
- Central orchestration service
- Federation protocol

### 13.3 Cloud Integration (Optional)

**Use Cases**:
- Remote access via VPN
- Cloud-based voice processing
- Analytics and logging

**⚠️ TO BE DEFINED**: Cloud integration architecture

## 14. Open Questions & TODO

### 14.1 High Priority

- [ ] **Security**: Define authentication token management (JWT issuance, refresh)
- [ ] **Security**: Certificate strategy for TLS (self-signed setup, rotation)
- [ ] **State**: Choose Room Agent state storage backend
- [ ] **Discovery**: Handle multiple Room Agents in same room (HA scenario)
- [ ] **Robot**: Define Robot Agent task schema and capabilities
- [ ] **Testing**: Set up integration test environment

### 14.2 Medium Priority

- [ ] **Performance**: Benchmark maximum message throughput per broker
- [ ] **Reliability**: Define HA strategy for Room Agent (active-passive? active-active?)
- [ ] **UX**: Define user feedback for spatial detection errors
- [ ] **Privacy**: Define data retention policy for state/history
- [ ] **Config**: Dynamic config reload mechanism

### 14.3 Low Priority

- [ ] **Cloud**: Design cloud integration (if needed)
- [ ] **Analytics**: Define telemetry schema for system monitoring
- [ ] **Federation**: Design cross-room communication protocol
- [ ] **Edge Cases**: Multi-user conflict resolution (simultaneous control requests)

## 15. Appendix

### 15.1 Technology Rationale

**Why BLE Beacon?**
- Low power, suitable for battery-operated beacons
- Widely supported on mobile devices
- No pairing required
- Good spatial resolution with RSSI

**Why mDNS?**
- Zero-configuration service discovery
- Built into all major OSes
- Works well on local networks
- No external dependencies

**Why MQTT?**
- Lightweight, suitable for IoT
- Built-in QoS levels
- Pub/sub decouples agents
- Efficient for small, frequent messages
- Widely adopted in IoT industry

### 15.2 Alternative Technologies Considered

| Component | Chosen | Alternatives | Rationale |
|-----------|--------|--------------|-----------|
| Spatial | BLE Beacon | WiFi triangulation, UWB | BLE is power-efficient and sufficient for room-level accuracy |
| Discovery | mDNS | Static config, central registry | mDNS is zero-config and works well on LAN |
| Communication | MQTT | HTTP, CoAP, gRPC | MQTT's pub/sub model fits async agent communication |
| Data | JSON | MessagePack, CBOR | JSON is human-readable and widely supported |

### 15.3 References

- MQTT Specification: https://mqtt.org/mqtt-specification/
- mDNS Specification: https://tools.ietf.org/html/rfc6762
- BLE Beacon Format: https://specifications.bluetooth.com/thesis-packages/
