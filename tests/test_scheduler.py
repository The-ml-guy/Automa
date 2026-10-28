"""
Unit tests for Persistent Scheduler and Queue State Transitions (Phase 7).
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from automa.db.schema import init_db
from automa.db.repository import PostRepository, PostRecord
from automa.scheduler.runner import SchedulerRunner


def test_sqlite_queue_state_transitions(tmp_path: Path):
    db_file = tmp_path / "test_automa.db"
    init_db(db_file)
    repo = PostRepository(db_path=db_file)

    post = PostRecord(
        id="post_state_001",
        platform="x",
        status="APPROVED",
        topic="Testing Queues",
        content="Testing state machine.",
        fingerprint="fp_state_001",
        idempotency_key="idemp_state_001",
        scheduled_at="2026-10-29T12:00:00Z",
        created_at="2026-10-29T00:00:00Z",
        updated_at="2026-10-29T00:00:00Z",
    )
    repo.save_post(post)

    saved = repo.get_post_by_id("post_state_001")
    assert saved.status == "APPROVED"

    # Transition to SCHEDULED
    repo.update_post_status("post_state_001", status="SCHEDULED")
    assert repo.get_post_by_id("post_state_001").status == "SCHEDULED"

    # Transition to PUBLISHED
    repo.update_post_status("post_state_001", status="PUBLISHED", external_id="ext_999")
    pub = repo.get_post_by_id("post_state_001")
    assert pub.status == "PUBLISHED"
    assert pub.external_post_id == "ext_999"
    assert pub.published_at is not None


def test_overdue_recovery(tmp_path: Path):
    db_file = tmp_path / "test_automa_recovery.db"
    init_db(db_file)
    repo = PostRepository(db_path=db_file)

    now = datetime.now(timezone.utc)
    # A post scheduled 4 hours ago (during downtime)
    past_time = (now - timedelta(hours=4)).isoformat()

    post = PostRecord(
        id="overdue_001",
        platform="linkedin",
        status="SCHEDULED",
        topic="Overdue Recovery Test",
        content="Testing recovery.",
        fingerprint="fp_overdue_001",
        idempotency_key="idemp_overdue_001",
        scheduled_at=past_time,
        created_at=past_time,
        updated_at=past_time,
    )
    repo.save_post(post)

    runner = SchedulerRunner(repo=repo)
    recovered = runner.recover_overdue_posts()
    assert recovered == 1


def test_exponential_backoff_calculation():
    runner = SchedulerRunner()
    t1 = runner.compute_exponential_backoff(retry_count=1, base_seconds=300)
    t2 = runner.compute_exponential_backoff(retry_count=2, base_seconds=300)

    # Retry 2 should have longer delay than Retry 1
    assert t2 > t1
