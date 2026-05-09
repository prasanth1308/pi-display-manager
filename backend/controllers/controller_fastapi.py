"""
Pi Display Manager - FastAPI Controller
Modern REST API with FastAPI framework and routers.
"""

from fastapi import FastAPI, APIRouter, Depends, HTTPException, UploadFile, File, Form, Cookie, Response, Request, status as http_status
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from pathlib import Path
import uuid
import threading

# Import authentication
import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).parent.parent))

from services.auth import authenticate_user, validate_session, destroy_session

# Import service layer
from services.service import (
    # Core functions
    setup_logging, ensure_directories, load_config, load_playlists_db,
    
    # State variables
    logger, config, playlists_db, download_status, downscale_status,
    slideshow_process, video_process, STATIC_DIR, IDLE_DIR, PLAYLISTS_DIR,
    DATA_DIR, VIDEOS_DIR,
    
    # Service functions
    get_status, start_slideshow, stop_slideshow, clear_framebuffer,
    list_playlists, create_playlist, update_playlist, delete_playlist,
    get_playlist_images_list, get_playlist_videos_list,
    upload_image, delete_image, delete_video,
    skip_image, unskip_image,
    parse_multipart_form_data, parse_multipart_form_data_streaming,
    download_youtube_video, downscale_video_to_1080p,
    start_video_playback, stop_video_playback, get_playlist_videos, save_playlists_db,
    
    # Idle screen
    get_idle_config, save_idle_config, start_idle_screen, stop_idle_screen,
    
    # Scheduler
    load_schedules_db, list_schedules, get_schedule, create_schedule,
    update_schedule, delete_schedule, stop_scheduler, start_scheduler,
)

# ═══════════════════════════════════════════════════════════════════════════
# Pydantic Models
# ═══════════════════════════════════════════════════════════════════════════

class LoginRequest(BaseModel):
    username: str
    password: str

class PlaylistCreate(BaseModel):
    name: str
    type: str = "image"
    delay: int = 5

class PlaylistUpdate(BaseModel):
    name: Optional[str] = None
    delay: Optional[int] = None

class VideoDownload(BaseModel):
    url: str

class ScheduleCreate(BaseModel):
    name: str
    playlist_id: str
    cron: str
    enabled: bool = True

class ScheduleUpdate(BaseModel):
    name: Optional[str] = None
    playlist_id: Optional[str] = None
    cron: Optional[str] = None
    enabled: Optional[bool] = None

class IdleConfigUpdate(BaseModel):
    image_path: Optional[str] = None
    custom_text: Optional[str] = ""
    enabled: bool = True

# ═══════════════════════════════════════════════════════════════════════════
# Authentication Dependency
# ═══════════════════════════════════════════════════════════════════════════

async def get_current_user(session_token: Optional[str] = Cookie(None)):
    """Verify user authentication from session cookie"""
    if not session_token:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized. Please login."
        )
    
    user_info = validate_session(session_token)
    if not user_info:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session. Please login."
        )
    
    return user_info

# ═══════════════════════════════════════════════════════════════════════════
# Initialize FastAPI App
# ═══════════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="Pi Display Manager API",
    version="2.0.0",
    description="REST API for managing Raspberry Pi display slideshows and video playback"
)

# CORS middleware (if needed for development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ═══════════════════════════════════════════════════════════════════════════
# Routers
# ═══════════════════════════════════════════════════════════════════════════

# ─── Authentication Router ────────────────────────────────────────────────
auth_router = APIRouter(prefix="/api/auth", tags=["Authentication"])

@auth_router.get("/status")
async def auth_status(session_token: Optional[str] = Cookie(None)):
    """Check authentication status"""
    if session_token:
        user_info = validate_session(session_token)
        if user_info:
            return {"authenticated": True, "user": user_info}
    return {"authenticated": False}

