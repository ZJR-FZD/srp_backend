# config/room_mapping.py
"""
房间ID映射表

用于ESP32 Beacon Major值与Room Agent room_id之间的映射
"""

# Room Agent room_id -> Beacon Major值
ROOM_ID_MAPPING = {
    "livingroom": 1,
    "bedroom": 2,
    "kitchen": 3,
    "bathroom": 4,
    "study": 5,
    "balcony": 6,
    "garage": 7,
}

# 反向映射：Beacon Major -> Room Agent room_id
MAJOR_TO_ROOM_ID = {v: k for k, v in ROOM_ID_MAPPING.items()}

# 房间名称（中文）
ROOM_NAMES = {
    "livingroom": "客厅",
    "bedroom": "卧室",
    "kitchen": "厨房",
    "bathroom": "浴室",
    "study": "书房",
    "balcony": "阳台",
    "garage": "车库",
}

# ESP32设备标识（可选）
ESP32_DEVICE_IDS = {
    1: "esp32-beacon-livingroom",
    2: "esp32-beacon-bedroom",
    3: "esp32-beacon-kitchen",
    4: "esp32-beacon-bathroom",
    5: "esp32-beacon-study",
    6: "esp32-beacon-balcony",
    7: "esp32-beacon-garage",
}

# ESP32编译时房间ID定义（C代码）
ESP32_ROOM_DEFINES = """
// 房间ID定义（用于ESP32编译选项或NVS配置）
#define ROOM_ID_LIVINGROOM  1
#define ROOM_ID_BEDROOM  2
#define ROOM_ID_KITCHEN  3
#define ROOM_ID_BATHROOM  4
#define ROOM_ID_STUDY  5
#define ROOM_ID_BALCONY  6
#define ROOM_ID_GARAGE  7

// 编译时选择（示例）
// #define ROOM_ID ROOM_ID_LIVINGROOM
"""


def get_room_name(room_id: str) -> str:
    """获取房间中文名称"""
    return ROOM_NAMES.get(room_id, room_id)


def get_major_for_room(room_id: str) -> int:
    """获取房间的Major值"""
    return ROOM_ID_MAPPING.get(room_id)


def get_room_for_major(major: int) -> str:
    """从Major值获取房间ID"""
    return MAJOR_TO_ROOM_ID.get(major)


def validate_room_id(room_id: str) -> bool:
    """验证房间ID是否有效"""
    return room_id in ROOM_ID_MAPPING


def validate_major(major: int) -> bool:
    """验证Major值是否有效"""
    return 0 <= major <= 65535 and major in MAJOR_TO_ROOM_ID
