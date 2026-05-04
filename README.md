# Pi Display Manager

A modern web-based image slideshow manager for Raspberry Pi with playlist support. Display images on your Pi's screen via the framebuffer using an intuitive web interface.

![Version](https://img.shields.io/badge/version-2.0-blue)
![Python](https://img.shields.io/badge/python-3.7+-green)
![License](https://img.shields.io/badge/license-MIT-orange)

## Features

- 🎨 **Modern Web Interface** - Clean, responsive UI accessible from any device
- 📁 **Multiple Playlists** - Create and manage multiple image playlists
- 📤 **Image Upload** - Upload images directly through the web interface
- ▶️ **Easy Controls** - Start, stop, and manage slideshows with one click
- 🔄 **Auto-refresh** - Real-time status updates
- 🖼️ **Framebuffer Display** - Direct rendering to Raspberry Pi display (no X server required)
- 🔒 **Single Playlist Playback** - Only one playlist can play at a time
- 🗑️ **Playlist Management** - Create, delete, and organize playlists easily

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
http://<raspberry-pi-ip>:8000
```

Or if accessing locally on the Pi:

```
http://localhost:8000
```

## Project Structure

```
pi-display-manager/
├── backend/                   # Backend API (MVC Architecture)
│   ├── slideshow_api.py      # Main entry point
│   ├── service.py            # Service layer (business logic)
│   ├── controller.py         # Controller layer (HTTP handling)
│   └── slideshow_api_backup.py  # Original monolithic version
├── frontend/                  # Web interface files
│   ├── index.html            # Main HTML page
│   ├── style.css             # Styles
│   └── app.js                # Frontend JavaScript
├── data/                      # Data directory (auto-generated)
│   ├── playlists/            # Playlist folders
│   │   ├── default/          # Default playlist
│   │   └── <playlist-id>/    # Other playlists
│   ├── videos/               # Video playlists
│   └── uploads/              # Temporary uploads
├── config.json               # Configuration file
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

- **`controller.py`** - Controller layer handling HTTP requests:
  - RESTful API endpoints
  - Request routing and validation
  - HTTP response formatting
  - Static file serving
  - Error handling

- **`slideshow_api.py`** - Entry point that initializes and runs the application

## Configuration

Edit `config.json` to customize settings:

```json
{
  "api_port": 8000,
  "delay": 5,
  "framebuffer": "/dev/fb0"
}
```

- **api_port**: Port for the web interface (default: 8000)
- **delay**: Seconds between images (default: 5)
- **framebuffer**: Framebuffer device path (default: /dev/fb0)

After changing configuration, restart the service:

```bash
sudo systemctl restart pi-slideshow
```

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
sudo netstat -tulpn | grep 8000

# Verify Python script
python3 slideshow_api.py
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
curl http://localhost:8000/api/health
```

### Images remain on screen after stop

```bash
# Clear the framebuffer manually
sudo dd if=/dev/zero of=/dev/fb0 bs=1M count=10

# Or use the API
curl http://localhost:8000/api/clear
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
python3 slideshow_api.py

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