@auth_router.post("/login")
async def login(credentials: LoginRequest, response: Response):
    """User login"""
    success, result = authenticate_user(credentials.username, credentials.password)
    
    if success:
        # Set session cookie
        response.set_cookie(
            key="session_token",
            value=result,
            httponly=True,
            samesite="strict",
            max_age=3600
        )
        return {
            "status": "success",
            "message": "Login successful",
            "user": {"username": credentials.username}
        }
    else:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail=result
        )

@auth_router.get("/logout")
async def logout(response: Response, session_token: Optional[str] = Cookie(None)):
    """User logout"""
    if session_token:
        destroy_session(session_token)
    
    response.delete_cookie("session_token")
    return {"status": "success", "message": "Logged out successfully"}

# ─── Playlist Router ───────────────────────────────────────────────────────
playlist_router = APIRouter(prefix="/api/playlists", tags=["Playlists"])

@playlist_router.get("")
async def get_playlists(user = Depends(get_current_user)):
    """List all playlists"""
    return {"status": "success", "playlists": list_playlists()}

@playlist_router.post("/create")
async def create_new_playlist(
    playlist: PlaylistCreate,
    user = Depends(get_current_user)
):
    """Create a new playlist"""
    return create_playlist(playlist.name, playlist.type, playlist.delay)

@playlist_router.put("/{playlist_id}")
async def update_existing_playlist(
    playlist_id: str,
    playlist: PlaylistUpdate,
    user = Depends(get_current_user)
):
    """Update playlist settings"""
    return update_playlist(playlist_id, playlist.name, playlist.delay)

@playlist_router.delete("/{playlist_id}")
async def delete_existing_playlist(
    playlist_id: str,
    user = Depends(get_current_user)
):
    """Delete a playlist"""
    return delete_playlist(playlist_id)

@playlist_router.get("/{playlist_id}/images")
async def get_images(playlist_id: str, user = Depends(get_current_user)):
    """Get images in a playlist"""
    return get_playlist_images_list(playlist_id)

@playlist_router.get("/{playlist_id}/videos")
async def get_videos(playlist_id: str, user = Depends(get_current_user)):
    """Get videos in a playlist"""
    return get_playlist_videos_list(playlist_id)

