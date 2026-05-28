#!/bin/bash
set -e

echo "=========================================="
echo "Pi Display Manager v2.0 - Setup Script"
echo "=========================================="
echo ""

# Check if running on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
    echo "Warning: This script is designed for Raspberry Pi."
    echo "Some dependencies may not work on other systems."
    echo ""
fi

# Update package list
echo "[1/11] Updating package list..."
sudo apt-get update

# Install fbi package
echo "[2/11] Checking fbi (framebuffer image viewer)..."
if ! dpkg -l | grep -q "^ii.*fbi "; then
    echo "Installing fbi..."
    sudo apt-get install -y fbi
else
    echo "fbi already installed"
fi

# Install Bluetooth packages
echo "[3/11] Checking Bluetooth packages..."
for pkg in bluetooth bluez bluez-tools avahi-daemon avahi-utils wireless-tools python3-gi python3-dbus dnsmasq; do
    if ! dpkg -l | grep -q "^ii.*$pkg "; then
        echo "Installing $pkg..."
        sudo apt-get install -y "$pkg"
    else
        echo "$pkg already installed"
    fi
done


# Ensure Bluetooth and Avahi are enabled
sudo systemctl enable bluetooth
sudo systemctl enable avahi-daemon
sudo systemctl restart bluetooth
sudo systemctl restart avahi-daemon

# Install VLC for video playback
echo "[4/11] Checking VLC media player..."
if ! dpkg -l | grep -q "^ii.*vlc "; then
    echo "Installing VLC..."
    sudo apt-get install -y vlc
else
    echo "VLC already installed"
fi

# Install ffmpeg for video processing
echo "[5/11] Checking ffmpeg (includes ffprobe)..."
if ! command -v ffmpeg &> /dev/null; then
    echo "Installing ffmpeg..."
    sudo apt-get install -y ffmpeg
    echo "ffmpeg installed: $(ffmpeg -version | head -n 1)"
else
    echo "ffmpeg already installed: $(ffmpeg -version | head -n 1)"
fi

# Install poppler-utils for PDF conversion
echo "[6/11] Checking poppler-utils (for PDF conversion)..."
if ! command -v pdftoppm &> /dev/null; then
    echo "Installing poppler-utils..."
    sudo apt-get install -y poppler-utils
    echo "poppler-utils installed successfully"
else
    echo "poppler-utils already installed"
fi

# Install LibreOffice for PowerPoint conversion
echo "[7/11] Checking LibreOffice (for PowerPoint conversion)..."
if ! command -v soffice &> /dev/null; then
    echo "Installing LibreOffice (this may take several minutes)..."
    sudo apt-get install -y libreoffice --no-install-recommends
    echo "LibreOffice installed: $(soffice --version 2>/dev/null || echo 'version check failed')"
else
    echo "LibreOffice already installed: $(soffice --version 2>/dev/null)"
fi

# Install Python3 and pip
echo "[8/11] Checking Python3 and pip..."
if ! command -v python3 &> /dev/null; then
    echo "Installing Python3..."
    sudo apt-get install -y python3
else
    echo "Python3 already installed: $(python3 --version)"
fi

# Install python3-venv and python3-full if not available
if ! dpkg -l | grep -q python3-venv; then
    echo "Installing python3-venv..."
    sudo apt-get install -y python3-venv python3-full
else
    echo "python3-venv already installed"
fi

# Set up directory structure (moved before venv creation)
echo "[9/11] Setting up directory structure..."
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Create data directories
mkdir -p "$SCRIPT_DIR/data/playlists/default"
mkdir -p "$SCRIPT_DIR/data/videos"
mkdir -p "$SCRIPT_DIR/data/uploads"
mkdir -p "$SCRIPT_DIR/frontend"

echo "Created data directories:"
echo "  - $SCRIPT_DIR/data/playlists/default"
echo "  - $SCRIPT_DIR/data/videos"
echo "  - $SCRIPT_DIR/data/uploads"
echo "  - $SCRIPT_DIR/frontend"

# Create virtual environment
echo "[10/11] Creating Python virtual environment..."
if [ ! -d "$SCRIPT_DIR/venv" ]; then
    python3 -m venv --system-site-packages "$SCRIPT_DIR/venv"
    echo "Virtual environment created at $SCRIPT_DIR/venv"
else
    echo "Virtual environment already exists"
    if [ -f "$SCRIPT_DIR/venv/pyvenv.cfg" ]; then
        sudo sed -i 's/^include-system-site-packages = false/include-system-site-packages = true/' "$SCRIPT_DIR/venv/pyvenv.cfg" || true
    fi
fi

# Install Python packages in virtual environment
echo "Installing Python packages (yt-dlp)..."
if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
    "$SCRIPT_DIR/venv/bin/pip" install --upgrade pip
    "$SCRIPT_DIR/venv/bin/pip" install --upgrade -r "$SCRIPT_DIR/requirements.txt"
    echo "Python packages installed in virtual environment"
else
    echo "Installing yt-dlp directly..."
    "$SCRIPT_DIR/venv/bin/pip" install --upgrade pip
    "$SCRIPT_DIR/venv/bin/pip" install --upgrade yt-dlp
fi

# Make scripts executable
chmod +x "$SCRIPT_DIR/backend/slideshow_api.py"
if [ -f "$SCRIPT_DIR/backend/bluetooth_pan_manager.sh" ]; then
    chmod +x "$SCRIPT_DIR/backend/bluetooth_pan_manager.sh"
fi
if [ -f "$SCRIPT_DIR/backend/bluetooth_stack_manager.sh" ]; then
    chmod +x "$SCRIPT_DIR/backend/bluetooth_stack_manager.sh"
