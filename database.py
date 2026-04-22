import sqlite3

DB_PATH = "pi_display.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS media_files (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            filename     TEXT NOT NULL,
            original_name TEXT NOT NULL,
            file_type    TEXT NOT NULL,
            file_path    TEXT NOT NULL,
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS playlists (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS playlist_items (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            playlist_id   INTEGER NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
            media_file_id INTEGER NOT NULL REFERENCES media_files(id) ON DELETE CASCADE,
            sort_order    INTEGER NOT NULL,
            duration      REAL DEFAULT 10.0
        );

        CREATE TABLE IF NOT EXISTS schedules (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT NOT NULL,
            playlist_id     INTEGER NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
            cron_expression TEXT NOT NULL,
            is_active       INTEGER DEFAULT 1,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()
