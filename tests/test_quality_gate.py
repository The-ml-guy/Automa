"""
Unit tests for Automa Deterministic Quality Gate (Phase 4, 5, 6).
"""

import pytest
from automa.gate.quality_gate import QualityGate
from automa.gate.rules import check_editorial_rules
from automa.config import PlatformConfig, PlatformConstraints


@pytest.fixture
def linkedin_cfg():
    return PlatformConfig(
        name="LinkedIn",
        enabled=True,
        constraints=PlatformConstraints(
            min_characters=100,
            max_characters=3000,
            max_emojis=2,
            max_hashtags=3,
        ),
    )


def test_cliche_detection_fails_hard(linkedin_cfg):
    gate = QualityGate()
    slop_content = (
        "In today's fast-paced digital world, you must delve into modern architecture. "
        "It is a true game-changer that will supercharge your workflow and unleash your potential."
    )
    verdict = gate.evaluate_draft(
        content=slop_content,
        topic="Architecture",
        platform="linkedin",
        platform_cfg=linkedin_cfg,
        existing_fingerprints=[],
        recent_post_texts=[],
        current_revision=0,
    )
    assert not verdict.passed
    assert verdict.score < 85
    assert any("delve" in f or "game-changer" in f or "supercharge" in f for f in verdict.hard_failures)


def test_fake_anecdotes_rejected(linkedin_cfg):
    gate = QualityGate()
    fake_content = (
        "Last week, a client came to me with an emergency. We scaled from $0 to $500,000 in 3 days. "
        "Studies show that 97% of engineers agree this is the secret sauce."
    )
    verdict = gate.evaluate_draft(
        content=fake_content,
        topic="Scaling",
        platform="linkedin",
        platform_cfg=linkedin_cfg,
        existing_fingerprints=[],
        recent_post_texts=[],
        current_revision=0,
    )
    assert not verdict.passed
    assert any("fabricated" in f.lower() for f in verdict.hard_failures)


def test_emoji_limits_enforced(linkedin_cfg):
    gate = QualityGate()
    excessive_emojis = "Cron jobs fail in production 🚀🔥💥🎉⚡️ when overlapping occurs."
    verdict = gate.evaluate_draft(
        content=excessive_emojis,
        topic="Cron",
        platform="linkedin",
        platform_cfg=linkedin_cfg,
        existing_fingerprints=[],
        recent_post_texts=[],
        current_revision=0,
    )
    assert not verdict.passed
    assert any("Too many emojis" in f for f in verdict.hard_failures)


def test_clean_technical_post_passes(linkedin_cfg):
    gate = QualityGate()
    valid_content = (
        "Cron is a scheduler, not an orchestrator.\n\n"
        "When batch jobs exceed their execution window, un-gated cron runners spawn duplicate instances. "
        "This triggers concurrent writes and database row locks.\n\n"
        "A reliable architecture requires:\n"
        "1. Advisory lock at the file or database level.\n"
        "2. Persistent state machine (QUEUED -> PROCESSING -> COMPLETED).\n"
        "3. Timeout heartbeats to recover stalled workers.\n\n"
        "#DistributedSystems #SoftwareEngineering"
    )
    verdict = gate.evaluate_draft(
        content=valid_content,
        topic="Schedulers",
        platform="linkedin",
        platform_cfg=linkedin_cfg,
        existing_fingerprints=[],
        recent_post_texts=[],
        current_revision=0,
    )
    assert verdict.passed
    assert verdict.score >= 85
    assert verdict.status == "APPROVED"
    assert len(verdict.hard_failures) == 0


def test_max_revisions_rejection(linkedin_cfg):
    gate = QualityGate(max_revisions=2)
    slop_content = "Supercharge your pipeline with this game-changer!"

    # First attempt: REVISE
    v1 = gate.evaluate_draft(slop_content, "Test", "linkedin", linkedin_cfg, [], [], current_revision=0)
    assert v1.status == "REVISE"

    # Second attempt: REVISE
    v2 = gate.evaluate_draft(slop_content, "Test", "linkedin", linkedin_cfg, [], [], current_revision=1)
    assert v2.status == "REVISE"

    # Third attempt (exceeded max 2 revisions): REJECTED
    v3 = gate.evaluate_draft(slop_content, "Test", "linkedin", linkedin_cfg, [], [], current_revision=2)
    assert v3.status == "REJECTED"
