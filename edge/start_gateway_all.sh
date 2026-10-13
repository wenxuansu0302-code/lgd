#!/bin/bash

# One script owns the complete gateway lifecycle:
# configure ports -> dial 5G -> wait for connected log -> ping -> start GW1.
set -u

EDGE_DIR="/root/lgd"
EDGE_SCRIPT="$EDGE_DIR/run_edge_GW1_v2.sh"
QUECTEL_CM="/root/Net_Tools/quectel-CM"
PING_TARGET="${PING_TARGET:-223.5.5.5}"
CLOUD_HOST="${CLOUD_HOST:-47.99.47.169}"
CLOUD_PORT="${CLOUD_PORT:-11500}"

QUECTEL_LOG="/run/quectel-CM.log"
EDGE_LOG="/var/log/gateway-app.log"
EDGE_LOG_LIMIT=20971520

QUECTEL_PID=""
EDGE_PID=""
STOPPING=0

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [gateway-startup] $*"
}

running() {
    [ -n "$1" ] && kill -0 "$1" 2>/dev/null
}

stop_process() {
    local pid="$1"
    local name="$2"
    local count=0

    running "$pid" || return 0
    log "Stopping $name PID=$pid"
    kill "$pid" 2>/dev/null || true

    while running "$pid" && [ "$count" -lt 10 ]; do
        sleep 1
        count=$((count + 1))
    done

    if running "$pid"; then
        log "Force killing $name PID=$pid"
        kill -9 "$pid" 2>/dev/null || true
    fi
    wait "$pid" 2>/dev/null || true
}

cleanup() {
    [ "$STOPPING" -eq 1 ] && return
    STOPPING=1
    stop_process "$EDGE_PID" "GW1"
    stop_process "$QUECTEL_PID" "quectel-CM"
    log "All gateway processes stopped"
}

trap 'cleanup; exit 0' INT TERM HUP QUIT
trap cleanup EXIT

configure_ports() {
    log "Configuring network ports"

    ip link set fm1-mac2 up
    ip addr flush dev fm1-mac2
    ip addr add 192.168.0.233/24 dev fm1-mac2

    ip link set fm1-mac4 up
    ip addr flush dev fm1-mac4
    ip addr add 192.168.1.106/24 dev fm1-mac4

    ip link set fm1-mac6 up
    ip addr flush dev fm1-mac6
    ip addr add 192.168.2.1/24 dev fm1-mac6

    log "Network ports configured"
}

kill_old_quectel() {
    local pids
    pids="$(pgrep -x quectel-CM 2>/dev/null || true)"
    [ -z "$pids" ] && return 0

    log "Stopping old quectel-CM process(es): $pids"
    for pid in $pids; do
        kill "$pid" 2>/dev/null || true
    done
    sleep 2
    for pid in $pids; do
        kill -9 "$pid" 2>/dev/null || true
    done
}

connected_log_seen() {
    grep -Eq \
        'requestGetIPAddress|bound to .* -- renewal|QNETDEVSTATUS: [0-9]+\.' \
        "$QUECTEL_LOG" 2>/dev/null
}

server_tcp_reachable() {
    python3 -c 'import socket,sys; s=socket.create_connection((sys.argv[1], int(sys.argv[2])), 3.0); s.close()' \
        "$CLOUD_HOST" "$CLOUD_PORT" >/dev/null 2>&1
}

usb0_link_ready() {
    ip -4 addr show dev usb0 2>/dev/null | grep -q 'inet ' \
        && ip route show default dev usb0 | grep -q '^default '
}

