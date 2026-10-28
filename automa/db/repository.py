"""
Repository pattern for SQLite persistence in Automa.
Provides atomic transactions, state transitions, deduplication, and audit logging.
"""

from __future__ import annotations
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from automa.db.schema import get_connection, DB_PATH


class PostRecord(BaseModel):
    id: str
    platform: str
    status: str
    topic: str
    content: str
    thread_items: List[str] = Field(default_factory=list)
    media_urls: List[str] = Field(default_factory=list)
    media_prompt: Optional[str] = None
    quality_score: int = 0
    quality_report: Dict[str, Any] = Field(default_factory=dict)
    revision_count: int = 0
    fingerprint: str
    idempotency_key: str
    scheduled_at: Optional[str] = None
    published_at: Optional[str] = None
    external_post_id: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    next_retry_at: Optional[str] = None
    last_error: Optional[str] = None
    requires_manual_review: bool = False
    manual_review_reason: Optional[str] = None
    created_at: str
    updated_at: str


class PostRepository:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path

    def _row_to_record(self, row: sqlite3.Row) -> PostRecord:
        return PostRecord(
            id=row["id"],
            platform=row["platform"],
            status=row["status"],
            topic=row["topic"],
            content=row["content"],
            thread_items=json.loads(row["thread_items_json"]) if row["thread_items_json"] else [],
            media_urls=json.loads(row["media_urls_json"]) if row["media_urls_json"] else [],
            media_prompt=row["media_prompt"],
            quality_score=row["quality_score"],
            quality_report=json.loads(row["quality_report_json"]) if row["quality_report_json"] else {},
            revision_count=row["revision_count"],
            fingerprint=row["fingerprint"],
            idempotency_key=row["idempotency_key"],
            scheduled_at=row["scheduled_at"],
            published_at=row["published_at"],
            external_post_id=row["external_post_id"],
            retry_count=row["retry_count"],
            max_retries=row["max_retries"],
            next_retry_at=row["next_retry_at"],
            last_error=row["last_error"],
            requires_manual_review=bool(row["requires_manual_review"]),
            manual_review_reason=row["manual_review_reason"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def save_post(self, post: PostRecord) -> None:
        """Insert or update a post record atomically."""
        now = datetime.now(timezone.utc).isoformat()
        with get_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO posts (
                    id, platform, status, topic, content, thread_items_json,
                    media_urls_json, media_prompt, quality_score, quality_report_json,
                    revision_count, fingerprint, idempotency_key, scheduled_at,
                    published_at, external_post_id, retry_count, max_retries,
                    next_retry_at, last_error, requires_manual_review,
                    manual_review_reason, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status = excluded.status,
                    topic = excluded.topic,
                    content = excluded.content,
                    thread_items_json = excluded.thread_items_json,
                    media_urls_json = excluded.media_urls_json,
                    media_prompt = excluded.media_prompt,
                    quality_score = excluded.quality_score,
                    quality_report_json = excluded.quality_report_json,
                    revision_count = excluded.revision_count,
                    fingerprint = excluded.fingerprint,
                    scheduled_at = excluded.scheduled_at,
                    published_at = excluded.published_at,
                    external_post_id = excluded.external_post_id,
                    retry_count = excluded.retry_count,
                    max_retries = excluded.max_retries,
                    next_retry_at = excluded.next_retry_at,
                    last_error = excluded.last_error,
                    requires_manual_review = excluded.requires_manual_review,
                    manual_review_reason = excluded.manual_review_reason,
                    updated_at = excluded.updated_at;
            """, (
                post.id,
                post.platform,
                post.status,
                post.topic,
                post.content,
                json.dumps(post.thread_items),
                json.dumps(post.media_urls),
                post.media_prompt,
                post.quality_score,
                json.dumps(post.quality_report),
                post.revision_count,
                post.fingerprint,
                post.idempotency_key,
                post.scheduled_at,
                post.published_at,
                post.external_post_id,
                post.retry_count,
                post.max_retries,
                post.next_retry_at,
                post.last_error,
                1 if post.requires_manual_review else 0,
                post.manual_review_reason,
                post.created_at or now,
                now,
            ))

            # Record fingerprint if approved/scheduled/published
            if post.status in ("APPROVED", "SCHEDULED", "PUBLISHED"):
                cursor.execute("""
                    INSERT OR IGNORE INTO content_fingerprints (fingerprint, post_id, platform, created_at)
                    VALUES (?, ?, ?, ?);
                """, (post.fingerprint, post.id, post.platform, now))

            conn.commit()

    def get_post_by_id(self, post_id: str) -> Optional[PostRecord]:
        with get_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM posts WHERE id = ?", (post_id,))
            row = cursor.fetchone()
            return self._row_to_record(row) if row else None

    def find_by_fingerprint(self, fingerprint: str) -> Optional[PostRecord]:
        with get_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM posts WHERE fingerprint = ?", (fingerprint,))
            row = cursor.fetchone()
            return self._row_to_record(row) if row else None

    def get_recent_posts(self, platform: Optional[str] = None, limit: int = 50) -> List[PostRecord]:
        with get_connection(self.db_path) as conn:
            cursor = conn.cursor()
            if platform:
                cursor.execute(
                    "SELECT * FROM posts WHERE platform = ? ORDER BY created_at DESC LIMIT ?",
                    (platform, limit),
                )
            else:
                cursor.execute("SELECT * FROM posts ORDER BY created_at DESC LIMIT ?", (limit,))
            return [self._row_to_record(row) for row in cursor.fetchall()]

    def get_scheduled_due_posts(self, current_utc_iso: str) -> List[PostRecord]:
        """Fetch posts scheduled for or before the given time that have not yet published."""
        with get_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM posts
                WHERE (status = 'SCHEDULED' AND scheduled_at <= ?)
                   OR (status = 'RETRY_PENDING' AND next_retry_at <= ?)
                ORDER BY scheduled_at ASC;
            """, (current_utc_iso, current_utc_iso))
            return [self._row_to_record(row) for row in cursor.fetchall()]

    def get_all_scheduled_posts(self) -> List[PostRecord]:
        """Fetch all scheduled and retry_pending posts regardless of timestamp."""
        with get_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM posts
                WHERE status IN ('SCHEDULED', 'RETRY_PENDING')
                ORDER BY scheduled_at ASC;
            """)
            return [self._row_to_record(row) for row in cursor.fetchall()]

    def get_overdue_posts(self, current_utc_iso: str, grace_hours: int = 24) -> List[PostRecord]:
        """Fetch scheduled posts whose time passed during a downtime window."""
        with get_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM posts
                WHERE status = 'SCHEDULED'
                  AND scheduled_at < ?
                ORDER BY scheduled_at ASC;
            """, (current_utc_iso,))
            return [self._row_to_record(row) for row in cursor.fetchall()]

    def get_posts_requiring_review(self) -> List[PostRecord]:
        with get_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM posts WHERE status = 'MANUAL_REVIEW_REQUIRED' ORDER BY created_at DESC;")
            return [self._row_to_record(row) for row in cursor.fetchall()]

    def get_queue_counts(self) -> Dict[str, int]:
        with get_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT status, COUNT(*) as cnt FROM posts GROUP BY status;")
            counts = {row["status"]: row["cnt"] for row in cursor.fetchall()}
            return counts

    def update_post_status(
        self,
        post_id: str,
        status: str,
        external_id: Optional[str] = None,
        last_error: Optional[str] = None,
        next_retry_at: Optional[str] = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with get_connection(self.db_path) as conn:
            cursor = conn.cursor()
            published_at = now if status == "PUBLISHED" else None
            cursor.execute("""
                UPDATE posts SET
                    status = ?,
                    external_post_id = COALESCE(?, external_post_id),
                    published_at = COALESCE(?, published_at),
                    last_error = ?,
                    next_retry_at = ?,
                    updated_at = ?
                WHERE id = ?;
            """, (status, external_id, published_at, last_error, next_retry_at, now, post_id))
            conn.commit()

    def log_audit_event(self, event_type: str, post_id: Optional[str], details: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with get_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO audit_logs (timestamp, event_type, post_id, details)
                VALUES (?, ?, ?, ?);
            """, (now, event_type, post_id, details))
            conn.commit()

    def get_recent_audit_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        with get_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?;", (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def record_generation_run(
        self,
        run_id: str,
        started_at: str,
        completed_at: str,
        status: str,
        topic_chosen: str,
        reason: str,
        posts_generated: int,
        posts_scheduled: int,
        details: Dict[str, Any],
    ) -> None:
        with get_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO generation_runs (
                    id, started_at, completed_at, status, topic_chosen,
                    reason, posts_generated, posts_scheduled, details_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                run_id,
                started_at,
                completed_at,
                status,
                topic_chosen,
                reason,
                posts_generated,
                posts_scheduled,
                json.dumps(details),
            ))
            conn.commit()
