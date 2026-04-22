# Pi Display Manager

A lightweight web-based media presentation system for **Raspberry Pi 3 Model A+** (512MB RAM) running **Raspberry Pi OS Lite**. Displays images, videos, and PowerPoint presentations on an office TV via HDMI.

## Features

- **Upload** images, videos, and presentations (PPT/PPTX/PDF) from any browser on the local network
- **Playlists** — organize files into ordered playlists with per-item display durations
- **Schedules** — auto-play playlists at specific times using cron expressions
- **Remote control** — Play, Pause, Resume, Stop, Next from the web UI
- **Physical keyboard** — arrow keys and spacebar work directly on the Pi
- **Low resource usage** — uses `mpv` for playback, no heavy GUI stack

## Hardware Requirements

| Component | Spec |
|-----------|------|
| Device | Raspberry Pi 3 Model A+ |
| RAM | 512 MB |
| Storage | 8GB+ microSD recommended |
| OS | Raspberry Pi OS Lite (Bookworm/Bullseye) |
| Display | HDMI to TV |
| Network | WiFi or Ethernet |

## Quick Start (on the Pi)

```bash
git clone <repo-url> /home/pi/pi-display-manager
cd /home/pi/pi-display-manager
chmod +x scripts/install.sh
./scripts/install.sh
```

Then start the server:
```bash
./scripts/start.sh
```

Access the web UI from any device on the same network:
```
http://<pi-ip-address>:8000
```

Find your Pi's IP with: `hostname -I`

## Manual Installation

See [ARCHITECTURE.md](ARCHITECTURE.md) for full component details.

### Dependencies
```bash
sudo apt-get install -y xserver-xorg x11-xserver-utils openbox xinit
sudo apt-get install -y feh mpv libreoffice-impress poppler-utils
sudo apt-get install -y python3 python3-pip python3-venv
```

### Python Setup
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Run
```bash
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Run as a System Service (auto-start on boot)

```bash
sudo cp scripts/pi-display.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable pi-display
sudo systemctl start pi-display
```

## Supported File Types

| Type | Formats |
|------|---------|
| Images | `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.webp` |
| Videos | `.mp4`, `.avi`, `.mkv`, `.mov`, `.webm` |
| Presentations | `.pptx`, `.ppt`, `.odp`, `.pdf` |

> Presentations are automatically converted to PNG images on upload using LibreOffice headless.

## Project Structure

```
pi-display-manager/
├── main.py                  # FastAPI app entry point
├── database.py              # SQLite setup
├── models.py                # Database models
├── player.py                # Display controller (mpv)
├── converter.py             # PPT/PDF → PNG conversion
├── scheduler_service.py     # APScheduler integration
├── routers/
│   ├── files.py             # Upload/delete API
│   ├── playlists.py         # Playlist CRUD API
│   ├── schedules.py         # Schedule CRUD API
│   └── control.py           # Playback control API
├── frontend/
│   ├── index.html           # Single-page web UI
│   └── static/
│       ├── css/style.css
│       └── js/app.js
├── scripts/
│   ├── install.sh           # Full Pi setup script
│   ├── start.sh             # Start server + display
│   └── pi-display.service   # systemd service
├── media/                   # Uploaded files (gitignored)
├── converted/               # PPT→PNG outputs (gitignored)
└── requirements.txt
```

## Development (on Mac/PC)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

> On non-Pi systems, playback controls will log commands but won't launch mpv unless it's installed.

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/files/` | List all uploaded files |
| POST | `/api/files/upload` | Upload a file |
| DELETE | `/api/files/{id}` | Delete a file |
| GET | `/api/playlists/` | List all playlists |
| POST | `/api/playlists/` | Create a playlist |
| PUT | `/api/playlists/{id}` | Update a playlist |
| DELETE | `/api/playlists/{id}` | Delete a playlist |
| GET | `/api/schedules/` | List all schedules |
| POST | `/api/schedules/` | Create a schedule |
| PUT | `/api/schedules/{id}` | Update a schedule |
| DELETE | `/api/schedules/{id}` | Delete a schedule |
| POST | `/api/control/play` | Play a file or playlist |
| POST | `/api/control/pause` | Pause playback |
| POST | `/api/control/resume` | Resume playback |
| POST | `/api/control/stop` | Stop playback |
| POST | `/api/control/next` | Skip to next item |
| GET | `/api/control/status` | Get current playback status |

Full interactive API docs: `http://<pi-ip>:8000/docs`
