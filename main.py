import logging
import shutil
import uuid
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
import yt_dlp

import database
from player import player
from scheduler import scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s — %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder="frontend/static", static_url_path="/static")
app.url_map.strict_slashes = False

MEDIA_DIR = Path("media")
MEDIA_DIR.mkdir(exist_ok=True)

ALLOWED_TYPES: dict[str, set[str]] = {
    "image": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"},
    "video": {".mp4", ".avi", ".mkv", ".mov", ".webm"},
}


def _file_type(filename: str):
    ext = Path(filename).suffix.lower()
    for ftype, exts in ALLOWED_TYPES.items():
        if ext in exts:
            return ftype
    return None


# ── UI ───────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("frontend", "index.html")


# ── Files ─────────────────────────────────────────────────────────────────────

@app.route("/api/files/")
def list_files():
    conn = database.get_db()
    rows = conn.execute("SELECT * FROM media_files ORDER BY created_at DESC").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/files/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    f = request.files["file"]
    ftype = _file_type(f.filename or "")
    if not ftype:
        return jsonify({"error": f"Unsupported type: {f.filename}"}), 400

    unique_name = str(uuid.uuid4()) + Path(f.filename).suffix.lower()
    file_path = MEDIA_DIR / unique_name
    f.save(str(file_path))

    conn = database.get_db()
    cur = conn.execute(
        "INSERT INTO media_files (filename, original_name, file_type, file_path) VALUES (?,?,?,?)",
        (unique_name, f.filename, ftype, str(file_path)),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM media_files WHERE id=?", (cur.lastrowid,)).fetchone()
    conn.close()
    return jsonify(dict(row))


@app.route("/api/files/download-youtube", methods=["POST"])
def download_youtube():
    data = request.json or {}
    url = data.get("url", "").strip()
    
    if not url:
        return jsonify({"error": "No URL provided"}), 400
    
    try:
        # Generate unique filename
        video_id = str(uuid.uuid4())
        output_template = str(MEDIA_DIR / f"{video_id}.%(ext)s")
        
        # yt-dlp options for 720p download
        ydl_opts = {
            'format': 'bestvideo[height<=720]+bestaudio/best[height<=720]',
            'outtmpl': output_template,
            'merge_output_format': 'mp4',
            'quiet': False,
            'no_warnings': False,
        }
        
        # Download the video
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_title = info.get('title', 'Unknown')
            final_filename = f"{video_id}.mp4"
            file_path = MEDIA_DIR / final_filename
        
        # Add to database
        conn = database.get_db()
        cur = conn.execute(
            "INSERT INTO media_files (filename, original_name, file_type, file_path) VALUES (?,?,?,?)",
            (final_filename, video_title, "video", str(file_path)),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM media_files WHERE id=?", (cur.lastrowid,)).fetchone()
        conn.close()
        
        return jsonify(dict(row))
        
    except Exception as e:
        logger.error(f"YouTube download error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/files/<int:file_id>", methods=["DELETE"])
def delete_file(file_id):
    conn = database.get_db()
    row = conn.execute("SELECT * FROM media_files WHERE id=?", (file_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Not found"}), 404
    Path(row["file_path"]).unlink(missing_ok=True)
    conn.execute("DELETE FROM media_files WHERE id=?", (file_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "deleted"})


# ── Playlists ─────────────────────────────────────────────────────────────────

@app.route("/api/playlists/")
def list_playlists():
    conn = database.get_db()
    rows = conn.execute("SELECT id, name FROM playlists ORDER BY created_at DESC").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/playlists/", methods=["POST"])
def create_playlist():
    data = request.json or {}
    conn = database.get_db()
    cur = conn.execute("INSERT INTO playlists (name) VALUES (?)", (data.get("name", "Untitled"),))
    pl_id = cur.lastrowid
    _save_playlist_items(conn, pl_id, data.get("items", []))
    conn.commit()
    result = _get_playlist_detail(conn, pl_id)
    conn.close()
    return jsonify(result)


@app.route("/api/playlists/<int:pl_id>")
def get_playlist(pl_id):
    conn = database.get_db()
    result = _get_playlist_detail(conn, pl_id)
    conn.close()
    if not result:
        return jsonify({"error": "Not found"}), 404
    return jsonify(result)


@app.route("/api/playlists/<int:pl_id>", methods=["PUT"])
def update_playlist(pl_id):
    data = request.json or {}
    conn = database.get_db()
    conn.execute("UPDATE playlists SET name=? WHERE id=?", (data.get("name", "Untitled"), pl_id))
    conn.execute("DELETE FROM playlist_items WHERE playlist_id=?", (pl_id,))
    _save_playlist_items(conn, pl_id, data.get("items", []))
    conn.commit()
    result = _get_playlist_detail(conn, pl_id)
    conn.close()
    return jsonify(result)


@app.route("/api/playlists/<int:pl_id>", methods=["DELETE"])
def delete_playlist(pl_id):
    conn = database.get_db()
    conn.execute("DELETE FROM playlists WHERE id=?", (pl_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "deleted"})


def _save_playlist_items(conn, pl_id, items):
    for item in items:
        conn.execute(
            "INSERT INTO playlist_items (playlist_id, media_file_id, sort_order, duration) VALUES (?,?,?,?)",
            (pl_id, item["media_file_id"], item.get("order", 0), item.get("duration", 10.0)),
        )


def _get_playlist_detail(conn, pl_id):
    pl = conn.execute("SELECT * FROM playlists WHERE id=?", (pl_id,)).fetchone()
    if not pl:
        return None
    items = conn.execute("""
        SELECT pi.id, pi.playlist_id, pi.media_file_id,
               pi.sort_order AS sort_order, pi.duration,
               mf.original_name, mf.file_type
        FROM playlist_items pi
        JOIN media_files mf ON mf.id = pi.media_file_id
        WHERE pi.playlist_id = ?
        ORDER BY pi.sort_order
    """, (pl_id,)).fetchall()
    result = dict(pl)
    result["items"] = [dict(i) for i in items]
    return result


# ── Schedules ─────────────────────────────────────────────────────────────────

@app.route("/api/schedules/")
def list_schedules():
    conn = database.get_db()
    rows = conn.execute("SELECT * FROM schedules ORDER BY created_at DESC").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/schedules/", methods=["POST"])
def create_schedule():
    data = request.json or {}
    conn = database.get_db()
    cur = conn.execute(
        "INSERT INTO schedules (name, playlist_id, cron_expression, is_active) VALUES (?,?,?,?)",
        (data["name"], data["playlist_id"], data["cron_expression"], 1 if data.get("is_active", True) else 0),
    )
    sch_id = cur.lastrowid
    conn.commit()
    row = conn.execute("SELECT * FROM schedules WHERE id=?", (sch_id,)).fetchone()
    conn.close()
    scheduler.refresh(sch_id, data["cron_expression"], data["playlist_id"], bool(data.get("is_active", True)))
    return jsonify(dict(row))


@app.route("/api/schedules/<int:sch_id>", methods=["PUT"])
def update_schedule(sch_id):
    data = request.json or {}
    is_active = 1 if data.get("is_active", True) else 0
    conn = database.get_db()
    conn.execute(
        "UPDATE schedules SET name=?, playlist_id=?, cron_expression=?, is_active=? WHERE id=?",
        (data["name"], data["playlist_id"], data["cron_expression"], is_active, sch_id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM schedules WHERE id=?", (sch_id,)).fetchone()
    conn.close()
    scheduler.refresh(sch_id, data["cron_expression"], data["playlist_id"], bool(is_active))
    return jsonify(dict(row))


@app.route("/api/schedules/<int:sch_id>", methods=["DELETE"])
def delete_schedule(sch_id):
    conn = database.get_db()
    conn.execute("DELETE FROM schedules WHERE id=?", (sch_id,))
    conn.commit()
    conn.close()
    scheduler.remove(sch_id)
    return jsonify({"status": "deleted"})


# ── Control ───────────────────────────────────────────────────────────────────

@app.route("/api/control/play", methods=["POST"])
def play():
    data = request.json or {}
    conn = database.get_db()
    try:
        if "playlist_id" in data:
            rows = conn.execute("""
                SELECT mf.file_path, mf.file_type, pi.duration
                FROM playlist_items pi
                JOIN media_files mf ON mf.id = pi.media_file_id
                WHERE pi.playlist_id = ?
                ORDER BY pi.sort_order
            """, (data["playlist_id"],)).fetchall()
            if not rows:
                return jsonify({"error": "Playlist is empty"}), 400
            items = [{"path": r["file_path"], "type": r["file_type"], "duration": r["duration"]} for r in rows]
            player.play_playlist(items)

        elif "file_id" in data:
            row = conn.execute("SELECT * FROM media_files WHERE id=?", (data["file_id"],)).fetchone()
            if not row:
                return jsonify({"error": "File not found"}), 404
            player.play_file(row["file_path"], row["file_type"])

        else:
            return jsonify({"error": "Provide playlist_id or file_id"}), 400
    finally:
        conn.close()
    return jsonify({"status": "playing"})


@app.route("/api/control/pause", methods=["POST"])
def pause():
    player.pause()
    return jsonify({"status": "paused"})


@app.route("/api/control/resume", methods=["POST"])
def resume():
    player.resume()
    return jsonify({"status": "resumed"})


@app.route("/api/control/stop", methods=["POST"])
def stop():
    player.stop()
    return jsonify({"status": "stopped"})


@app.route("/api/control/next", methods=["POST"])
def next_item():
    player.next()
    return jsonify({"status": "next"})


@app.route("/api/control/status")
def status():
    return jsonify(player.get_status())


# ── Startup ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    database.init_db()
    scheduler.load_from_db()
    scheduler.start()
    app.run(host="0.0.0.0", port=8000, threaded=True)
