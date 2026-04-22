#!/usr/bin/env bash
# ── Pi Display Manager (lite) — Raspberry Pi setup script ───────────────────
# Raspberry Pi OS Lite (Bullseye / Bookworm) — Pi 3 Model A+
# Run once: chmod +x scripts/install.sh && ./scripts/install.sh

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
echo "Installing Pi Display Manager (lite) in: $PROJECT_DIR"

# ── 1. System packages ───────────────────────────────────────────────────────
echo ""
echo "==> Updating package lists…"
sudo apt-get update -y

echo ""
echo "==> Installing fbi (framebuffer image viewer)…"
sudo apt-get install -y fbi

echo ""
echo "==> Installing VLC (video player)…"
sudo apt-get install -y vlc

echo ""
echo "==> Installing Python 3…"
sudo apt-get install -y python3 python3-pip python3-venv

# ── 2. Python virtual environment ────────────────────────────────────────────
echo ""
echo "==> Creating Python virtual environment…"
cd "$PROJECT_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
deactivate

# ── 3. Create media directory ────────────────────────────────────────────────
mkdir -p "$PROJECT_DIR/media"

chmod +x "$PROJECT_DIR/scripts/start.sh"

echo ""
echo "============================================================"
echo " Installation complete!"
echo ""
echo " Start the server:    ./scripts/start.sh"
echo " Web UI:              http://$(hostname -I | awk '{print $1}'):8000"
echo "============================================================"