@playlist_router.post("/{playlist_id}/upload")
async def upload_content(
    playlist_id: str,
    request: Request,
    user = Depends(get_current_user)
):
    """Upload image or video to playlist"""
    # Check if playlist exists
    if playlist_id not in playlists_db["playlists"]:
        raise HTTPException(status_code=404, detail="Playlist not found")
    
    # Check for existing videos in video playlists
    playlist_type = playlists_db["playlists"][playlist_id].get("type", "image")
    if playlist_type == "video":
        existing_videos = get_playlist_videos(playlist_id)
        if existing_videos:
            raise HTTPException(
                status_code=400,
                detail="Playlist already contains a video. Delete the existing video first."
            )
    
    # Get content type and length
    content_type = request.headers.get('content-type', '')
    content_length = int(request.headers.get('content-length', 0))
    
    if 'multipart/form-data' not in content_type:
        raise HTTPException(status_code=400, detail="Content must be multipart/form-data")
    
    # Large file handling (>10MB)
    if content_length > 10 * 1024 * 1024:
        upload_id = str(uuid.uuid4())[:8]
        playlist_dir = VIDEOS_DIR / playlist_id
        playlist_dir.mkdir(parents=True, exist_ok=True, mode=0o755)
        temp_dest = playlist_dir / f".uploading_{upload_id}.tmp"
        
        try:
            # Stream upload
            file_info = parse_multipart_form_data_streaming(
                content_type,
                request.stream(),
                content_length,
                temp_dest,
                upload_id
            )
            
            if file_info and file_info.get('filename'):
                filename = file_info['filename']
                file_ext = Path(filename).suffix.lower()
                
                valid_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm'}
                if file_ext not in valid_extensions:
                    temp_dest.unlink()
                    raise HTTPException(status_code=400, detail="Invalid video file type")
                
                # Rename to final path
                final_path = playlist_dir / filename
                counter = 1
                while final_path.exists():
                    name_stem = Path(filename).stem
                    final_path = playlist_dir / f"{name_stem}_{counter}{file_ext}"
                    counter += 1
                
                temp_dest.rename(final_path)
                final_path.chmod(0o644)
                
                # Update database
                videos = get_playlist_videos(playlist_id)
                playlists_db["playlists"][playlist_id]["video_count"] = len(videos)
                save_playlists_db()
                
                # Start background downscaling
                thread = threading.Thread(
                    target=downscale_video_to_1080p,
                    args=(final_path, upload_id),
                    daemon=True
                )
                thread.start()
                
                return {
                    "status": "success",
                    "message": "Video uploaded successfully",
                    "filename": final_path.name,
                    "upload_id": upload_id,
                    "downscale_id": upload_id
                }
            else:
                if temp_dest.exists():
                    temp_dest.unlink()
                raise HTTPException(status_code=400, detail="No valid file uploaded")
                
        except HTTPException:
            raise
        except Exception as e:
            if temp_dest.exists():
                temp_dest.unlink()
            raise HTTPException(status_code=500, detail=str(e))
    
    else:
        # Small file (<10MB)
        body = await request.body()
        expected_field = "video" if playlist_type == "video" else "image"
        file_info = parse_multipart_form_data(content_type, body, expected_field)
        
        if not file_info or not file_info.get('filename') or not file_info.get('data'):
            raise HTTPException(status_code=400, detail="No valid file uploaded")
        
        filename = file_info['filename']
        file_ext = Path(filename).suffix.lower()
        video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm'}
        
        if file_ext in video_extensions:
            playlist_dir = VIDEOS_DIR / playlist_id
            playlist_dir.mkdir(parents=True, exist_ok=True, mode=0o755)
            
            final_path = playlist_dir / filename
            counter = 1
            while final_path.exists():
                name_stem = Path(filename).stem
                final_path = playlist_dir / f"{name_stem}_{counter}{file_ext}"
                counter += 1
            
            final_path.write_bytes(file_info['data'])
            final_path.chmod(0o644)
            
            downscale_id = str(uuid.uuid4())[:8]
            
            # Update database
            videos = get_playlist_videos(playlist_id)
            playlists_db["playlists"][playlist_id]["video_count"] = len(videos)
            save_playlists_db()
            
            # Background downscaling
            thread = threading.Thread(
                target=downscale_video_to_1080p,
                args=(final_path, downscale_id),
                daemon=True
            )
            thread.start()
            
            return {
                "status": "success",
                "message": "Video uploaded successfully",
                "filename": final_path.name,
                "downscale_id": downscale_id
            }
        else:
            return upload_image(playlist_id, file_info['data'], filename)

@playlist_router.post("/{playlist_id}/download")
async def download_video(
    playlist_id: str,
    video: VideoDownload,
    user = Depends(get_current_user)
):
    """Download video from YouTube"""
    if not video.url:
        raise HTTPException(status_code=400, detail="No URL provided")
    
    existing_videos = get_playlist_videos(playlist_id)
    if existing_videos:
        raise HTTPException(
            status_code=400,
            detail="Playlist already contains a video. Please remove it first."
        )
    
    download_id = str(uuid.uuid4())[:8]
    thread = threading.Thread(
        target=download_youtube_video,
        args=(playlist_id, video.url, download_id),
        daemon=True
    )
    thread.start()
    
    return {
        "status": "started",
        "download_id": download_id,
        "message": "Download started"
    }

@playlist_router.delete("/{playlist_id}/images/{filename}")
async def delete_playlist_image(
    playlist_id: str,
    filename: str,
    user = Depends(get_current_user)
):
    """Delete an image from playlist"""
    return delete_image(playlist_id, filename)

@playlist_router.delete("/{playlist_id}/videos/{filename}")
async def delete_playlist_video(
    playlist_id: str,
    filename: str,
    user = Depends(get_current_user)
):
    """Delete a video from playlist"""
    return delete_video(playlist_id, filename)

