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
from automa.db.schema import get_connection, init_db, DB_PATH


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


class DiscoveredItemRecord(BaseModel):
    id: str
    title: str
    url: str
    source_type: str  # "arxiv", "huggingface", "github", "hackernews"
    primary_category: Optional[str] = None
    authors: Optional[str] = None
    organization: Optional[str] = None
    abstract: Optional[str] = None
    raw_metadata: Dict[str, Any] = Field(default_factory=dict)
    published_at: Optional[str] = None
    discovered_at: str
    status: str = "DISCOVERED"  # "DISCOVERED", "VERIFIED", "RANKED", "PROCESSED"


class VerifiedSourceRecord(BaseModel):
    id: str
    discovered_item_id: str
    primary_url: str
    is_verified: bool = True
    pub_type: str = "preprint"  # preprint, peer_reviewed, official_announcement, open_source_repo
    confirmed_facts: List[str] = Field(default_factory=list)
    caveats: List[str] = Field(default_factory=list)
    evidence_snippets: List[str] = Field(default_factory=list)
    requires_human_review: bool = False
    review_reason: Optional[str] = None
    verified_at: str


class TopicRankingRecord(BaseModel):
    id: str
    discovered_item_id: str
    total_score: float
    score_recency: float
    score_usefulness: float
    score_significance: float
    score_accessibility: float
    score_credibility: float
    score_novelty: float
    signals: Dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None
    ranked_at: str


class ResearchDistillationRecord(BaseModel):
    id: str
    discovered_item_id: str
    problem: str
    why_it_matters: str
    core_idea: str
    what_is_new: str
    results_and_conditions: str
    limitations: str
    code_and_paper_links: List[str] = Field(default_factory=list)
    distilled_at: str


class ContentAngleRecord(BaseModel):
    id: str
    discovered_item_id: str
    candidate_angles: List[Dict[str, str]] = Field(default_factory=list)
    selected_angle: str
    target_platform: str
    strategy_reasoning: str
    created_at: str


