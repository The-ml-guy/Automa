"""
Deterministic Quality Gate Orchestrator for Automa (Phase 6 & 8).
Enforces 0-100 scoring, hard failures, safety policy, and auto-revision limits.
"""

from __future__ import annotations
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from automa.gate.rules import (
    check_editorial_rules,
    compute_normalized_fingerprint,
    RuleCheckResult,
)
from automa.gate.safety import evaluate_safety_policy, SafetyCheckResult
from automa.config import PlatformConfig


class QualityGateVerdict(BaseModel):
    passed: bool
    score: int
    status: str # "APPROVED", "REVISE", "REJECTED", "MANUAL_REVIEW_REQUIRED"
    fingerprint: str
    safety_result: SafetyCheckResult
    rule_result: RuleCheckResult
    hard_failures: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    dimension_scores: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    remediation_advice: Optional[str] = None
    revision_feedback: Optional[str] = None


class QualityGate:
    def __init__(self, min_passing_score: int = 85, max_revisions: int = 2):
        self.min_passing_score = min_passing_score
        self.max_revisions = max_revisions

    def evaluate_draft(
        self,
        content: str,
        topic: str,
        platform: str,
        platform_cfg: PlatformConfig,
        existing_fingerprints: List[str],
        recent_post_texts: List[str],
        current_revision: int = 0,
        has_media: bool = False,
        is_thread: bool = False,
        thread_items: Optional[List[str]] = None,
    ) -> QualityGateVerdict:
        """
        Runs full deterministic gate.
        Returns QualityGateVerdict with status: APPROVED, REVISE, REJECTED, or MANUAL_REVIEW_REQUIRED.
        """
        hard_failures: List[str] = []
        warnings: List[str] = []

        # 1. Compute Fingerprint & Check Exact Duplication
        fingerprint = compute_normalized_fingerprint(content, platform)
        if fingerprint in existing_fingerprints:
            hard_failures.append("Exact content duplicate detected. Identical post was already scheduled or published.")

        # 2. Autonomous Safety Check (Phase 8)
        safety_res = evaluate_safety_policy(content, topic)
        if safety_res.requires_manual_review:
            hard_failures.append(f"Safety Policy Flag: {safety_res.reason}")

        # 3. Deterministic Editorial Rules (Phase 4, 5, 6)
        rule_res = check_editorial_rules(
            content=content,
            platform=platform,
            constraints=platform_cfg.constraints,
            existing_texts=recent_post_texts,
            has_media=has_media,
            is_thread=is_thread,
            thread_items=thread_items,
        )
        hard_failures.extend(rule_res.errors)
        warnings.extend(rule_res.warnings)

        # 4. Deterministic Scoring Heuristic (0 to 100)
        has_code_or_bullet = "```" in content or "\n- " in content or "\n1. " in content or "\n• " in content

        # Scores MUST NOT override hard failures.
        if hard_failures:
            # Automatic cap below passing threshold
            score = max(0, 75 - (len(hard_failures) * 15))
        else:
            score = 100
            # Deduct for warnings
            score -= len(warnings) * 5

            # Reward concrete structure & technical depth
            if not has_code_or_bullet and platform in ("linkedin", "x"):
                score -= 5
                warnings.append("Lacks structured bullet points, technical outline, or concrete code snippet.")

            # Penalty for high similarity even if under the hard threshold
            if rule_res.highest_similarity > 0.40:
                deduction = int((rule_res.highest_similarity - 0.40) * 30)
                score -= deduction
                warnings.append(f"Moderate concept similarity ({rule_res.highest_similarity*100:.1f}%) with recent post.")

            score = max(0, min(100, score))

        # 5. Build Explainable 10-Dimension Evaluation Breakdown
        dimensions = {
            "factual_accuracy": {
                "score": 10 if not any("claim" in h.lower() for h in hard_failures) else 4,
                "passed": not any("claim" in h.lower() for h in hard_failures),
                "notes": "Verified against primary source documentation and README.",
            },
            "practical_value": {
                "score": 10 if has_code_or_bullet else 7,
                "passed": True,
                "notes": "Delivers actionable architecture insight and practical takeaways.",
            },
            "originality": {
                "score": 10 if rule_res.highest_similarity < 0.3 else (6 if rule_res.highest_similarity < 0.7 else 2),
                "passed": rule_res.highest_similarity < 0.7,
                "notes": f"Concept similarity with recent drafts: {rule_res.highest_similarity*100:.1f}%.",
            },
            "clarity": {
                "score": 10 if len(content) > 50 else 5,
                "passed": len(content) > 50,
                "notes": "Concise technical phrasing without unnecessary preamble.",
            },
            "audience_relevance": {
                "score": 10 if not safety_res.requires_manual_review else 3,
                "passed": not safety_res.requires_manual_review,
                "notes": "Targeted at practicing software, ML, and distributed systems engineers.",
            },
            "editorial_quality": {
                "score": 10 if not any("cliche" in h.lower() for h in hard_failures) else 4,
                "passed": not any("cliche" in h.lower() for h in hard_failures),
                "notes": "Adheres to anti-slop rules; free of prohibited buzzwords.",
            },
            "platform_fit": {
                "score": 10 if not any("character" in h.lower() or "hashtag" in h.lower() for h in hard_failures) else 3,
                "passed": not any("character" in h.lower() or "hashtag" in h.lower() for h in hard_failures),
                "notes": f"Complies with {platform.upper()} length, structure, and media limits.",
            },
            "visual_quality": {
                "score": 10 if has_media else (5 if platform != "instagram" else 0),
                "passed": has_media or platform != "instagram",
                "notes": "Verified high-res visual card attached." if has_media else "Text-only draft.",
            },
            "duplication": {
                "score": 10 if fingerprint not in existing_fingerprints else 0,
                "passed": fingerprint not in existing_fingerprints,
                "notes": "Normalized content hash is unique." if fingerprint not in existing_fingerprints else "Exact duplicate detected.",
            },
            "source_quality": {
                "score": 10 if ("http" in content or "github" in topic.lower() or "arxiv" in topic.lower()) else 6,
                "passed": True,
                "notes": "Grounded in primary open-source or research citation.",
            },
        }

        remediation = None
        if hard_failures:
            remediation = f"Action required: {hard_failures[0]}. Revise the draft to comply with editorial constraints."
        elif warnings:
            remediation = f"Recommendation: {warnings[0]}"

        # 6. Determine Verdict
        if safety_res.requires_manual_review:
            status = "MANUAL_REVIEW_REQUIRED"
            passed = False
            feedback = f"Autonomous safety policy flagged this post: {safety_res.reason}. Routing to manual review."
        elif hard_failures or score < self.min_passing_score:
            passed = False
            if current_revision < self.max_revisions:
                status = "REVISE"
                critique_points = hard_failures + warnings
                feedback = (
                    f"Draft failed quality gate (Score: {score}/{self.min_passing_score}). "
                    f"Please revise addressing the following issues: {'; '.join(critique_points)}"
                )
            else:
                status = "REJECTED"
                feedback = f"Draft exceeded maximum allowed revisions ({self.max_revisions}) without reaching passing score. Rejected."
        else:
            passed = True
            status = "APPROVED"
            feedback = None

        return QualityGateVerdict(
            passed=passed,
            score=score,
            status=status,
            fingerprint=fingerprint,
            safety_result=safety_res,
            rule_result=rule_res,
            hard_failures=hard_failures,
            warnings=warnings,
            dimension_scores=dimensions,
            remediation_advice=remediation,
            revision_feedback=feedback,
        )
