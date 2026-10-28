"""
Unit tests for Publisher and Secret Scrubber (Phase 7, 9, 10).
"""

from pathlib import Path
from automa.db.repository import PostRecord
from automa.publishers.dry_run import DryRunPublisher
from automa.notifications.scrubber import scrub_secrets


def test_dry_run_publisher_creates_artifact(tmp_path: Path):
    publisher = DryRunPublisher(output_dir=tmp_path)
    post = PostRecord(
        id="test_post_001",
        platform="linkedin",
        status="SCHEDULED",
        topic="Architecture",
        content="Clean architecture principles.",
        fingerprint="dummy_fp",
        idempotency_key="idemp_123",
        created_at="2026-10-29T00:00:00Z",
        updated_at="2026-10-29T00:00:00Z",
    )

    result = publisher.publish(post)
    assert result.success
    assert result.external_post_id.startswith("dry_linkedin_")

    artifact_file = tmp_path / "test_post_001_linkedin.json"
    assert artifact_file.exists()


def test_secret_scrubber_masks_keys():
    raw_log = "Error connecting with AIzaSyD3aBcDeFgHiJkLmNoPqRsTuVwXyZ123456 and token=my_super_secret_password"
    clean_log = scrub_secrets(raw_log)

    assert "AIzaSy" not in clean_log
    assert "[REDACTED_GEMINI_KEY]" in clean_log
    assert "my_super_secret_password" not in clean_log
