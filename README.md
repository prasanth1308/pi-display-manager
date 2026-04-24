# Pi Display Manager (lite)

A lightweight web-based media display system for **Raspberry Pi 3 Model A+** (512MB RAM) running **Raspberry Pi OS Lite**. Upload images and videos from any browser on your network and play them on an office TV via HDMI.

## Features

- **Upload** images and videos from any browser on the local network
- **YouTube downloads** — download videos directly from YouTube at 720p using yt-dlp
- **Playlists** — order files into playlists with per-item display duration
- **Schedules** — auto-play playlists at set times using cron expressions
- **Remote control** — Play, Pause, Resume, Stop, Next from the web UI
- **Auto-start on boot** — systemd service starts automatically when Pi powers on
- **Smooth image transitions** — fbi slideshow batches consecutive images for seamless playback
- **No desktop required** — `fbi` renders images directly to the framebuffer, no X11 needed
- **Lightweight** — minimal dependencies, optimized for 512MB RAM

## Hardware

| Component | Spec                                       |
| --------- | ------------------------------------------ |
| Device    | Raspberry Pi 3 Model A+                    |
| RAM       | 512 MB                                     |
| Storage   | 8 GB+ microSD                              |
| OS        | Raspberry Pi OS Lite (Bullseye / Bookworm) |
| Display   | HDMI to TV                                 |
| Network   | WiFi or Ethernet                           |

## Supported File Types

| Type   | Formats                                          |
| ------ | ------------------------------------------------ |
| Images | `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.webp` |
| Videos | `.mp4`, `.avi`, `.mkv`, `.mov`, `.webm`          |

## Quick Start — Raspberry Pi

```bash
git clone <repo-url> /home/pi/pi-display-manager
cd /home/pi/pi-display-manager
chmod +x scripts/install.sh
./scripts/install.sh
```

The installer automatically:

- ✓ Installs system dependencies (fbi, vlc, ffmpeg, Python)
- ✓ Creates Python virtual environment
- ✓ Installs Python packages (Flask, yt-dlp)
- ✓ Sets up systemd service for auto-start on boot

**The service starts automatically on boot.** To control it manually:

```bash
# Start the service now
./scripts/service.sh start

# Check status
./scripts/service.sh status

# View live logs
./scripts/service.sh logs

# Stop the service
./scripts/service.sh stop

# Restart after code changes
./scripts/service.sh restart
```

Open from any device on the same network:

```
http://<pi-ip>:8000
```

Find your Pi's IP: `hostname -I`

## Service Management

After installation, the Pi Display Manager runs as a systemd service:

| Command                        | Description                     |
| ------------------------------ | ------------------------------- |
| `./scripts/service.sh start`   | Start the service now           |
| `./scripts/service.sh stop`    | Stop the service                |
| `./scripts/service.sh restart` | Restart the service             |
| `./scripts/service.sh status`  | Check if running                |
| `./scripts/service.sh logs`    | View live logs (Ctrl+C to exit) |
| `./scripts/service.sh enable`  | Enable auto-start on boot       |
| `./scripts/service.sh disable` | Disable auto-start on boot      |

The service is automatically enabled during installation and will start on every boot.

## Manual Installation — Raspberry Pi

```bash
# System packages (no X11 needed)
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv fbi vlc ffmpeg

# Clone and setup
git clone <repo-url>
cd pi-display-manager
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run manually
./scripts/start.sh
```

## Development on Mac / PC

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

Open `http://localhost:8000` — upload, create playlists, and test scheduling works fully. When you hit Play on Mac it opens the file in Preview / QuickTime via `open`, so you can verify the full flow without a Pi.

## Project Structure

```
pi-display-manager/
├── main.py          # Flask app — all routes
├── database.py      # SQLite setup (built-in sqlite3)
├── player.py        # Display controller: fbi (images) + cvlc (videos)
├── scheduler.py     # Cron scheduler using threading
├── frontend/
│   ├── index.html   # Single-page web UI
│   └── static/
│       ├── css/style.css
│       └── js/app.js
├── scripts/
│   ├── install.sh           # Pi setup script
│   ├── start.sh             # Start the server
│   └── pi-display.service   # systemd unit file
├── media/           # Uploaded files (gitignored)
└── requirements.txt # Just: flask
```

## How Display Works on the Pi

| File type | Tool                              | X11 needed? |
| --------- | --------------------------------- | ----------- |
| Images    | `fbi` (framebuffer image viewer)  | No          |
| Videos    | `cvlc` (VLC CLI with `--vout fb`) | No          |

Both tools write directly to `/dev/fb0` (the HDMI framebuffer), so no desktop environment is required — keeping RAM usage low.

## Cron Expression Reference

Used for scheduling auto-play:

| Expression        | Meaning                    |
| ----------------- | -------------------------- |
| `0 9 * * *`       | Every day at 9:00 AM       |
| `0 9 * * 1-5`     | Weekdays at 9:00 AM        |
| `0 9,13,17 * * *` | 9 AM, 1 PM, and 5 PM daily |
| `*/30 * * * *`    | Every 30 minutes           |

Reference: [crontab.guru](https://crontab.guru)

## Troubleshooting

### Playlists not playing properly when running as service

**Symptom**: Images display briefly then revert, or fbi fails to show images.

**Cause**: The service user doesn't have access to the framebuffer device.

**Solution**: The installer automatically adds your user to `video` and `tty` groups, but you need to reboot for the changes to take effect:

```bash
sudo reboot
```

After reboot, check group membership:

```bash
groups
# Should show: ... video tty ...
```

### Manually add groups (if needed)

```bash
sudo usermod -a -G video,tty $(whoami)
sudo reboot
```

### Check service logs

```bash
./scripts/service.sh logs
# or
sudo journalctl -u pi-display -f
```

Look for permission errors like:

- `cannot open /dev/fb0`
- `cannot open /dev/tty`

### Test fbi manually

```bash
# Should display image on HDMI
fbi -a /path/to/image.jpg
```

If this fails, check:

- `/dev/fb0` exists: `ls -l /dev/fb0`
- User in video group: `groups`

## API Reference

| Method | Endpoint              | Description             |
| ------ | --------------------- | ----------------------- |
| GET    | `/api/files/`         | List uploaded files     |
| POST   | `/api/files/upload`   | Upload a file           |
| DELETE | `/api/files/<id>`     | Delete a file           |
| GET    | `/api/playlists/`     | List playlists          |
| POST   | `/api/playlists/`     | Create a playlist       |
| GET    | `/api/playlists/<id>` | Get playlist with items |
| PUT    | `/api/playlists/<id>` | Update a playlist       |
| DELETE | `/api/playlists/<id>` | Delete a playlist       |
| GET    | `/api/schedules/`     | List schedules          |
| POST   | `/api/schedules/`     | Create a schedule       |
| PUT    | `/api/schedules/<id>` | Update a schedule       |
| DELETE | `/api/schedules/<id>` | Delete a schedule       |
| POST   | `/api/control/play`   | Play a file or playlist |
| POST   | `/api/control/pause`  | Pause                   |
| POST   | `/api/control/resume` | Resume                  |
| POST   | `/api/control/stop`   | Stop                    |
| POST   | `/api/control/next`   | Skip to next item       |
| GET    | `/api/control/status` | Current playback status |
