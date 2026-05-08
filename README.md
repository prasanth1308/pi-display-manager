# Pi Display Manager

A web-based display manager for Raspberry Pi OS Lite. Control image slideshows, PDF presentations, and video playback on your Pi's framebuffer — no desktop environment required — through a clean, responsive web interface.

![Version](https://img.shields.io/badge/version-2.0-blue)
![Python](https://img.shields.io/badge/python-3.7+-green)
![License](https://img.shields.io/badge/license-MIT-orange)

## Features

- 🖼️ **Image Playlists** — Upload and cycle through images (JPG, PNG, BMP, GIF)
- 📄 **PDF Slideshows** — Upload a PDF; pages are extracted and displayed with a configurable per-page timer
- 📹 **Video Playlists** — Download and play YouTube videos in fullscreen via VLC
- 🗓️ **Scheduler** — Automatically start playlists at scheduled times (daily, weekly, or one-off)
- 🖥️ **Idle Screen** — Customisable idle screen with clock and background image shown when nothing is playing
- 🔒 **Authentication** — Session-based login with brute-force protection
- 🔄 **Real-time Status** — Live status updates without page refresh
- 📟 **Framebuffer Rendering** — Renders directly to `/dev/fb0`; no X server or desktop required

## Requirements

### Hardware
- Raspberry Pi (any model) running **Raspberry Pi OS Lite**

### System packages

| Package | Purpose |
|---|---|
| `fbi` | Framebuffer image viewer (image & PDF slideshows) |
| `vlc` | Video playback |
| `poppler-utils` | PDF → image conversion (`pdftoppm`) |
| `python3`, `python3-venv` | Runtime |

### Python packages (installed automatically into venv)
- `fastapi`, `uvicorn` — web framework
- `yt-dlp` — YouTube downloading
- `Pillow` — image processing for idle screen

## Quick Start

### 1. Clone

```bash
cd ~
git clone <your-repo-url> pi-display-manager
cd pi-display-manager
```

### 2. Run the setup script

```bash
chmod +x setup.sh
sudo ./setup.sh
```

The script installs all system packages (`fbi`, `vlc`, `poppler-utils`), creates a Python virtual environment, installs Python dependencies, and registers a systemd service that starts on boot.

### 3. Open the web interface

```
http://<raspberry-pi-ip>:8000
```

Default credentials: **admin / admin123** — change these immediately (see [Authentication](#authentication)).

## Project Structure

```
pi-display-manager/
├── backend/
│   ├── slideshow_api.py       # Entry point
│   ├── service.py             # Business logic
│   ├── controller.py          # HTTP routing
│   └── auth.py                # Authentication
├── frontend/
│   ├── index.html             # Main UI
│   ├── login.html             # Login page
│   ├── style.css
│   └── scripts/
│       ├── config.js          # Constants & playlist type config
│       ├── dom.js             # DOM references
│       ├── state.js           # App state
│       ├── ui.js              # UI helpers
│       ├── api.js             # API client
│       ├── events.js          # Event wiring
│       ├── app.js             # Initialisation
│       ├── auth.js            # Auth module
│       └── managers/
│           ├── playlist.js    # Playlist CRUD
│           ├── content.js     # Content coordinator
│           ├── image.js       # Image upload & display
│           ├── pdf.js         # PDF upload & display
│           ├── video.js       # Video download & display
│           ├── playback.js    # Play / stop controls
│           ├── idle.js        # Idle screen settings
│           ├── schedule.js    # Scheduler UI
│           └── status.js      # Status bar
├── data/                      # Auto-generated at runtime
│   ├── playlists/             # Image & PDF playlist folders
│   ├── videos/                # Video playlist folders
│   └── idle/                  # Idle screen background image
├── auth.json                  # User & session config
├── config.json                # App config (port, delay, framebuffer)
├── playlists.json             # Playlist database (auto-generated)
├── schedules.json             # Schedule database (auto-generated)
├── requirements.txt           # Python dependencies
├── setup.sh                   # Installation script
└── pi-slideshow.service       # Systemd unit file
```

## Configuration

Edit `config.json`:

```json
{
  "api_port": 8000,
  "delay": 5,
  "framebuffer": "/dev/fb0"
}
```

| Key | Description | Default |
|---|---|---|
| `api_port` | Web interface port | `8000` |
| `delay` | Seconds between slides for image playlists | `5` |
| `framebuffer` | Framebuffer device | `/dev/fb0` |

> PDF playlists have their own per-playlist **seconds per page** setting that overrides `delay`.

Restart after changes:

```bash
sudo systemctl restart pi-slideshow
```

## Authentication

### Default credentials

```
Username: admin
Password: admin123
```

**Change these immediately after first login.**

### Managing users — `auth.json`

```json
{
  "users": [
    { "username": "admin", "password": "admin123", "role": "admin" }
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

For hashed passwords (recommended):

```python
import hashlib
print(hashlib.sha256("your_password".encode()).hexdigest())
```

## Usage

### Playlist types

#### Image playlist
1. Click **New Playlist** → select *Image Playlist* → Create
2. Click the playlist card → **Upload Images**
3. Select the playlist and click **▶ Play**

#### PDF slideshow
1. Click **New Playlist** → select *PDF Slideshow* → set **Seconds per page** → Create
2. Click the playlist card → **Upload PDF**
3. The PDF is converted to images server-side (requires `poppler-utils`)
4. The **Seconds per page** timer can be changed at any time from the content panel
5. Select the playlist and click **▶ Play**

#### Video playlist (YouTube)
1. Click **New Playlist** → select *Video Playlist (YouTube)* → Create
2. Click the playlist card → **Download Video** → paste a YouTube URL
3. Select the playlist and click **▶ Play**

### Idle screen
Configure a background image and optional text displayed when no playlist is playing. The clock updates every minute. Enable it in the **Idle Screen** section and click **Save & Apply**.

### Scheduler
Create schedules to automatically start playlists at set times:
- **Daily** — every day at a given time
- **Weekly** — chosen days of the week
- **Once** — a specific date and time

## API Reference

### Status

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/status` | Current playback status |
| GET | `/api/health` | Health check |

### Playlists

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/playlists` | List all playlists |
| POST | `/api/playlists/create` | Create playlist (`name`, `type`, `page_duration`) |
| DELETE | `/api/playlists/{id}` | Delete playlist |
| PUT | `/api/playlists/{id}` | Update settings (`page_duration`) |
| GET | `/api/playlists/{id}/images` | List images / PDF pages |
| POST | `/api/playlists/{id}/upload` | Upload image (multipart, field: `image`) |
| POST | `/api/playlists/{id}/upload-pdf` | Upload PDF (multipart, field: `pdf`) |
| DELETE | `/api/playlists/{id}/images/{filename}` | Delete image |
| GET | `/api/playlists/{id}/videos` | List videos |
| POST | `/api/playlists/{id}/download` | Start YouTube download (`url`) |
| GET | `/api/download/{download_id}` | Poll download progress |
| DELETE | `/api/playlists/{id}/videos/{filename}` | Delete video |

### Playback

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/start?playlist={id}` | Start playback |
| GET | `/api/stop` | Stop playback |
| GET | `/api/clear` | Clear framebuffer |

### Idle screen

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/idle-config` | Get idle config |
| POST | `/api/idle-config` | Save idle config |
| POST | `/api/idle-config/upload` | Upload idle background (multipart, field: `file`) |

### Scheduler

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/schedules` | List schedules |
| POST | `/api/schedules` | Create schedule |
| PUT | `/api/schedules/{id}` | Update schedule |
| DELETE | `/api/schedules/{id}` | Delete schedule |

## Service Management

```bash
sudo systemctl start pi-slideshow      # Start
sudo systemctl stop pi-slideshow       # Stop
sudo systemctl restart pi-slideshow    # Restart
sudo systemctl status pi-slideshow     # Check status
sudo systemctl enable pi-slideshow     # Auto-start on boot
sudo systemctl disable pi-slideshow    # Disable auto-start

sudo journalctl -u pi-slideshow -f     # Follow logs
sudo journalctl -u pi-slideshow -n 50  # Last 50 lines
```

## Troubleshooting

### Images / PDF pages not displaying

```bash
# Check fbi is installed
which fbi

# Check poppler-utils (for PDF)
which pdftoppm

# Test fbi directly
sudo fbi -T 1 -d /dev/fb0 /path/to/image.jpg

# Check framebuffer permissions
ls -l /dev/fb0
```

### PDF upload fails with "pdftoppm not found"

```bash
sudo apt-get install poppler-utils
```

### Service won't start

```bash
sudo journalctl -u pi-slideshow -n 50

# Check port
sudo netstat -tulpn | grep 8000
```

### Cannot access web interface

```bash
sudo systemctl status pi-slideshow
curl http://localhost:8000/api/health
```

### Screen not clearing after stop

```bash
sudo dd if=/dev/zero of=/dev/fb0 bs=1M count=10
# or
curl http://localhost:8000/api/clear
```

## Security Notes

- Run on a trusted local network; the service has no HTTPS
- The service requires root access to write to `/dev/fb0`
- Change the default password and `session.secret_key` in `auth.json` before exposing on any network

## License

MIT — free to use and modify.
