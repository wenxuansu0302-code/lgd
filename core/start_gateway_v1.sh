#!/bin/sh
set -u

LOG_FILE=/root/gateway_v1_start.log
GATEWAY_LOG=/root/lgd/gateway_v1.log

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG_FILE"
}

run_cmd() {
    log "+ $*"
    "$@" >> "$LOG_FILE" 2>&1
    rc=$?
    if [ "$rc" -ne 0 ]; then
        log "WARN rc=$rc cmd=$*"
    fi
    return 0
}

log "start gateway_v1 bootstrap"

run_cmd ip link set fm1-mac6 up
run_cmd ip addr flush dev fm1-mac6
run_cmd ip addr add 192.168.2.1/24 dev fm1-mac6

run_cmd ip link set fm1-mac2 up
run_cmd ip addr flush dev fm1-mac2
run_cmd ip addr add 192.168.0.233/24 dev fm1-mac2

run_cmd systemctl start quectel-cm.service

sleep 10

cd /root
log "+ exec python3 -u lgd/gateway_v1.py --server-host 47.99.47.169"
exec python3 -u lgd/gateway_v1.py --server-host 47.99.47.169 >> "$GATEWAY_LOG" 2>&1