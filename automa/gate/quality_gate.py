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
        # Scores MUST NOT override hard failures.
        if hard_failures:
            # Automatic cap below passing threshold
            score = max(0, 75 - (len(hard_failures) * 15))
        else:
            score = 100
            # Deduct for warnings
            score -= len(warnings) * 5

            # Reward concrete structure & technical depth
            has_code_or_bullet = "```" in content or "\n- " in content or "\n1. " in content
            if not has_code_or_bullet and platform in ("linkedin", "x"):
                score -= 5
                warnings.append("Lacks structured bullet points, technical outline, or concrete code snippet.")

            # Penalty for high similarity even if under the hard threshold
            if rule_res.highest_similarity > 0.40:
                deduction = int((rule_res.highest_similarity - 0.40) * 30)
                score -= deduction
                warnings.append(f"Moderate concept similarity ({rule_res.highest_similarity*100:.1f}%) with recent post.")

            score = max(0, min(100, score))

        # 5. Determine Verdict
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
            revision_feedback=feedback,
        )
