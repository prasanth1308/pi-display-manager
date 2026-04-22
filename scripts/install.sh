#!/usr/bin/env bash
# ── Pi Display Manager — Raspberry Pi setup script ──────────────────────────
# Tested on Raspberry Pi OS Lite (Bookworm / Bullseye)
# Run once after cloning the repo:  chmod +x scripts/install.sh && ./scripts/install.sh

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
echo "Installing Pi Display Manager in: $PROJECT_DIR"

# ── 1. System packages ───────────────────────────────────────────────────────
echo ""
echo "==> Updating package lists…"
sudo apt-get update -y

echo ""
echo "==> Installing X11 (minimal window manager)…"
sudo apt-get install -y \
  xserver-xorg \
  x11-xserver-utils \
  openbox \
  xinit

echo ""
echo "==> Installing media tools…"
sudo apt-get install -y \
  mpv \
  poppler-utils  # pdftoppm for PDF conversion

echo ""
echo "==> Installing LibreOffice (for PPT/PPTX → PNG conversion)…"
echo "    This may take a few minutes…"
sudo apt-get install -y libreoffice-impress

echo ""
echo "==> Installing Python 3…"
sudo apt-get install -y python3 python3-pip python3-venv

# ── 2. Allow X11 for non-root users ─────────────────────────────────────────
echo ""
echo "==> Configuring X11 permissions…"
echo "needs_root_rights=no" | sudo tee /etc/X11/Xwrapper.config > /dev/null

# ── 3. Python virtual environment ───────────────────────────────────────────
echo ""
echo "==> Creating Python virtual environment…"
cd "$PROJECT_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q

deactivate

# ── 4. Create media directories ──────────────────────────────────────────────
mkdir -p "$PROJECT_DIR/media"
mkdir -p "$PROJECT_DIR/converted"

# ── 5. Make scripts executable ───────────────────────────────────────────────
chmod +x "$PROJECT_DIR/scripts/start.sh"

echo ""
echo "============================================================"
echo " Installation complete!"
echo ""
echo " Start the server:    ./scripts/start.sh"
echo " Or as a service:     sudo cp scripts/pi-display.service /etc/systemd/system/"
echo "                      sudo systemctl enable --now pi-display"
echo ""
echo " Access from network: http://$(hostname -I | awk '{print $1}'):8000"
echo "============================================================"
