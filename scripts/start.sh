#!/usr/bin/env bash
# ── Pi Display Manager (lite) — Start script ────────────────────────────────
# No X11 needed — fbi uses the framebuffer, cvlc uses --vout fb

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

source "$PROJECT_DIR/venv/bin/activate"

PI_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")
echo ""
echo "Starting Pi Display Manager (lite)…"
echo "Web UI: http://${PI_IP}:8000"
echo ""

exec uvicorn main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 1
