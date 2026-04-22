# Architecture — Pi Display Manager

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│              Office Network (LAN / WiFi)                    │
│                                                             │
│   ┌──────────────────┐        ┌──────────────────┐         │
│   │  PC / Phone      │        │  Physical Pi     │         │
│   │  Browser         │        │  Keyboard        │         │
│   │  http://pi:8000  │        │  (spacebar, →)   │         │
│   └────────┬─────────┘        └────────┬─────────┘         │
└────────────│─────────────────────────  │ ────────────────── ┘
             │                           │
             ▼                           ▼
┌─────────────────────────────────────────────────────────────┐
│                 Raspberry Pi 3 Model A+                     │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              FastAPI Web Server (:8000)              │   │
│  │                                                     │   │
│  │  /api/files      → FileRouter   ─→ Local Storage    │   │
│  │  /api/playlists  → PlaylistRouter → SQLite DB       │   │
│  │  /api/schedules  → ScheduleRouter → APScheduler     │   │
│  │  /api/control    → ControlRouter → DisplayPlayer    │   │
│  │  /               → Static HTML/JS/CSS               │   │
│  └───────────────────────────┬─────────────────────────┘   │
│                               │                             │
│  ┌────────────────────────────▼──────────────────────────┐ │
│  │                  DisplayPlayer                        │ │
│  │                                                       │ │
│  │  play_playlist() → background thread                  │ │
│  │  pause/resume    → threading.Event                    │ │
│  │  next            → threading.Event                    │ │
│  │  stop            → threading.Event                    │ │
│  │                                                       │ │
│  │  Per item:                                            │ │
│  │  ├── image/slide → mpv --no-audio (image display)    │ │
│  │  └── video       → mpv (full playback)               │ │
│  └───────────────────────────┬─────────────────────────-─┘ │
│                               │ DISPLAY=:0                  │
│  ┌────────────────────────────▼───────────────────────────┐ │
│  │              X11 (minimal openbox)                     │ │
│  └────────────────────────────┬───────────────────────────┘ │
│                               │ HDMI                        │
└───────────────────────────────│─────────────────────────────┘
                                ▼
                         Office TV / Monitor
```

## Component Breakdown

### 1. Web Server — `main.py`
- **Framework**: FastAPI (Python)
- **Transport**: Uvicorn ASGI server
- **Port**: 8000 (all interfaces)
- **Responsibilities**:
  - Serves the single-page frontend (`frontend/index.html`)
  - Mounts static assets (`frontend/static/`)
  - Registers API routers
  - Initializes DB and scheduler on startup

### 2. Database — `database.py` + `models.py`
- **Engine**: SQLite (file: `pi_display.db`)
- **ORM**: SQLAlchemy

| Table | Purpose |
|-------|---------|
| `media_files` | Uploaded file metadata (path, type, name) |
| `playlists` | Named collections of media items |
| `playlist_items` | Ordered items in a playlist with per-item duration |
| `schedules` | Cron-based triggers linked to playlists |

### 3. File Storage — `routers/files.py`
- **Upload directory**: `media/` (flat, UUID-named files)
- **Conversion directory**: `converted/<uuid>/` (per-presentation PNG slides)
- On upload, PPT/PDF files are immediately converted to PNGs via LibreOffice headless
- File type is determined by extension

### 4. PPT Conversion — `converter.py`
```
PPTX/PPT/ODP  →  LibreOffice headless  →  PDF  →  PNG images
PDF           →  pdftoppm (poppler)    →  PNG images
```
- Slides become individually addressable PNG files
- Stored in `converted/<file-uuid>/slide-001.png`, etc.
- Treated as images by the playlist system

### 5. Playback Engine — `player.py`
- **Single media player**: `mpv` (handles both video and image display)
- **Control mechanism**: Python `threading.Event` flags + subprocess management
- **Playlist loop**: Background thread iterates items, waits per-item duration

```
play_playlist(items)
    └── Thread: _run_playlist()
          └── for each item:
                ├── kill previous mpv process
                ├── spawn: mpv --fullscreen <file>
                └── wait(duration) OR stop/next event
