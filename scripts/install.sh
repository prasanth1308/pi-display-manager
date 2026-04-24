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

echo ""
echo "==> Installing ffmpeg (for yt-dlp video processing)…"
sudo apt-get install -y ffmpeg

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
chmod +x "$PROJECT_DIR/scripts/service.sh"

# ── 4. Add user to required groups ──────────────────────────────────────────
echo ""
echo "==> Adding user to video and tty groups (for framebuffer access)…"
CURRENT_USER="$(whoami)"
sudo usermod -a -G video,tty "$CURRENT_USER"

# ── 5. Install systemd service ───────────────────────────────────────────────
echo ""
echo "==> Setting up systemd service for auto-start on boot…"

SERVICE_FILE="/tmp/pi-display.service"

sed -e "s|__USER__|$CURRENT_USER|g" \
    -e "s|__PROJECT_DIR__|$PROJECT_DIR|g" \
    "$PROJECT_DIR/scripts/pi-display.service" > "$SERVICE_FILE"

# Install service
sudo cp "$SERVICE_FILE" /etc/systemd/system/pi-display.service
rm "$SERVICE_FILE"

# Reload systemd and enable service
sudo systemctl daemon-reload
sudo systemctl enable pi-display.service

echo ""
echo "============================================================"
echo " Installation complete!"
echo ""
echo " IMPORTANT: User added to 'video' and 'tty' groups."
echo " You must REBOOT or log out/in for group changes to take effect."
echo ""
echo " After reboot, the service will start automatically."
echo ""
echo " Manual control:"
echo "   Start now:         ./scripts/service.sh start"
echo "   Stop:              ./scripts/service.sh stop"
echo "   View logs:         ./scripts/service.sh logs"
echo "   Check status:      ./scripts/service.sh status"
echo ""
echo " ✓ Service is enabled and will start automatically on boot"
echo " Web UI:              http://$(hostname -I | awk '{print $1}'):8000"
echo ""
echo " REBOOT NOW:          sudo reboot"
echo "============================================================"
