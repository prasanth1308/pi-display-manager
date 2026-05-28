#!/bin/bash
set -euo pipefail

BNEP_IF="bnep0"
PAN_IP="192.168.66.1/24"
PID_FILE="/run/pi-bnep-dnsmasq.pid"
CFG_FILE="/run/pi-bnep-dnsmasq.conf"
HOST_NAME="$(hostname)"

cleanup() {
  if [ -f "$PID_FILE" ]; then
    kill "$(cat "$PID_FILE")" >/dev/null 2>&1 || true
    rm -f "$PID_FILE"
  fi
}

trap cleanup EXIT INT TERM

while true; do
  if ip link show "$BNEP_IF" >/dev/null 2>&1; then
    ip link set "$BNEP_IF" up >/dev/null 2>&1 || true

    if ! ip addr show "$BNEP_IF" | grep -q "192.168.66.1/24"; then
      ip addr add "$PAN_IP" dev "$BNEP_IF" >/dev/null 2>&1 || true
    fi

    if [ ! -f "$PID_FILE" ] || ! kill -0 "$(cat "$PID_FILE")" >/dev/null 2>&1; then
      cat > "$CFG_FILE" <<EOF
interface=$BNEP_IF
bind-interfaces
dhcp-range=192.168.66.10,192.168.66.60,255.255.255.0,12h
dhcp-option=3,192.168.66.1
    dhcp-option=6,192.168.66.1
    address=/$HOST_NAME.local/192.168.66.1
    server=8.8.8.8
log-queries
log-dhcp
EOF
      dnsmasq --conf-file="$CFG_FILE" --pid-file="$PID_FILE"
    fi
  fi

  sleep 2
done