```

**Control signals**:
| Action | Mechanism |
|--------|-----------|
| Pause | `_pause_event.set()` — thread stops counting duration |
| Resume | `_pause_event.clear()` |
| Next | `_next_event.set()` — thread skips wait loop |
| Stop | `_stop_event.set()` + kill mpv process |

### 6. Scheduler — `scheduler_service.py`
- **Library**: APScheduler (BackgroundScheduler)
- **Trigger type**: CronTrigger (standard 5-field cron)
- Schedules are loaded from DB on startup
- New/updated schedules are hot-reloaded without restart
- Example: `0 9 * * 1-5` = weekdays at 9:00am

### 7. Frontend — `frontend/`
- **Pure HTML/CSS/JS** — no framework, no build step
- Single-page app with 4 tabs:

| Tab | Purpose |
|-----|---------|
| Files | Upload, preview, delete media files |
| Playlists | Create/edit ordered playlists |
| Schedules | Set cron schedules for auto-play |
| Control | Manual play/pause/stop/next + live status |

- Polls `/api/control/status` every 3 seconds for live status
- File upload uses `FormData` with progress feedback

## Data Flow Examples

### Upload a PowerPoint
```
Browser → POST /api/files/upload (multipart)
  → Save to media/abc123.pptx
  → LibreOffice: convert to PNG slides
  → Save slides to converted/abc123/slide-001.png ...
  → Insert MediaFile row (type=presentation)
  → Return file metadata
```

### Play a Playlist
```
Browser → POST /api/control/play { playlist_id: 3 }
  → Load playlist items from DB
  → DisplayPlayer.play_playlist(items)
  → Thread starts
  → mpv --fullscreen slide-001.png  (10s)
  → mpv --fullscreen slide-002.png  (10s)
  → mpv --fullscreen video.mp4      (until end)
  → loop back to start
```

### Scheduled Playback
```
APScheduler fires at cron time
  → play_scheduled_playlist(playlist_id=2)
  → Same as manual play flow above
```

## Resource Usage Estimates (Pi 3 A+)

| Component | RAM Usage |
|-----------|-----------|
| FastAPI + Uvicorn | ~60 MB |
| mpv (image) | ~30 MB |
| mpv (video 1080p) | ~80–120 MB |
| OS (RPi OS Lite) | ~80 MB |
| **Total** | **~250–300 MB** |

Leaves ~200MB headroom on 512MB RAM.

## X11 Display Setup

RPi OS Lite has no desktop by default. Minimal X11 is added:

```bash
sudo apt-get install -y xserver-xorg x11-xserver-utils openbox xinit
```

`start.sh` launches:
```bash
startx /usr/bin/openbox-session -- :0 &   # lightweight window manager
DISPLAY=:0 uvicorn main:app ...           # server with display access
```

mpv uses `DISPLAY=:0` to render fullscreen on the TV output.

## Network Access

The web server binds to `0.0.0.0:8000`, accessible at:
```
http://<raspberry-pi-ip>:8000
```

No authentication is implemented (trusted LAN assumed). To restrict access, use UFW:
```bash
sudo ufw allow from 192.168.1.0/24 to any port 8000
```

## File Naming Convention

Uploaded files are renamed to `<uuid4>.<ext>` to avoid collisions:
```
media/
├── 3f4a1b2c-...-.jpg
├── 7d8e9f0a-...-.mp4
└── a1b2c3d4-...-.pptx

converted/
└── a1b2c3d4-.../   ← matches pptx uuid
    ├── slide-001.png
    ├── slide-002.png
    └── slide-003.png
```

## Cron Expression Reference

| Expression | Meaning |
|-----------|---------|
| `0 9 * * *` | Every day at 9:00 AM |
| `0 9 * * 1-5` | Weekdays at 9:00 AM |
| `0 9,13,17 * * *` | 9 AM, 1 PM, 5 PM daily |
| `*/30 * * * *` | Every 30 minutes |
| `0 8 * * 1` | Every Monday at 8 AM |
