"""
Minimal cron scheduler using a background thread.
Checks every 60 seconds whether any active schedule matches the current time.
Supports standard 5-field cron syntax with *, */n, n-m, and comma lists.
"""

import logging
import threading
import time
from datetime import datetime

logger = logging.getLogger(__name__)


class SimpleScheduler:
    def __init__(self):
        self._jobs: dict[int, tuple] = {}  # id → (cron_expr, playlist_id, is_active)
        self._lock = threading.Lock()

    def start(self):
        t = threading.Thread(target=self._run, daemon=True, name="scheduler")
        t.start()

    def load_from_db(self):
        import database
        conn = database.get_db()
        rows = conn.execute(
            "SELECT id, cron_expression, playlist_id, is_active FROM schedules"
        ).fetchall()
        conn.close()
        with self._lock:
            for r in rows:
                self._jobs[r["id"]] = (r["cron_expression"], r["playlist_id"], bool(r["is_active"]))
        logger.info("Loaded %d schedule(s)", len(rows))

    def refresh(self, job_id: int, cron_expr: str, playlist_id: int, is_active: bool):
        with self._lock:
            self._jobs[job_id] = (cron_expr, playlist_id, is_active)

    def remove(self, job_id: int):
        with self._lock:
            self._jobs.pop(job_id, None)

    # ------------------------------------------------------------------

    def _run(self):
        # Align to the start of the next minute before entering the loop
        time.sleep(60 - datetime.now().second)
        while True:
            now = datetime.now()
            with self._lock:
                jobs = list(self._jobs.items())
            for job_id, (cron_expr, playlist_id, is_active) in jobs:
                if is_active and self._matches(cron_expr, now):
                    self._fire(playlist_id)
            time.sleep(60)

    def _fire(self, playlist_id: int):
        import database
        from player import player
        conn = database.get_db()
        try:
            rows = conn.execute("""
                SELECT mf.file_path, mf.file_type, pi.duration
                FROM playlist_items pi
                JOIN media_files mf ON mf.id = pi.media_file_id
                WHERE pi.playlist_id = ?
                ORDER BY pi.sort_order
            """, (playlist_id,)).fetchall()
            if rows:
                items = [{"path": r["file_path"], "type": r["file_type"], "duration": r["duration"]} for r in rows]
                logger.info("Scheduler firing playlist %d (%d items)", playlist_id, len(items))
                player.play_playlist(items)
        finally:
            conn.close()

    @staticmethod
    def _matches(expr: str, dt: datetime) -> bool:
        parts = expr.strip().split()
        if len(parts) != 5:
            return False
        fields = [
            (parts[0], dt.minute),
            (parts[1], dt.hour),
            (parts[2], dt.day),
            (parts[3], dt.month),
            (parts[4], dt.weekday()),
        ]
        return all(SimpleScheduler._field_match(f, v) for f, v in fields)

    @staticmethod
    def _field_match(field: str, val: int) -> bool:
        if field == "*":
            return True
        if "," in field:
            return val in [int(x) for x in field.split(",")]
        if "/" in field:
            _, step = field.split("/")
            return val % int(step) == 0
        if "-" in field:
            lo, hi = field.split("-")
            return int(lo) <= val <= int(hi)
        return val == int(field)


scheduler = SimpleScheduler()
