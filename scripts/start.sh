#!/usr/bin/env bash
# ── Pi Display Manager — Start script ───────────────────────────────────────
# Starts X11 (if not running) then launches the FastAPI web server.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

export DISPLAY=:0

# ── Start X11 + openbox if not already running ───────────────────────────────
if ! xdpyinfo -display :0 &>/dev/null 2>&1; then
  echo "Starting X11 display…"
  startx /usr/bin/openbox-session -- :0 vt7 &
  # Wait for X to be ready
  for i in {1..20}; do
    xdpyinfo -display :0 &>/dev/null 2>&1 && break
    sleep 0.5
  done
  echo "X11 ready."
fi

# ── Activate virtualenv ──────────────────────────────────────────────────────
source "$PROJECT_DIR/venv/bin/activate"

# ── Launch FastAPI server ─────────────────────────────────────────────────────
PI_IP=$(hostname -I | awk '{print $1}')
echo ""
echo "Starting Pi Display Manager…"
echo "Web UI: http://${PI_IP}:8000"
echo ""

exec uvicorn main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 1
