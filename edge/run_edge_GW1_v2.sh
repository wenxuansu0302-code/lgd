#!/bin/sh

# ============================================================================
# GW1 统一边缘网关启动脚本
#
# 启动程序：/root/lgd/gateway_merged.py
#
# 端口职责：
#   7777  本地视频/图片 VID0、SNAP 接收
#   8888  本地 JSON 统一接收
#   9100  宝通设备连接、链路探测及火情报文下发
#   11500 云服务器 JSON 与媒体数据转发目标
#   11502 云端白名单 HTTP 服务
#
# 默认配置：
#   云服务器：47.99.47.169
#   网关标识：gateway_1
#   宝通被叫 ID：025202
#   详细日志：开启（不传 --compact-log）
#   白名单同步：开启
#   白名单过滤：默认关闭，可用 ENABLE_WHITELIST_FILTER=1 开启
# ============================================================================

BASE_DIR="/root/lgd"
PYTHON_SCRIPT="$BASE_DIR/gateway_merged.py"

CLOUD_HOST="${CLOUD_HOST:-47.99.47.169}"
CLOUD_PORT="${CLOUD_PORT:-11500}"
GATEWAY_ID="${GATEWAY_ID:-gateway_1}"
CALLEE_ID="${CALLEE_ID:-025202}"

MEDIA_LISTEN_HOST="${MEDIA_LISTEN_HOST:-0.0.0.0}"
MEDIA_LISTEN_PORT="${MEDIA_LISTEN_PORT:-7777}"
JSON_LISTEN_HOST="${JSON_LISTEN_HOST:-0.0.0.0}"
JSON_LISTEN_PORT="${JSON_LISTEN_PORT:-8888}"
BAOTONG_HOST="${BAOTONG_HOST:-192.168.2.1}"
BAOTONG_PORT="${BAOTONG_PORT:-9100}"

JSON_MAX_BUFFER="${JSON_MAX_BUFFER:-20971520}"
JSON_QUEUE="${JSON_QUEUE:-1000}"
MEDIA_QUEUE="${MEDIA_QUEUE:-120}"
LOG_EVERY="${LOG_EVERY:-30}"
TIME_SET_INTERVAL="${TIME_SET_INTERVAL:-2.0}"

WHITELIST_URL="${WHITELIST_URL:-http://${CLOUD_HOST}:11502/}"
WHITELIST_INTERVAL="${WHITELIST_INTERVAL:-30.0}"
WHITELIST_FILE="${WHITELIST_FILE:-$BASE_DIR/whitelist.json}"
ENABLE_WHITELIST_FILTER="${ENABLE_WHITELIST_FILTER:-1}"

GATEWAY_PID=""
CLEANED_UP=0

cleanup() {
    if [ "$CLEANED_UP" -eq 1 ]; then
        return
    fi
    CLEANED_UP=1

    echo ""
    echo "Stopping unified Edge Gateway GW1..."

    if [ -n "$GATEWAY_PID" ] && kill -0 "$GATEWAY_PID" 2>/dev/null; then
        echo "Stopping PID: $GATEWAY_PID"
        kill "$GATEWAY_PID" 2>/dev/null || true

        count=0
        while kill -0 "$GATEWAY_PID" 2>/dev/null && [ "$count" -lt 5 ]; do
            sleep 1
            count=$((count + 1))
        done

        if kill -0 "$GATEWAY_PID" 2>/dev/null; then
            echo "Force killing PID: $GATEWAY_PID"
            kill -9 "$GATEWAY_PID" 2>/dev/null || true
        fi
    fi

    echo "Unified Edge Gateway GW1 stopped."
}

trap 'cleanup; exit 0' INT TERM QUIT HUP
trap 'cleanup' EXIT

cd "$BASE_DIR" || {
    echo "Error: cannot enter $BASE_DIR"
    exit 1
}

if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "Error: $PYTHON_SCRIPT not found"
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: python3 not found"
    exit 1
fi

if ! python3 -m py_compile "$PYTHON_SCRIPT"; then
    echo "Error: Python syntax check failed: $PYTHON_SCRIPT"
    exit 1
fi

set -- \
    python3 "$PYTHON_SCRIPT" \
        --satellite-port auto \
    --media-listen-host "$MEDIA_LISTEN_HOST" \
    --media-listen-port "$MEDIA_LISTEN_PORT" \
    --json-listen-host "$JSON_LISTEN_HOST" \
    --json-listen-port "$JSON_LISTEN_PORT" \
    --cloud-host "$CLOUD_HOST" \
    --cloud-port "$CLOUD_PORT" \
    --baotong-host "$BAOTONG_HOST" \
    --baotong-port "$BAOTONG_PORT" \
    --callee-id "$CALLEE_ID" \
    --gateway "$GATEWAY_ID" \
    --gateway-handshake \
    --json-max-buffer "$JSON_MAX_BUFFER" \
    --json-queue "$JSON_QUEUE" \
    --media-queue "$MEDIA_QUEUE" \
    --log-every "$LOG_EVERY" \
    --time-set-interval "$TIME_SET_INTERVAL" \
    --whitelist-url "$WHITELIST_URL" \
    --whitelist-interval "$WHITELIST_INTERVAL" \
    --whitelist-file "$WHITELIST_FILE"

case "$ENABLE_WHITELIST_FILTER" in
    1|true|TRUE|yes|YES|on|ON)
        set -- "$@" --whitelist-filter
        WHITELIST_FILTER_STATUS="enabled"
        ;;
    *)
        WHITELIST_FILTER_STATUS="disabled"
        ;;
esac

echo "============================================================"
echo "Starting unified Edge Gateway GW1..."
echo "Python file       : $PYTHON_SCRIPT"
echo "Gateway ID        : $GATEWAY_ID"
echo "BaoTong callee ID : $CALLEE_ID"
echo "Media input       : $MEDIA_LISTEN_HOST:$MEDIA_LISTEN_PORT"
echo "JSON input        : $JSON_LISTEN_HOST:$JSON_LISTEN_PORT"
echo "BaoTong service   : $BAOTONG_HOST:$BAOTONG_PORT"
echo "Cloud target      : $CLOUD_HOST:$CLOUD_PORT"
echo "Whitelist URL     : $WHITELIST_URL"
echo "Whitelist filter  : $WHITELIST_FILTER_STATUS"
echo "Time-set interval : ${TIME_SET_INTERVAL}s"
echo "Detailed logging  : enabled"
echo "============================================================"
echo "Press Ctrl+C to stop the service."
echo ""

"$@" &
GATEWAY_PID=$!

echo "Gateway PID: $GATEWAY_PID"

wait "$GATEWAY_PID"
EXIT_CODE=$?
GATEWAY_PID=""

if [ "$EXIT_CODE" -ne 0 ]; then
    echo "Warning: gateway_merged.py exited unexpectedly, code=$EXIT_CODE"
else
    echo "gateway_merged.py exited normally."
fi

exit "$EXIT_CODE"

