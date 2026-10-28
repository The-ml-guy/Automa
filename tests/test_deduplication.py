"""
Unit tests for Content Fingerprinting and Deduplication (Phase 6 & 7).
"""

from automa.gate.rules import compute_normalized_fingerprint, compute_jaccard_similarity
from automa.gate.quality_gate import QualityGate
from automa.config import PlatformConfig, PlatformConstraints


def test_fingerprint_normalization():
    text1 = "Cron is a scheduler, NOT an orchestrator!"
    text2 = "  cron   is a scheduler not an orchestrator   "

    fp1 = compute_normalized_fingerprint(text1, "linkedin")
    fp2 = compute_normalized_fingerprint(text2, "linkedin")

    assert fp1 == fp2, "Fingerprints must match despite punctuation and whitespace differences."


def test_exact_duplicate_blocked():
    cfg = PlatformConfig(name="LinkedIn", constraints=PlatformConstraints())
    gate = QualityGate()

    content = (
        "Cron is a scheduler, not an orchestrator.\n\n"
        "1. Advisory locks.\n2. Persistent state machine.\n3. Timeout heartbeats.\n\n"
        "#Engineering #Architecture"
    )
    fp = compute_normalized_fingerprint(content, "linkedin")

    verdict = gate.evaluate_draft(
        content=content,
        topic="Schedulers",
        platform="linkedin",
        platform_cfg=cfg,
        existing_fingerprints=[fp],
        recent_post_texts=[],
    )

    assert not verdict.passed
    assert any("Exact content duplicate detected" in f for f in verdict.hard_failures)


def test_high_similarity_repetition_blocked():
    text_a = "SQLite WAL mode allows concurrent readers and a single writer with zero locks."
    text_b = "SQLite WAL mode enables concurrent readers and single writers with zero lock contention."

    sim = compute_jaccard_similarity(text_a, text_b)
    assert sim >= 0.55, f"Expected high similarity between rephrased versions, got {sim}"

    cfg = PlatformConfig(name="LinkedIn", constraints=PlatformConstraints())
    gate = QualityGate()
    verdict = gate.evaluate_draft(
        content=text_b,
        topic="SQLite Concurrency",
        platform="linkedin",
        platform_cfg=cfg,
        existing_fingerprints=[],
        recent_post_texts=[text_a],
    )
    assert not verdict.passed
    assert any("similarity" in f.lower() for f in verdict.hard_failures)
