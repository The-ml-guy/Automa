"""
Unit tests for Autonomous Safety Policy (Phase 8).
"""

from automa.gate.safety import evaluate_safety_policy
from automa.gate.quality_gate import QualityGate
from automa.config import PlatformConfig, PlatformConstraints


def test_financial_advice_flagged():
    res = evaluate_safety_policy(
        content="You should immediately buy crypto before the next bull run. Guaranteed returns!",
        topic="Crypto Investment",
    )
    assert not res.is_safe
    assert res.requires_manual_review
    assert res.category == "FINANCIAL_ADVICE"


def test_medical_advice_flagged():
    res = evaluate_safety_policy(
        content="Here is how to cure chronic pain without any medical prescription or doctor visit.",
        topic="Health Tips",
    )
    assert not res.is_safe
    assert res.requires_manual_review
    assert res.category == "MEDICAL_ADVICE"


def test_political_endorsement_flagged():
    res = evaluate_safety_policy(
        content="Everyone in engineering must vote for candidate Smith in the upcoming election.",
        topic="Election Commentary",
    )
    assert not res.is_safe
    assert res.requires_manual_review
    assert res.category == "POLITICAL_CONTENT"


def test_safety_gate_routes_to_manual_review():
    cfg = PlatformConfig(name="LinkedIn", constraints=PlatformConstraints())
    gate = QualityGate()

    risky_content = "Buy bitcoin and altcoins now for guaranteed yield! #Crypto #Finance"
    verdict = gate.evaluate_draft(
        content=risky_content,
        topic="Investment Advice",
        platform="linkedin",
        platform_cfg=cfg,
        existing_fingerprints=[],
        recent_post_texts=[],
    )

    assert not verdict.passed
    assert verdict.status == "MANUAL_REVIEW_REQUIRED"
    assert verdict.safety_result.requires_manual_review
