# Pi Display Manager

A modern web-based image slideshow manager for Raspberry Pi with playlist support. Display images on your Pi's screen via the framebuffer using an intuitive web interface.

![Version](https://img.shields.io/badge/version-2.0-blue)
![Python](https://img.shields.io/badge/python-3.7+-green)
![License](https://img.shields.io/badge/license-MIT-orange)

## Features

- 🎨 **Modern Web Interface** - Clean, responsive UI accessible from any device
- � **Secure Authentication** - User login with session management and configurable security
- 📁 **Multiple Playlists** - Create and manage multiple image playlists
- 📤 **Image Upload** - Upload images directly through the web interface
- ▶️ **Easy Controls** - Start, stop, and manage slideshows with one click
- 🔄 **Auto-refresh** - Real-time status updates
- 🖼️ **Framebuffer Display** - Direct rendering to Raspberry Pi display (no X server required)
- 🔒 **Single Playlist Playback** - Only one playlist can play at a time
- 🗑️ **Playlist Management** - Create, delete, and organize playlists easily
- 📹 **Video Support** - Play videos from YouTube in fullscreen
- 🎯 **Idle Screen** - Customizable idle screen with clock and background image

## Requirements

- Raspberry Pi (any model with display output)
- Python 3.7 or higher
- fbi (framebuffer image viewer)
- Network connection (for web interface access)

## Quick Start

### 1. Clone or Download

```bash
cd ~
git clone <your-repo-url> pi-display-manager
cd pi-display-manager
```

### 2. Install Dependencies

```bash
sudo apt-get update
sudo apt-get install -y fbi python3
```

### 3. Run Setup Script

```bash
chmod +x setup.sh
sudo ./setup.sh
```

The setup script will:

- Create necessary directories
- Install the systemd service
- Enable auto-start on boot
- Start the service

### 4. Access Web Interface

Open a web browser and navigate to:

```
http://<raspberry-pi-ip>
```

Or if accessing locally on the Pi:

```
http://localhost
```

## Project Structure

```
pi-display-manager/
├── backend/                   # Backend API (MVC Architecture)
│   ├── slideshow_api.py      # Main entry point (Flask)
│   ├── controllers/          # Controller layer
│   │   └── controller.py     # Flask REST API controller
│   ├── services/             # Service layer (business logic)
│   │   ├── service.py        # Core business logic
│   │   └── auth.py           # Authentication service
│   └── tests/                # Test files
├── frontend/                  # Web interface files
│   ├── index.html            # Main application page
│   ├── login.html            # Login page
│   ├── style.css             # Styles
│   └── scripts/              # JavaScript modules
│       ├── auth.js           # Authentication module
│       ├── config.js         # Configuration
│       ├── dom.js            # DOM references
│       ├── state.js          # State management
│       ├── ui.js             # UI utilities
│       ├── api.js            # API client
│       ├── events.js         # Event handlers
│       ├── app.js            # Main app
│       └── managers/         # Feature managers
│           ├── status.js     # Status management
│           ├── playlist.js   # Playlist management
│           ├── content.js    # Content coordination
│           ├── image.js      # Image management
│           ├── video.js      # Video management
│           ├── playback.js   # Playback control
│           └── idle.js       # Idle screen management
├── data/                      # Data directory (auto-generated)
│   ├── playlists/            # Playlist folders
│   │   ├── default/          # Default playlist
│   │   └── <playlist-id>/    # Other playlists
│   ├── videos/               # Video playlists
│   ├── idle/                 # Idle screen assets
│   └── uploads/              # Temporary uploads
├── auth.json                 # Authentication configuration
├── config.json               # Application configuration
├── requirements.txt          # Python dependencies
├── setup.sh                  # Installation script
├── pi-slideshow.service      # Systemd service file
├── slideshow_api_old.py      # Legacy API version
├── playlists.json            # Playlist database (auto-generated)
├── fbi_error.log             # FBI process log (auto-generated)
└── README.md                 # This file
```

### Architecture

The backend follows an **MVC (Model-View-Controller)** pattern:

- **`service.py`** - Service layer containing all business logic:
  - Slideshow management (start, stop, status)
  - Playlist CRUD operations
  - Image and video file management
  - YouTube video downloading
  - Framebuffer operations
  - Database persistence

- **`auth.py`** - Authentication service handling user login and session management

- **`controller.py`** - Flask controller with lightweight REST API:
  - RESTful API endpoints
  - Request routing with decorator-based authentication
  - JSON request/response handling
  - Static file serving
  - Comprehensive error handling

- **`slideshow_api.py`** - Entry point that initializes and runs the Flask application

## Configuration

Edit `config.json` to customize settings:

```json
{
  "api_port": 80,
  "delay": 5,
  "framebuffer": "/dev/fb0"
}
```

- **api_port**: Port for the web interface (default: 80)
- **delay**: Seconds between images (default: 5)
- **framebuffer**: Framebuffer device path (default: /dev/fb0)

After changing configuration, restart the service:

```bash
sudo systemctl restart pi-slideshow
```

## Authentication

Pi Display Manager includes user authentication to secure access to your display manager.

### Default Credentials

```
Username: admin
Password: admin123
```

⚠️ **Important**: Change the default password immediately after first login!

### Managing Users

Edit the `auth.json` file to manage users and authentication settings:

```json
{
  "users": [
    {
      "username": "admin",
      "password": "admin123",
      "role": "admin"
    }
  ],
  "session": {
    "timeout": 3600,
    "secret_key": "change-this-to-a-secure-random-string"
  },
  "security": {
    "max_login_attempts": 5,
    "lockout_duration": 300
  }
}
```

### Configuration Options

#### Users

- **username**: Login username
- **password**: User password (plain text or SHA-256 hash)
- **role**: User role (currently "admin" or "user")

#### Session

- **timeout**: Session duration in seconds (default: 3600 = 1 hour)
- **secret_key**: Secret key for session generation (change to a random string)

#### Security

- **max_login_attempts**: Maximum failed login attempts before lockout (default: 5)
- **lockout_duration**: Lockout duration in seconds after max attempts (default: 300 = 5 minutes)

### Adding New Users

1. Edit `auth.json`:

```json
{
  "users": [
    {
      "username": "admin",
      "password": "admin123",
      "role": "admin"
    },
    {
      "username": "user1",
      "password": "password123",
      "role": "user"
    }
  ],
  ...
}
```

2. Restart the service:

```bash
sudo systemctl restart pi-slideshow
```

### Using Hashed Passwords (Recommended)

For better security, use SHA-256 hashed passwords:

```python
# Generate a hashed password
import hashlib
password = "your_secure_password"
hashed = hashlib.sha256(password.encode()).hexdigest()
print(hashed)
```

Then use the hash in `auth.json`:

```json
{
  "username": "admin",
  "password": "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8",
  "role": "admin"
}
```

### Session Management

- Sessions expire after the configured timeout period
- Sessions are automatically extended on user activity
- Logout clears the session immediately
- All API endpoints require valid authentication
- Login page is accessible at `/login.html`

### Security Features

✅ **Session-based authentication** - Secure cookie-based sessions  
✅ **Login attempt limiting** - Prevents brute force attacks  
✅ **Automatic lockout** - Temporary account lock after failed attempts  
✅ **HttpOnly cookies** - Prevents XSS attacks  
✅ **SameSite cookies** - Prevents CSRF attacks  
✅ **Configurable timeouts** - Customizable session duration

## Usage

### Web Interface

1. **Create a Playlist**
   - Click "New Playlist" button
   - Enter a name and click "Create"

2. **Upload Images**
   - Click on a playlist to view its images
   - Click "Upload Images"
   - Select one or more image files
   - Supported formats: JPG, JPEG, PNG, BMP, GIF

3. **Play Slideshow**
   - Select a playlist by clicking on it
   - Click "Play Slideshow"
   - The slideshow will display on the Pi's screen

4. **Stop Slideshow**
   - Click "Stop Slideshow"
   - The screen will be cleared

5. **Manage Images**
   - Click on a playlist to view images
   - Delete individual images as needed

6. **Delete Playlist**
   - Click the trash icon on a playlist card
   - Confirm deletion
   - Note: The default playlist cannot be deleted

### API Endpoints

The backend provides a RESTful API:

#### Status

- `GET /api/status` - Get current status

#### Playlists

- `GET /api/playlists` - List all playlists
- `POST /api/playlists/create` - Create new playlist
- `DELETE /api/playlists/{id}` - Delete playlist
- `GET /api/playlists/{id}/images` - List images in playlist

#### Images

- `POST /api/playlists/{id}/upload` - Upload image (multipart/form-data)
- `DELETE /api/playlists/{id}/images/{filename}` - Delete image

#### Controls

- `GET /api/start?playlist={id}` - Start slideshow
- `GET /api/stop` - Stop slideshow
- `GET /api/clear` - Clear framebuffer

#### Health

- `GET /api/health` - Health check

### Command Line

```bash
# Check service status
sudo systemctl status pi-slideshow

# Start service
sudo systemctl start pi-slideshow

# Stop service
sudo systemctl stop pi-slideshow

# Restart service
sudo systemctl restart pi-slideshow

# View logs
sudo journalctl -u pi-slideshow -f

# Manually clear display
sudo dd if=/dev/zero of=/dev/fb0 bs=1M count=10
```

## Troubleshooting

### Service won't start

```bash
# Check logs
sudo journalctl -u pi-slideshow -n 50

# Check if port is available
sudo netstat -tulpn | grep 80

# Verify Python script
python3 slideshow_api_fastapi.py
```

### Images not displaying

```bash
# Check if fbi is installed
which fbi

# Test fbi directly
sudo fbi -T 1 -d /dev/fb0 /path/to/test-image.jpg

# Check framebuffer permissions
ls -l /dev/fb0
```

### Cannot access web interface

```bash
# Check if service is running
sudo systemctl status pi-slideshow

# Check firewall (if enabled)
sudo ufw status

# Test locally
curl http://localhost/api/health
```

### Images remain on screen after stop

```bash
# Clear the framebuffer manually
sudo dd if=/dev/zero of=/dev/fb0 bs=1M count=10

# Or use the API
curl http://localhost/api/clear
```

## Migration from Old Version

If you have images in `/home/larokiaraj/pi` from a previous version:

```bash
# Copy images to default playlist
sudo cp /home/larokiaraj/pi/*.{jpg,jpeg,png,gif,bmp} \
  ~/pi-display-manager/data/playlists/default/ 2>/dev/null

# Or upload them via the web interface
```

## Development

### Running in Development Mode

```bash
# Stop the service
sudo systemctl stop pi-slideshow

# Run manually
python3 slideshow_api_fastapi.py

# Access logs in terminal
```

### File Permissions

The service runs as root to access the framebuffer. For development:

```bash
# Add user to video group (allows framebuffer access)
sudo usermod -a -G video $USER

# Reboot for changes to take effect
sudo reboot
```

## Service Management

The application runs as a systemd service for automatic startup and management.

### Enable Auto-start

```bash
sudo systemctl enable pi-slideshow
```

### Disable Auto-start

```bash
sudo systemctl disable pi-slideshow
```

### Uninstall Service

```bash
sudo systemctl stop pi-slideshow
sudo systemctl disable pi-slideshow
sudo rm /etc/systemd/system/pi-slideshow.service
sudo systemctl daemon-reload
```

## Security Notes

- The web interface has no authentication by default
- Only expose the service on trusted networks
- Consider using a reverse proxy with authentication for public access
- The service runs as root to access the framebuffer

## Performance Tips

- Use compressed JPEGs for faster loading
- Recommended image size: Match your display resolution
- Keep playlists under 100 images for best performance
- Use appropriate delay settings in config (3-10 seconds recommended)

## Supported Image Formats

- JPEG (.jpg, .jpeg)
- PNG (.png)
- GIF (.gif)
- BMP (.bmp)

## BLE GATT Text Communication (Pi <-> macOS)

This project now includes a BLE GATT bidirectional text channel using modern Python BLE libraries:

- Pi peripheral/server: `bless` (GATT server on Linux/BlueZ)
- macOS central/client: `bleak` (GATT client)

The BLE service is started automatically inside the existing `pi-slideshow` systemd service.

### BLE Architecture

- Device name: `PiDisplayManager`
- Service UUID: `12345678-1234-5678-1234-56789abcdef0`
- Write characteristic (Mac -> Pi): `12345678-1234-5678-1234-56789abcdef1`
- Notify characteristic (Pi -> Mac): `12345678-1234-5678-1234-56789abcdef2`

Flow:

1. Pi advertises custom BLE service UUID.
2. macOS scans and connects as central.
3. macOS writes UTF-8 command text to write characteristic.
4. Pi decodes command, logs it, prints it to console, and optionally sends response via notify characteristic.
5. macOS displays notifications in terminal.

### Installed Files

- Pi peripheral implementation: `backend/ble/peripheral.py`
- Standalone Pi BLE server: `backend/ble/pi_server.py`
- macOS BLE client: `backend/ble/macos_client.py`
- Shared UUID constants: `backend/ble/constants.py`

### Pi Setup (Raspberry Pi OS Lite)

Use your existing virtual environment and service:

```bash
cd ~/pi-display-manager
./venv/bin/pip install -r requirements.txt
```

Enable Bluetooth stack and adapter:

```bash
sudo apt-get update
sudo apt-get install -y bluez bluetooth
sudo systemctl enable --now bluetooth
sudo rfkill unblock bluetooth
sudo hciconfig hci0 up
```

Restart your existing service:

```bash
sudo systemctl restart pi-slideshow
sudo systemctl status pi-slideshow
```

BLE startup and message logs are written to `slideshow.log`.

### macOS Setup

Create or use a Python 3.11+ virtual environment on macOS, then install client dependency:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install bleak
```

Run the client from this repository:

```bash
python3 backend/ble/macos_client.py
```

Optional arguments:

```bash
python3 backend/ble/macos_client.py --device-name PiDisplayManager --scan-timeout 15 --log-level DEBUG
```

### Supported BLE Commands

Send these from the macOS client prompt:

- `ping`
- `status`
- `start <playlist_id>`
- `stop`
- `default-start`

The Pi responds through notifications (for example, status JSON or command ACK/ERROR messages).

### Standalone Pi BLE Server (Optional)

If you want BLE-only testing outside Flask/systemd:

```bash
cd ~/pi-display-manager
./venv/bin/python backend/ble/pi_server.py
```

## BLE Troubleshooting

### 1. Device not discovered from macOS

- Verify Pi service is running: `sudo systemctl status pi-slideshow`
- Verify adapter is up: `hciconfig hci0`
- Ensure Bluetooth is not blocked: `rfkill list`
- Move devices closer and retry scan.

### 2. macOS does not prompt for Bluetooth permission

- First scan attempt must happen from a terminal app with BLE entitlement prompts.
- Go to `System Settings -> Privacy & Security -> Bluetooth` and allow your terminal app (Terminal/iTerm).
- Restart terminal after permission change.

### 3. BLE connection drops or reconnect loop

- Keep the Pi powered and within range.
- Check `slideshow.log` for disconnect/reconnect messages.
- Restart adapter on Pi if needed:

```bash
sudo systemctl restart bluetooth
sudo hciconfig hci0 reset
```

### 4. Writes succeed but no notifications appear

- Confirm macOS client is subscribed (client logs show subscription).
- Use short UTF-8 payloads for notifications.
- Verify UUIDs match exactly on both sides.

### 5. Service starts but BLE does not initialize

- Reinstall Python deps inside the same venv used by systemd:

```bash
cd ~/pi-display-manager
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt
sudo systemctl restart pi-slideshow
```

### 6. Log/debug output location

- Application + BLE logs: `slideshow.log` in repo root.
- Service logs: `sudo journalctl -u pi-slideshow -f`

## License

MIT License - Feel free to use and modify as needed.

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues.

## Author

Created for Raspberry Pi slideshow management with modern web interface.

## Changelog

### Version 2.0

- ✨ Complete rewrite with web interface
- 📁 Multiple playlist support
- 📤 Image upload functionality
- 🎨 Modern, responsive UI
- 🔄 Real-time status updates
- 🗑️ Playlist and image management

### Version 1.0

- Basic API for slideshow control
- Single folder support
- Command-line configuration

## Support

For issues, questions, or feature requests, please open an issue in the repository.

---

**Enjoy your Pi Display Manager! 🎉**