class PostRepository:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        init_db(self.db_path)

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

    def get_existing_fingerprints(self) -> List[str]:
        with get_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT fingerprint FROM content_fingerprints;")
            return [row["fingerprint"] for row in cursor.fetchall()]

    def save_fingerprint(self, fingerprint: str, post_id: str, platform: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with get_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO content_fingerprints (fingerprint, post_id, platform, created_at)
                VALUES (?, ?, ?, ?);
            """, (fingerprint, post_id, platform, now))
            conn.commit()

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

    # =========================================================================
    # AI CONTENT INTELLIGENCE METHODS
    # =========================================================================

    def save_discovered_item(self, item: DiscoveredItemRecord) -> bool:
        """Saves a discovered item if URL is not already in database. Returns True if inserted."""
        with get_connection(self.db_path) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO discovered_items (
                        id, title, url, source_type, primary_category, authors,
                        organization, abstract, raw_metadata_json, published_at,
                        discovered_at, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(url) DO UPDATE SET
                        title = excluded.title,
                        raw_metadata_json = excluded.raw_metadata_json;
                """, (
                    item.id,
                    item.title,
                    item.url,
                    item.source_type,
                    item.primary_category,
                    item.authors,
                    item.organization,
                    item.abstract,
                    json.dumps(item.raw_metadata),
                    item.published_at,
                    item.discovered_at,
                    item.status,
                ))
                conn.commit()
                return cursor.rowcount > 0
            except Exception:
                return False

    def get_discovered_items(
        self,
        source_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[DiscoveredItemRecord]:
        with get_connection(self.db_path) as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM discovered_items WHERE 1=1"
            params: List[Any] = []
            if source_type:
                query += " AND source_type = ?"
                params.append(source_type)
            if status:
                query += " AND status = ?"
                params.append(status)
            query += " ORDER BY discovered_at DESC LIMIT ?;"
            params.append(limit)
            cursor.execute(query, params)
            items = []
            for row in cursor.fetchall():
                items.append(DiscoveredItemRecord(
                    id=row["id"],
                    title=row["title"],
                    url=row["url"],
                    source_type=row["source_type"],
                    primary_category=row["primary_category"],
                    authors=row["authors"],
                    organization=row["organization"],
                    abstract=row["abstract"],
                    raw_metadata=json.loads(row["raw_metadata_json"]) if row["raw_metadata_json"] else {},
                    published_at=row["published_at"],
                    discovered_at=row["discovered_at"],
                    status=row["status"],
                ))
            return items

    def get_discovered_item_by_id(self, item_id: str) -> Optional[DiscoveredItemRecord]:
        with get_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM discovered_items WHERE id = ?;", (item_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return DiscoveredItemRecord(
                id=row["id"],
                title=row["title"],
                url=row["url"],
                source_type=row["source_type"],
                primary_category=row["primary_category"],
                authors=row["authors"],
                organization=row["organization"],
                abstract=row["abstract"],
                raw_metadata=json.loads(row["raw_metadata_json"]) if row["raw_metadata_json"] else {},
                published_at=row["published_at"],
                discovered_at=row["discovered_at"],
                status=row["status"],
            )

    def update_discovered_item_status(self, item_id: str, status: str) -> None:
        with get_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE discovered_items SET status = ? WHERE id = ?;", (status, item_id))
            conn.commit()

    def save_verified_source(self, record: VerifiedSourceRecord) -> None:
        with get_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO verified_sources (
                    id, discovered_item_id, primary_url, is_verified, pub_type,
                    confirmed_facts_json, caveats_json, evidence_snippets_json,
                    requires_human_review, review_reason, verified_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                record.id,
                record.discovered_item_id,
                record.primary_url,
                1 if record.is_verified else 0,
                record.pub_type,
                json.dumps(record.confirmed_facts),
                json.dumps(record.caveats),
                json.dumps(record.evidence_snippets),
                1 if record.requires_human_review else 0,
                record.review_reason,
                record.verified_at,
            ))
            conn.commit()

    def get_verified_source(self, discovered_item_id: str) -> Optional[VerifiedSourceRecord]:
        with get_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM verified_sources WHERE discovered_item_id = ?;", (discovered_item_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return VerifiedSourceRecord(
                id=row["id"],
                discovered_item_id=row["discovered_item_id"],
                primary_url=row["primary_url"],
                is_verified=bool(row["is_verified"]),
                pub_type=row["pub_type"],
                confirmed_facts=json.loads(row["confirmed_facts_json"]) if row["confirmed_facts_json"] else [],
                caveats=json.loads(row["caveats_json"]) if row["caveats_json"] else [],
                evidence_snippets=json.loads(row["evidence_snippets_json"]) if row["evidence_snippets_json"] else [],
                requires_human_review=bool(row["requires_human_review"]),
                review_reason=row["review_reason"],
                verified_at=row["verified_at"],
            )

    def save_topic_ranking(self, ranking: TopicRankingRecord) -> None:
        with get_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO topic_rankings (
                    id, discovered_item_id, total_score, score_recency, score_usefulness,
                    score_significance, score_accessibility, score_credibility, score_novelty,
                    signals_json, notes, ranked_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                ranking.id,
                ranking.discovered_item_id,
                ranking.total_score,
                ranking.score_recency,
                ranking.score_usefulness,
                ranking.score_significance,
                ranking.score_accessibility,
                ranking.score_credibility,
                ranking.score_novelty,
                json.dumps(ranking.signals),
                ranking.notes,
                ranking.ranked_at,
            ))
            conn.commit()

    def get_top_ranked_topics(self, limit: int = 20) -> List[Dict[str, Any]]:
        with get_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    r.*,
                    d.title, d.url, d.source_type, d.authors, d.organization, d.abstract, d.published_at
                FROM topic_rankings r
                JOIN discovered_items d ON r.discovered_item_id = d.id
                ORDER BY r.total_score DESC
                LIMIT ?;
            """, (limit,))
            rows = cursor.fetchall()
            results = []
            for row in rows:
                results.append({
                    "ranking_id": row["id"],
                    "item_id": row["discovered_item_id"],
                    "title": row["title"],
                    "url": row["url"],
                    "source_type": row["source_type"],
                    "authors": row["authors"],
                    "organization": row["organization"],
                    "abstract": row["abstract"],
                    "published_at": row["published_at"],
                    "total_score": row["total_score"],
                    "score_recency": row["score_recency"],
                    "score_usefulness": row["score_usefulness"],
                    "score_significance": row["score_significance"],
                    "score_accessibility": row["score_accessibility"],
                    "score_credibility": row["score_credibility"],
                    "score_novelty": row["score_novelty"],
                    "signals": json.loads(row["signals_json"]) if row["signals_json"] else {},
                    "notes": row["notes"],
                    "ranked_at": row["ranked_at"],
                })
            return results

    def save_research_distillation(self, distillation: ResearchDistillationRecord) -> None:
        with get_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO research_distillations (
                    id, discovered_item_id, problem, why_it_matters, core_idea,
                    what_is_new, results_and_conditions, limitations,
                    code_and_paper_links_json, distilled_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                distillation.id,
                distillation.discovered_item_id,
                distillation.problem,
                distillation.why_it_matters,
                distillation.core_idea,
                distillation.what_is_new,
                distillation.results_and_conditions,
                distillation.limitations,
                json.dumps(distillation.code_and_paper_links),
                distillation.distilled_at,
            ))
            conn.commit()

    def get_research_distillation(self, discovered_item_id: str) -> Optional[ResearchDistillationRecord]:
        with get_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM research_distillations WHERE discovered_item_id = ?;", (discovered_item_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return ResearchDistillationRecord(
                id=row["id"],
                discovered_item_id=row["discovered_item_id"],
                problem=row["problem"],
                why_it_matters=row["why_it_matters"],
                core_idea=row["core_idea"],
                what_is_new=row["what_is_new"],
                results_and_conditions=row["results_and_conditions"],
                limitations=row["limitations"],
                code_and_paper_links=json.loads(row["code_and_paper_links_json"]) if row["code_and_paper_links_json"] else [],
                distilled_at=row["distilled_at"],
            )

    def save_content_angles(self, angles: ContentAngleRecord) -> None:
        with get_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO content_angles (
                    id, discovered_item_id, candidate_angles_json, selected_angle,
                    target_platform, strategy_reasoning, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (
                angles.id,
                angles.discovered_item_id,
                json.dumps(angles.candidate_angles),
                angles.selected_angle,
                angles.target_platform,
                angles.strategy_reasoning,
                angles.created_at,
            ))
            conn.commit()

    def get_content_angles(self, discovered_item_id: str) -> List[ContentAngleRecord]:
        with get_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM content_angles WHERE discovered_item_id = ?;", (discovered_item_id,))
            rows = cursor.fetchall()
            results = []
            for row in rows:
                results.append(ContentAngleRecord(
                    id=row["id"],
                    discovered_item_id=row["discovered_item_id"],
                    candidate_angles=json.loads(row["candidate_angles_json"]) if row["candidate_angles_json"] else [],
                    selected_angle=row["selected_angle"],
                    target_platform=row["target_platform"],
                    strategy_reasoning=row["strategy_reasoning"],
                    created_at=row["created_at"],
                ))
            return results

    def get_intelligence_stats(self) -> Dict[str, Any]:
        with get_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM discovered_items;")
            total_discovered = cursor.fetchone()[0]

            cursor.execute("SELECT source_type, COUNT(*) as cnt FROM discovered_items GROUP BY source_type;")
            source_breakdown = {row["source_type"]: row["cnt"] for row in cursor.fetchall()}

            cursor.execute("SELECT COUNT(*) FROM verified_sources WHERE is_verified = 1;")
            total_verified = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM topic_rankings;")
            total_ranked = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM research_distillations;")
            total_distilled = cursor.fetchone()[0]

            return {
                "total_discovered": total_discovered,
                "source_breakdown": source_breakdown,
                "total_verified": total_verified,
                "total_ranked": total_ranked,
                "total_distilled": total_distilled,
            }