dial_5g_until_online() {
    local attempt=0
    local deadline
    local usb_ip

    while [ "$STOPPING" -eq 0 ]; do
        attempt=$((attempt + 1))
        kill_old_quectel
        : > "$QUECTEL_LOG"

        # Required command: run quectel-CM persistently in the background.
        "$QUECTEL_CM" >> "$QUECTEL_LOG" 2>&1 &
        QUECTEL_PID=$!
        log "5G attempt=$attempt, quectel-CM started in background PID=$QUECTEL_PID"

        deadline=$(( $(date +%s) + 90 ))
        while running "$QUECTEL_PID" && [ "$STOPPING" -eq 0 ]; do
            if connected_log_seen; then
                log "Connected log detected, checking usb0 address and route"
                if usb0_link_ready; then
                    usb_ip="$(
                        ip -4 -o addr show dev usb0 |
                            awk '{print $4}' |
                            head -1
                    )"
                    if server_tcp_reachable; then
                        log "5G ready: usb0=$usb_ip, cloud $CLOUD_HOST:$CLOUD_PORT reachable"
                    else
                        log "WARN: 5G ready: usb0=$usb_ip; cloud probe unavailable, gateway will keep retrying"
                    fi
                    tail -20 "$QUECTEL_LOG"
                    return 0
                fi
            fi

            if [ "$(date +%s)" -ge "$deadline" ]; then
                log "5G attempt=$attempt timed out; restarting quectel-CM"
                break
            fi
            sleep 2
        done

        if ! running "$QUECTEL_PID"; then
            log "quectel-CM exited before 5G became reachable"
        fi
        stop_process "$QUECTEL_PID" "quectel-CM"
        QUECTEL_PID=""

        [ "$STOPPING" -eq 1 ] && return 1
        log "5G is not reachable; retrying in 5 seconds"
        sleep 5
    done
    return 1
}

start_gateway_program() {
    if [ ! -x "$EDGE_SCRIPT" ]; then
        log "ERROR: $EDGE_SCRIPT is missing or not executable"
        return 1
    fi

    : > "$EDGE_LOG"
    cd "$EDGE_DIR" || return 1
    "$EDGE_SCRIPT" >> "$EDGE_LOG" 2>&1 &
    EDGE_PID=$!
    log "GW1 started in background PID=$EDGE_PID"

    sleep 3
    if ! running "$EDGE_PID"; then
        log "ERROR: GW1 exited during startup"
        tail -50 "$EDGE_LOG"
        return 1
    fi
}

limit_gateway_log() {
    local size=0
    [ -f "$EDGE_LOG" ] || return 0
    size="$(wc -c < "$EDGE_LOG" 2>/dev/null || echo 0)"
    if [ "$size" -gt "$EDGE_LOG_LIMIT" ]; then
        log "Gateway log reached $size bytes; truncating it"
        : > "$EDGE_LOG"
    fi
}

monitor_all() {
    local link_failures=0

    while [ "$STOPPING" -eq 0 ]; do
        sleep 15
        limit_gateway_log

        if ! running "$EDGE_PID"; then
            log "ERROR: GW1 PID=$EDGE_PID exited"
            return 1
        fi

        if ! running "$QUECTEL_PID"; then
            log "quectel-CM PID=$QUECTEL_PID exited; redialing"
            QUECTEL_PID=""
            dial_5g_until_online || return 1
            link_failures=0
            continue
        fi

        # A cloud/server timeout must never trigger a modem redial.  Redial only
        # when the local 5G interface actually loses its address or default route.
        if usb0_link_ready; then
            [ "$link_failures" -gt 0 ] && log "5G usb0 address and route recovered"
            link_failures=0
        else
            link_failures=$((link_failures + 1))
            log "5G usb0 address/route check failed $link_failures/3"
            if [ "$link_failures" -ge 3 ]; then
                stop_process "$QUECTEL_PID" "quectel-CM"
                QUECTEL_PID=""
                dial_5g_until_online || return 1
                link_failures=0
            fi
        fi
    done
}

main() {
    [ -x "$QUECTEL_CM" ] || {
        log "ERROR: $QUECTEL_CM is missing or not executable"
        return 1
    }

    configure_ports || return 1
    dial_5g_until_online || return 1
    start_gateway_program || return 1
    monitor_all
}

main
