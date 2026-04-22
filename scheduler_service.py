"""
APScheduler integration — loads Schedule rows from DB and fires playlists at cron times.
Schedules are hot-reloadable: calling refresh_schedule() adds/removes jobs at runtime.
"""

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone="UTC")


def _play_scheduled_playlist(playlist_id: int):
    """Called by APScheduler — runs in scheduler thread."""
    from database import SessionLocal
    from models import Playlist
    from player import player

    db = SessionLocal()
    try:
        playlist = db.query(Playlist).filter(Playlist.id == playlist_id).first()
        if not playlist or not playlist.items:
            logger.warning("Scheduled playlist %d not found or empty", playlist_id)
            return

        items = [
            {
                "path": item.media_file.file_path,
                "type": item.media_file.file_type,
                "duration": item.duration,
            }
            for item in playlist.items
        ]
        logger.info("Scheduler firing playlist %d (%s)", playlist_id, playlist.name)
        player.play_playlist(items)
    finally:
        db.close()


def load_schedules():
    """Load all active schedules from DB into APScheduler on startup."""
    from database import SessionLocal
    from models import Schedule

    db = SessionLocal()
    try:
        schedules = db.query(Schedule).filter(Schedule.is_active == True).all()
        for s in schedules:
            _add_job(s.id, s.cron_expression, s.playlist_id)
        logger.info("Loaded %d schedule(s) from database", len(schedules))
    finally:
        db.close()


def refresh_schedule(schedule_id: int, cron_expression: str, playlist_id: int, is_active: bool):
    """Add, update, or remove a single schedule job at runtime."""
    job_id = f"schedule_{schedule_id}"

    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    if is_active:
        _add_job(schedule_id, cron_expression, playlist_id)


def remove_schedule(schedule_id: int):
    """Remove a schedule job by ID."""
    job_id = f"schedule_{schedule_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)


def _add_job(schedule_id: int, cron_expression: str, playlist_id: int):
    job_id = f"schedule_{schedule_id}"
    try:
        scheduler.add_job(
            _play_scheduled_playlist,
            CronTrigger.from_crontab(cron_expression),
            args=[playlist_id],
            id=job_id,
            replace_existing=True,
        )
        logger.info("Scheduled job %s: %s → playlist %d", job_id, cron_expression, playlist_id)
    except Exception as e:
        logger.error("Failed to add schedule job %s: %s", job_id, e)


def start_scheduler():
    load_schedules()
    scheduler.start()
    logger.info("APScheduler started")
