"""Central runtime configuration for the edge gateway.

Keep fixed deployment values and protocol timers here so gateway_merged.py can
be updated without searching through the business logic.  Command-line options
may still override the matching DEFAULT_* values at startup.
"""

# Local ingress services.
DEFAULT_MEDIA_LISTEN_HOST = "0.0.0.0"
DEFAULT_MEDIA_LISTEN_PORT = 7777
DEFAULT_JSON_LISTEN_HOST = "0.0.0.0"
DEFAULT_JSON_LISTEN_PORT = 8888

# Cloud services.
DEFAULT_CLOUD_HOST = "47.99.47.169"
DEFAULT_CLOUD_PORT = 11500
DEFAULT_SLICE_METRICS_PORT = 11510
DEFAULT_SLICE_METRICS_INTERVAL = 1.0
DEFAULT_EDGE_HEARTBEAT_PORT = 11511
DEFAULT_EDGE_HEARTBEAT_INTERVAL = 1.0
DEFAULT_LINK_STATUS_PORT = 11417
DEFAULT_LINK_STATUS_TIMEOUT = 15.0

# BaoTong shortwave industrial PC.
DEFAULT_BAOTONG_HOST = "192.168.2.1"
DEFAULT_BAOTONG_PORT = 9100
DEFAULT_CALLEE_ID = "025202"
BAOTONG_BUFFER_SIZE = 4096
BAOTONG_MAX_PAYLOAD_SIZE = 4096
BAOTONG_SMS_MAX_CONTENT_BYTES = 80
BAOTONG_SNR_THRESHOLD = -23.0

# Shortwave business timers.  Edge link probing uses 400s (shorter than the
# core's 600s probe window) so a lost probe reply returns the edge to idle
# before the core gives up, avoiding simultaneous probing that jams the
# channel; the edge then stays passive until the next core call.  The stale
# radio/reset watchdog uses twenty minutes.
# 2026-09-21 电台拉远后整体翻倍（核心 config.py 同步改）：
# 200->400 / 300->600 / 600->1200，"边缘探测 < 核心探测"的不变量保持。
SHORTWAVE_LINK_TEST_TIMEOUT_SECONDS = 400.0
SHORTWAVE_RESPONSE_TIMEOUT_SECONDS = 600.0
SHORTWAVE_RESET_TIMEOUT_SECONDS = 1200.0

# The industrial PC emits an application heartbeat every 10 seconds.  This is
# an online/offline detector rather than a radio business timeout, so retain the
# previously agreed two-missed-heartbeat (20 second) rule.
BAOTONG_HEARTBEAT_TIMEOUT = 20.0
BAOTONG_HEARTBEAT_POLL_INTERVAL = 1.0

SHORTWAVE_BUSINESS_BY_GATEWAY = {
    "gateway1": "fire",
    "gateway2": "windspeed",
    "gateway4": "fire",
}

# Gateway identity.  Registration can override these at runtime.
DEFAULT_GATEWAY_ID = "gateway_1"
DEFAULT_GATEWAY_HANDSHAKE = False

# Queue and socket limits.
DEFAULT_JSON_MAX_BUFFER_SIZE = 20 * 1024 * 1024
DEFAULT_JSON_MAX_QUEUE_SIZE = 1000
DEFAULT_MEDIA_MAX_QUEUE_PACKETS = 120
BUFFER_SIZE = 65536
MAX_PACKET_SIZE = 20 * 1024 * 1024
RECONNECT_INTERVAL = 3.0
REPORT_INTERVAL = 5.0
TIME_SET_INTERVAL = 2.0

# Whitelist synchronization.
DEFAULT_WHITELIST_CLOUD_PORT = 11502
DEFAULT_WHITELIST_INTERVAL = 30.0
DEFAULT_WHITELIST_FILE = "whitelist.json"
DEFAULT_WHITELIST_HTTP_TIMEOUT = 5

# 400-GM12 USB serial satellite uplink.
# 默认 auto：启动脚本不传 --satellite-port 时（gw2 即如此）走多口唯一
# CP210x 命中加固，避免误打 5G 模组的 ttyUSB0。
DEFAULT_SATELLITE_PORT = "auto"
DEFAULT_SATELLITE_BAUD = 115200
DEFAULT_SATELLITE_INTERVAL = 60.0
DEFAULT_SATELLITE_COMMAND_TIMEOUT = 4.0
DEFAULT_SATELLITE_RECONNECT_INTERVAL = 3.0
DEFAULT_SATELLITE_DATA_TYPE = 0
SATELLITE_MAX_PAYLOAD_BYTES = 120
# 模组积压帧(AT+CMMQ?)的巡检间隔：独立线程每该秒数查询一次 pending
# 帧数并打进日志，用于观察模组是否成功把帧发上星（数值持续上涨=积压）。
# <=0 时关闭巡检。
DEFAULT_SATELLITE_PENDING_LOG_INTERVAL = 30.0
# 火情严格跳变模式（2026-09-21，对齐规范 4.3 模拟脚本行为）：True 时
# 火情(s=F)只在值变化（跳变）时上星，值未变化的周期不再重发当前值；
# 跳变帧发送失败会在下个周期自动重试（_last_sent_fire 只在成功后更新）。
# 风速业务不受影响，仍按周期发。False 恢复"周期+跳变"双通道。
SATELLITE_FIRE_JUMP_ONLY = True

# BaoTong framing.
FRAME_HEAD = b"\xAA\x55"
FRAME_TAIL = b"\x55\xAA"

# Logging and JSON stream resynchronization.
DETAIL_LOG_ENABLED = True
LOG_PREVIEW_CHARS = 500
RESYNC_MARKERS = (
    '{"packet_type"',
    '{"type"',
    '{"timestamp"',
    '{"gateway"',
    '{"gateway_id"',
    '{"data_source"',
    '{"fire"',
)

# Nebula is installed as an independent service; business goes to the core.
TUNNEL_ENABLED = True
TUNNEL_CORE_HOST = "10.77.0.10"
TUNNEL_CORE_PORT = 11500
TUNNEL_CONTROL_HOST = "10.77.0.1"
TUNNEL_OUTBOX_PATH = "/root/lgd/tunnel_outbox.db"
DEFAULT_CLOUD_HOST = TUNNEL_CONTROL_HOST if TUNNEL_ENABLED else DEFAULT_CLOUD_HOST
