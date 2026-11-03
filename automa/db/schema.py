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

        # =====================================================================
        # AI CONTENT INTELLIGENCE & MULTI-AGENT PIPELINE TABLES
        # =====================================================================

        # Agent A: Discovered Research & News Items
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS discovered_items (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                url TEXT UNIQUE NOT NULL,
                source_type TEXT NOT NULL,
                primary_category TEXT,
                authors TEXT,
                organization TEXT,
                abstract TEXT,
                raw_metadata_json TEXT,
                published_at TEXT,
                discovered_at TEXT NOT NULL,
                status TEXT DEFAULT 'DISCOVERED'
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_disc_source ON discovered_items(source_type);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_disc_status ON discovered_items(status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_disc_published ON discovered_items(published_at);")

        # Agent B: Source Verification Records
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS verified_sources (
                id TEXT PRIMARY KEY,
                discovered_item_id TEXT NOT NULL,
                primary_url TEXT NOT NULL,
                is_verified INTEGER DEFAULT 0,
                pub_type TEXT NOT NULL,
                confirmed_facts_json TEXT,
                caveats_json TEXT,
                evidence_snippets_json TEXT,
                requires_human_review INTEGER DEFAULT 0,
                review_reason TEXT,
                verified_at TEXT NOT NULL,
                FOREIGN KEY (discovered_item_id) REFERENCES discovered_items(id) ON DELETE CASCADE
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_verified_item ON verified_sources(discovered_item_id);")

        # Agent C: Topic Rankings & Trend Scoring
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS topic_rankings (
                id TEXT PRIMARY KEY,
                discovered_item_id TEXT NOT NULL,
                total_score REAL NOT NULL,
                score_recency REAL NOT NULL,
                score_usefulness REAL NOT NULL,
                score_significance REAL NOT NULL,
                score_accessibility REAL NOT NULL,
                score_credibility REAL NOT NULL,
                score_novelty REAL NOT NULL,
                signals_json TEXT,
                notes TEXT,
                ranked_at TEXT NOT NULL,
                FOREIGN KEY (discovered_item_id) REFERENCES discovered_items(id) ON DELETE CASCADE
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rank_score ON topic_rankings(total_score DESC);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rank_item ON topic_rankings(discovered_item_id);")

        # Agent D: Research Simplification (7-Question Framework)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS research_distillations (
                id TEXT PRIMARY KEY,
                discovered_item_id TEXT NOT NULL,
                problem TEXT NOT NULL,
                why_it_matters TEXT NOT NULL,
                core_idea TEXT NOT NULL,
                what_is_new TEXT NOT NULL,
                results_and_conditions TEXT NOT NULL,
                limitations TEXT NOT NULL,
                code_and_paper_links_json TEXT,
                distilled_at TEXT NOT NULL,
                FOREIGN KEY (discovered_item_id) REFERENCES discovered_items(id) ON DELETE CASCADE
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_distill_item ON research_distillations(discovered_item_id);")

        # Agent E: Content Strategy Angles
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS content_angles (
                id TEXT PRIMARY KEY,
                discovered_item_id TEXT NOT NULL,
                candidate_angles_json TEXT NOT NULL,
                selected_angle TEXT NOT NULL,
                target_platform TEXT NOT NULL,
                strategy_reasoning TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (discovered_item_id) REFERENCES discovered_items(id) ON DELETE CASCADE
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_angles_item ON content_angles(discovered_item_id);")

        conn.commit()
