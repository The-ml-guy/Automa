"""
SQLite Schema and Connection Manager for Automa.
Configures WAL mode, busy timeout, and relational tables.
"""

from __future__ import annotations
import sqlite3
from pathlib import Path
from automa.config import DATA_DIR

DB_PATH = DATA_DIR / "automa.db"


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Creates a hardened connection to SQLite with WAL mode enabled."""
    conn = sqlite3.connect(str(db_path), timeout=10.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: Path = DB_PATH) -> None:
    """Initializes tables, indexes, and constraints."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        # Posts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id TEXT PRIMARY KEY,
                platform TEXT NOT NULL,
                status TEXT NOT NULL,
                topic TEXT NOT NULL,
                content TEXT NOT NULL,
                thread_items_json TEXT,
                media_urls_json TEXT,
                media_prompt TEXT,
                quality_score INTEGER DEFAULT 0,
                quality_report_json TEXT,
                revision_count INTEGER DEFAULT 0,
                fingerprint TEXT NOT NULL,
                idempotency_key TEXT UNIQUE NOT NULL,
                scheduled_at TEXT,
                published_at TEXT,
                external_post_id TEXT,
                retry_count INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 3,
                next_retry_at TEXT,
                last_error TEXT,
                requires_manual_review INTEGER DEFAULT 0,
                manual_review_reason TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)

        # Indexes for fast querying
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_posts_status ON posts(status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_posts_platform ON posts(platform);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_posts_scheduled_at ON posts(scheduled_at);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_posts_fingerprint ON posts(fingerprint);")

        # Content fingerprints table for strict deduplication
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS content_fingerprints (
                fingerprint TEXT PRIMARY KEY,
                post_id TEXT NOT NULL,
                platform TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE
            );
        """)

        # Generation runs history
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS generation_runs (
                id TEXT PRIMARY KEY,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                status TEXT NOT NULL,
                topic_chosen TEXT,
                reason TEXT,
                posts_generated INTEGER DEFAULT 0,
                posts_scheduled INTEGER DEFAULT 0,
                details_json TEXT
            );
        """)

        # Audit logs for all state transitions and critical events
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                post_id TEXT,
                details TEXT NOT NULL
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp);")
        conn.commit()