fi

# Stop and clean up existing service before re-setup
echo "Preparing existing pi-slideshow service (if any)..."
if sudo systemctl list-unit-files | grep -q "^pi-slideshow.service"; then
    if sudo systemctl is-active --quiet pi-slideshow.service; then
        echo "Stopping running pi-slideshow service..."
        sudo systemctl stop pi-slideshow.service || true
    fi

    echo "Disabling previous pi-slideshow service instance..."
    sudo systemctl disable pi-slideshow.service >/dev/null 2>&1 || true
    sudo systemctl reset-failed pi-slideshow.service >/dev/null 2>&1 || true
fi

# Remove stale runtime processes from previous runs
sudo pkill -f "backend/slideshow_api.py" >/dev/null 2>&1 || true
sudo pkill -x fbi >/dev/null 2>&1 || true
sudo pkill -f "bt-network -s nap" >/dev/null 2>&1 || true

# Setup systemd service
echo "[11/11] Setting up systemd service..."
if [ -f "$SCRIPT_DIR/pi-slideshow.service" ]; then
    # Always replace existing units in systemd folder with latest files from repo
    sudo rm -f /etc/systemd/system/pi-slideshow.service
    sudo cp "$SCRIPT_DIR/pi-slideshow.service" /etc/systemd/system/pi-slideshow.service

    # Replace unified Bluetooth stack unit
    if [ -f "$SCRIPT_DIR/pi-bt-stack.service" ]; then
        sudo rm -f /etc/systemd/system/pi-bt-stack.service
        sudo cp "$SCRIPT_DIR/pi-bt-stack.service" /etc/systemd/system/pi-bt-stack.service
    fi

    # Reload systemd daemon after replacing unit files
    sudo systemctl daemon-reload

    # Enable service to start on boot
    sudo systemctl enable pi-slideshow.service

    # Disable old split Bluetooth services (if present)
    sudo systemctl disable --now pi-bt-agent.service >/dev/null 2>&1 || true
    sudo systemctl disable --now pi-bt-nap.service >/dev/null 2>&1 || true
    sudo systemctl disable --now pi-bt-pan-ip.service >/dev/null 2>&1 || true

    # Install unified Bluetooth stack service for auto-pair + PAN web access
    if [ -f "$SCRIPT_DIR/pi-bt-stack.service" ]; then
        sudo systemctl enable pi-bt-stack.service
        sudo systemctl restart pi-bt-stack.service || true
        echo "Unified Bluetooth stack service installed and enabled"
    fi

    # Set framebuffer permissions
    sudo chmod 666 /dev/fb0

    # Ensure kernel cursor is disabled on tty (idempotent)
    CMDLINE_FILE="/boot/firmware/cmdline.txt"
    if [ -f "$CMDLINE_FILE" ]; then
        if grep -q "vt.global_cursor_default=" "$CMDLINE_FILE"; then
            if grep -q "vt.global_cursor_default=1" "$CMDLINE_FILE"; then
                sudo sed -i 's/vt\.global_cursor_default=1/vt.global_cursor_default=0/g' "$CMDLINE_FILE"
                echo "Updated vt.global_cursor_default to 0 in $CMDLINE_FILE"
            else
                echo "vt.global_cursor_default already configured in $CMDLINE_FILE"
            fi
        else
            sudo sed -i 's|$| vt.global_cursor_default=0|' "$CMDLINE_FILE"
            echo "Added vt.global_cursor_default=0 to $CMDLINE_FILE"
        fi
    else
        echo "Warning: $CMDLINE_FILE not found; skipping cursor kernel parameter"
    fi

    # Start the service
    sudo systemctl start pi-slideshow.service

    echo "Systemd service installed and enabled"
else
    echo "Warning: pi-slideshow.service file not found"
fi

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "🎉 Pi Display Manager is now running!"
echo ""
echo "Web Interface:"
echo "  http://$(hostname -I | awk '{print $1}')"
echo "  or"
echo "  http://localhost"
echo ""
echo "Service Management Commands:"
echo "  sudo systemctl start pi-slideshow    - Start the service"
echo "  sudo systemctl stop pi-slideshow     - Stop the service"
echo "  sudo systemctl restart pi-slideshow  - Restart the service"
echo "  sudo systemctl status pi-slideshow   - Check service status"
echo "  sudo systemctl enable pi-slideshow   - Auto-start on boot (already done)"
echo "  sudo systemctl disable pi-slideshow  - Disable auto-start"
echo ""
echo "View logs:"
echo "  sudo journalctl -u pi-slideshow -f   - Follow logs in real-time"
echo "  sudo journalctl -u pi-slideshow -n 50 - Last 50 log lines"
echo ""
echo "API Endpoints (curl examples):"
echo "  curl http://localhost/api/health"
echo "  curl http://localhost/api/status"
echo "  curl http://localhost/api/playlists"
echo "  curl http://localhost/api/start?playlist=default"
echo "  curl http://localhost/api/stop"
echo ""
echo "Configuration:"
echo "  Config file: $SCRIPT_DIR/config.json"
echo "  Data directory: $SCRIPT_DIR/data"
echo "  Image Playlists: $SCRIPT_DIR/data/playlists"
echo "  Video Playlists: $SCRIPT_DIR/data/videos"
echo ""
echo "Next Steps:"
echo "  1. Open the web interface in your browser"
echo "  2. Create playlists (images or videos)"
echo "  3. Upload images or download YouTube videos"
echo "  4. Click 'Play' to start"
echo ""