@playlist_router.post("/{playlist_id}/images/{filename}/skip")
async def skip_playlist_image(
    playlist_id: str,
    filename: str,
    user = Depends(get_current_user)
):
    """Skip an image in playlist"""
    return skip_image(playlist_id, filename)

@playlist_router.delete("/{playlist_id}/images/{filename}/skip")
async def unskip_playlist_image(
    playlist_id: str,
    filename: str,
    user = Depends(get_current_user)
):
    """Unskip an image in playlist"""
    return unskip_image(playlist_id, filename)

# ─── Playback Router ──────────────────────────────────────────────────────
playback_router = APIRouter(prefix="/api", tags=["Playback"])

@playback_router.get("/status")
async def playback_status(user = Depends(get_current_user)):
    """Get current playback status"""
    return get_status()

@playback_router.get("/start")
async def start_playback(
    playlist: Optional[str] = None,
    user = Depends(get_current_user)
):
    """Start slideshow or video playback"""
    playlist_id = playlist
    
    if playlist_id and playlist_id in playlists_db["playlists"]:
        plist_type = playlists_db["playlists"][playlist_id].get("type", "image")
        if plist_type == "video":
            return start_video_playback(playlist_id)
        else:
            return start_slideshow(playlist_id)
    else:
        return start_slideshow(playlist_id)

@playback_router.get("/stop")
async def stop_playback(user = Depends(get_current_user)):
    """Stop all playback"""
    video_stopped = False
    slideshow_stopped = False
    
    if video_process is not None:
        response = stop_video_playback()
        video_stopped = True
    
    if slideshow_process is not None:
        response = stop_slideshow()
        slideshow_stopped = True
    
    if not video_stopped and not slideshow_stopped:
        response = stop_slideshow()
    
    if video_stopped or slideshow_stopped:
        return {
            "status": "stopped",
            "message": "Playback stopped",
            "video_stopped": video_stopped,
            "slideshow_stopped": slideshow_stopped
        }
    return response

@playback_router.get("/clear")
async def clear_display(user = Depends(get_current_user)):
    """Clear the framebuffer"""
    clear_framebuffer()
    return {"status": "success", "message": "Framebuffer cleared"}

# ─── Progress Tracking Router ─────────────────────────────────────────────
progress_router = APIRouter(prefix="/api", tags=["Progress"])

@progress_router.get("/download/{download_id}")
async def get_download_status(
    download_id: str,
    user = Depends(get_current_user)
):
    """Get download progress status"""
    if download_id in download_status:
        return download_status[download_id]
    raise HTTPException(status_code=404, detail="Download not found")

@progress_router.get("/downscale/{downscale_id}")
async def get_downscale_status(
    downscale_id: str,
    user = Depends(get_current_user)
):
    """Get downscale progress status"""
    if downscale_id in downscale_status:
        return downscale_status[downscale_id]
    raise HTTPException(status_code=404, detail="Downscale not found")

# ─── Idle Screen Router ───────────────────────────────────────────────────
idle_router = APIRouter(prefix="/api/idle-config", tags=["Idle Screen"])

@idle_router.get("")
async def get_idle_configuration(user = Depends(get_current_user)):
    """Get idle screen configuration"""
    return get_idle_config()

@idle_router.post("")
async def save_idle_configuration(
    config_data: IdleConfigUpdate,
    user = Depends(get_current_user)
):
    """Save idle screen configuration"""
    cfg = save_idle_config(config_data.dict())
    stop_idle_screen()
    if cfg.get("enabled") and cfg.get("image_path"):
        start_idle_screen()
    return cfg

@idle_router.post("/upload")
async def upload_idle_background(
    file: UploadFile = File(...),
    user = Depends(get_current_user)
):
    """Upload idle screen background image"""
    if not file:
        raise HTTPException(status_code=400, detail="No file provided")
    
    ext = Path(file.filename).suffix.lower()
    dest = IDLE_DIR / f"idle_bg{ext}"
    
    contents = await file.read()
    dest.write_bytes(contents)
    
    return {"status": "success", "image_path": str(dest)}

