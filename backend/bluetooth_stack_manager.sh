#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

AGENT_SCRIPT="$SCRIPT_DIR/bluetooth_auto_accept_agent.py"
PAN_MANAGER_SCRIPT="$SCRIPT_DIR/bluetooth_pan_manager.sh"
VENV_PY="$BASE_DIR/venv/bin/python3"

AGENT_PID=""
NAP_PID=""
PAN_IP_PID=""

cleanup() {
  for pid in "$PAN_IP_PID" "$NAP_PID" "$AGENT_PID"; do
    if [ -n "$pid" ] && kill -0 "$pid" >/dev/null 2>&1; then
      kill "$pid" >/dev/null 2>&1 || true
    fi
  done
  wait || true
}

trap cleanup EXIT INT TERM

# Prepare Bluetooth controller state before child processes start.
modprobe bnep >/dev/null 2>&1 || true
hciconfig hci0 up >/dev/null 2>&1 || true
bluetoothctl --timeout 5 power on >/dev/null 2>&1 || true
bluetoothctl --timeout 5 pairable on >/dev/null 2>&1 || true
bluetoothctl --timeout 5 discoverable on >/dev/null 2>&1 || true
bluetoothctl --timeout 5 pairable-timeout 0 >/dev/null 2>&1 || true
bluetoothctl --timeout 5 discoverable-timeout 0 >/dev/null 2>&1 || true

if [ -x "$VENV_PY" ] && [ -f "$AGENT_SCRIPT" ]; then
  "$VENV_PY" "$AGENT_SCRIPT" >> "$BASE_DIR/bt_agent.log" 2>&1 &
  AGENT_PID=$!
else
  echo "Bluetooth agent prerequisites missing" >&2
  exit 1
fi

BT_NET="$(command -v bt-network || true)"
if [ -n "$BT_NET" ]; then
  "$BT_NET" -s nap >> "$BASE_DIR/bt_nap.log" 2>&1 &
  NAP_PID=$!
else
  echo "bt-network command not found (install bluez-tools)" >&2
  exit 1
fi

if [ -x "$PAN_MANAGER_SCRIPT" ]; then
  "$PAN_MANAGER_SCRIPT" >> "$BASE_DIR/bt_pan_ip.log" 2>&1 &
  PAN_IP_PID=$!
else
  echo "PAN IP manager script missing or not executable" >&2
  exit 1
fi

# Exit if any child exits unexpectedly; systemd will restart this service.
wait -n "$AGENT_PID" "$NAP_PID" "$PAN_IP_PID"
exit 1
