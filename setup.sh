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
echo "[1/10] Updating package list..."
sudo apt-get update

# Install fbi package
echo "[2/10] Installing fbi (framebuffer image viewer)..."
sudo apt-get install -y fbi

# Install VLC for video playback
echo "[3/10] Installing VLC media player..."
sudo apt-get install -y vlc

# Install ffmpeg for video processing
echo "[4/10] Installing ffmpeg (includes ffprobe)..."
sudo apt-get install -y ffmpeg
echo "ffmpeg installed: $(ffmpeg -version | head -n 1)"

# Install poppler-utils for PDF conversion
echo "[5/10] Installing poppler-utils (for PDF conversion)..."
sudo apt-get install -y poppler-utils
echo "poppler-utils installed successfully"

# Install LibreOffice for PowerPoint conversion
echo "[6/10] Installing LibreOffice (for PowerPoint conversion)..."
echo "Note: This may take several minutes..."
sudo apt-get install -y libreoffice --no-install-recommends
echo "LibreOffice installed: $(soffice --version 2>/dev/null || echo 'version check failed')"

# Install Python3 and pip
echo "[7/10] Checking Python3 and pip..."
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
echo "[8/10] Setting up directory structure..."
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
echo "[9/10] Creating Python virtual environment..."
if [ ! -d "$SCRIPT_DIR/venv" ]; then
    python3 -m venv "$SCRIPT_DIR/venv"
    echo "Virtual environment created at $SCRIPT_DIR/venv"
else
    echo "Virtual environment already exists"
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

# Setup systemd service
echo "[10/10] Setting up systemd service..."
if [ -f "$SCRIPT_DIR/pi-slideshow.service" ]; then
    # Determine the actual installation path
    INSTALL_PATH="$SCRIPT_DIR"

    # Copy service file to systemd directory
    sudo cp "$SCRIPT_DIR/pi-slideshow.service" /etc/systemd/system/

    # Update service file with correct paths (service runs as root for framebuffer access)
    sudo sed -i "s|WorkingDirectory=/home/larokiaraj/pi-display-manager|WorkingDirectory=$INSTALL_PATH|g" /etc/systemd/system/pi-slideshow.service
    sudo sed -i "s|ExecStart=/home/larokiaraj/pi-display-manager/venv/bin/python3 /home/larokiaraj/pi-display-manager/backend/slideshow_api.py|ExecStart=$INSTALL_PATH/venv/bin/python3 $INSTALL_PATH/backend/slideshow_api.py|g" /etc/systemd/system/pi-slideshow.service

    # Reload systemd daemon
    sudo systemctl daemon-reload

    # Enable service to start on boot
    sudo systemctl enable pi-slideshow.service

    # Set framebuffer permissions
    sudo chmod 666 /dev/fb0

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
