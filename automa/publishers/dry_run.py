"""
Safe Dry-Run Publisher for Automa (Phase 10 & 11).
Simulates multi-platform publishing, persists verification records,
and enforces payload validation without external network calls.
"""

from __future__ import annotations
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from automa.config import CONTENT_DIR
from automa.db.repository import PostRecord
from automa.publishers.base import BasePublisher, PublishResult

logger = logging.getLogger("automa.publishers.dry_run")


class DryRunPublisher(BasePublisher):
    """
    Simulates publishing to LinkedIn, X, and Instagram.
    Serializes publication payload to content/published/ for inspection.
    """

    def __init__(self, output_dir: Path = CONTENT_DIR / "published"):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def publish(self, post: PostRecord) -> PublishResult:
        logger.info("[DRY-RUN PUBLISHER] Simulating publication of %s on %s", post.id, post.platform)

        # Validate required media for Instagram in dry run
        if post.platform == "instagram" and not post.media_urls:
            return PublishResult(
                success=False,
                is_transient_error=False,
                error_message="Instagram publication failed: Missing verified image asset.",
            )

        simulated_id = f"dry_{post.platform}_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()

        payload = {
            "post_id": post.id,
            "platform": post.platform,
            "external_post_id": simulated_id,
            "topic": post.topic,
            "content": post.content,
            "thread_items": post.thread_items,
            "media_urls": post.media_urls,
            "idempotency_key": post.idempotency_key,
            "fingerprint": post.fingerprint,
            "simulated_at": now,
            "status": "PUBLISHED_SIMULATED",
        }

        artifact_file = self.output_dir / f"{post.id}_{post.platform}.json"
        with open(artifact_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        return PublishResult(
            success=True,
            external_post_id=simulated_id,
            is_transient_error=False,
            details={"artifact_file": str(artifact_file)},
        )

    def verify_status(self, external_id: str, platform: str) -> str:
        """Returns confirmed status for dry run."""
        return "PUBLISHED"