# ─── Scheduler Router ─────────────────────────────────────────────────────
scheduler_router = APIRouter(prefix="/api/schedules", tags=["Scheduler"])

@scheduler_router.get("")
async def get_schedules(user = Depends(get_current_user)):
    """List all schedules"""
    return list_schedules()

@scheduler_router.get("/{schedule_id}")
async def get_schedule_by_id(
    schedule_id: str,
    user = Depends(get_current_user)
):
    """Get a specific schedule"""
    s = get_schedule(schedule_id)
    if not s:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return s

@scheduler_router.post("")
async def create_new_schedule(
    schedule: ScheduleCreate,
    user = Depends(get_current_user)
):
    """Create a new schedule"""
    return create_schedule(
        schedule.name,
        schedule.playlist_id,
        schedule.cron,
        schedule.enabled
    )

@scheduler_router.put("/{schedule_id}")
async def update_existing_schedule(
    schedule_id: str,
    schedule: ScheduleUpdate,
    user = Depends(get_current_user)
):
    """Update a schedule"""
    result = update_schedule(schedule_id, schedule.dict(exclude_unset=True))
    if not result:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return result

@scheduler_router.delete("/{schedule_id}")
async def delete_existing_schedule(
    schedule_id: str,
    user = Depends(get_current_user)
):
    """Delete a schedule"""
    ok = delete_schedule(schedule_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return {"status": "ok"}

# ─── Health Check Router ──────────────────────────────────────────────────
health_router = APIRouter(prefix="/api", tags=["Health"])

@health_router.get("/health")
async def health_check():
    """API health check"""
    return {"status": "ok"}

# ═══════════════════════════════════════════════════════════════════════════
# Register Routers
# ═══════════════════════════════════════════════════════════════════════════

app.include_router(auth_router)
app.include_router(playlist_router)
app.include_router(playback_router)
app.include_router(progress_router)
app.include_router(idle_router)
app.include_router(scheduler_router)
app.include_router(health_router)

# ═══════════════════════════════════════════════════════════════════════════
# Static Files & Data Serving
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/", response_class=FileResponse)
@app.get("/index.html", response_class=FileResponse)
async def serve_index(session_token: Optional[str] = Cookie(None)):
    """Serve main application page"""
    user_info = validate_session(session_token)
    if not user_info:
        return RedirectResponse(url="/login.html")
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/login.html", response_class=FileResponse)
@app.get("/login", response_class=FileResponse)
async def serve_login():
    """Serve login page"""
    return FileResponse(STATIC_DIR / "login.html")

# Mount static files
app.mount("/frontend", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Serve data files (with authentication)
@app.get("/data/idle/{filename}")
async def serve_idle_file(
    filename: str,
    user = Depends(get_current_user)
):
    """Serve idle screen images"""
    file_path = IDLE_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)

@app.get("/data/playlists/{playlist_id}/{filename}")
async def serve_playlist_file(
    playlist_id: str,
    filename: str,
    user = Depends(get_current_user)
):
    """Serve playlist images/videos"""
    file_path = PLAYLISTS_DIR / playlist_id / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)

# ═══════════════════════════════════════════════════════════════════════════
# Application Lifecycle
# ═══════════════════════════════════════════════════════════════════════════

@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    setup_logging()
    ensure_directories()
    load_config()
    load_playlists_db()
    
    # Load idle config
    cfg = get_idle_config()
    if cfg.get("enabled") and cfg.get("image_path"):
        start_idle_screen()
    
    # Start scheduler
    load_schedules_db()
    start_scheduler()
    
    logger.info("=== Pi Display Manager FastAPI Started ===")
    logger.info("API Documentation: http://localhost:%d/docs", config.get("api_port", 8000))

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down Pi Display Manager...")
    stop_scheduler()
    stop_slideshow()
    logger.info("Pi Display Manager stopped")

# ═══════════════════════════════════════════════════════════════════════════
# Main Entry Point
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    port = config.get("api_port", 8000) if config else 8000
    
    uvicorn.run(
        "controller_fastapi:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info"
    )
