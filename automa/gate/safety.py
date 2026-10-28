"""
Autonomous Safety Policy for Automa (Phase 8).
Blocks automated publishing of high-stakes, sensitive, or risky topics.
"""

from __future__ import annotations
import re
from typing import Tuple, Optional
from pydantic import BaseModel


class SafetyCheckResult(BaseModel):
    is_safe: bool
    requires_manual_review: bool
    category: Optional[str] = None
    reason: Optional[str] = None


# Patterns for high-stakes topics that must NEVER be autonomously published
HIGH_STAKES_PATTERNS = [
    # Financial, Investment, Crypto Advice
    (
        re.compile(r"\b(buy|sell|invest in|short)\s+(crypto|bitcoin|eth|stocks|equities|options|altcoins)\b", re.IGNORECASE),
        "FINANCIAL_ADVICE",
        "Direct investment or financial trading recommendations are strictly forbidden from autonomous publishing.",
    ),
    (
        re.compile(r"\b(guaranteed\s+(returns?|yield|profit)|100x|10x\s+gains?)\b", re.IGNORECASE),
        "FINANCIAL_ADVICE",
        "Exaggerated financial return claims detected.",
    ),
    # Medical & Health Advice
    (
        re.compile(r"\b(cure|treat|diagnose|prescription|vaccine\s+efficacy|alternative\s+medicine\s+cures)\b", re.IGNORECASE),
        "MEDICAL_ADVICE",
        "Medical advice, health diagnoses, or treatment claims cannot be published autonomously.",
    ),
    # Legal Advice & Lawsuits
    (
        re.compile(r"\b(sue|lawsuit|legal\s+liability|infringing\s+copyright|breach\s+of\s+contract)\b", re.IGNORECASE),
        "LEGAL_ADVICE",
        "Legal advice or discussions of litigation require manual review.",
    ),
    # Political Endorsements & Partisan Politics
    (
        re.compile(r"\b(vote\s+for|democrats?|republicans?|presidential\s+candidate|election\s+fraud)\b", re.IGNORECASE),
        "POLITICAL_CONTENT",
        "Partisan political statements or endorsements must not be posted autonomously on behalf of brand.",
    ),
    # Unverified Breaking News & Accusations
    (
        re.compile(r"\b(breaking\s*:\s*|allegations?\s+against|scandal\s+exposed|fraud\s+investigation)\b", re.IGNORECASE),
        "UNVERIFIED_ACCUSATION",
        "Unverified breaking news and accusations require independent human verification.",
    ),
    # Confidential or Third-Party Data
    (
        re.compile(r"\b(confidential|nda|internal\s+memo|unreleased\s+features?|proprietary\s+codebase)\b", re.IGNORECASE),
        "CONFIDENTIAL_DATA",
        "Potential breach of confidentiality or internal company information.",
    ),
    # PII Patterns (Credit cards, SSN, API secrets)
    (
        re.compile(r"\b(?:\d{3}-\d{2}-\d{4}|\d{4}-\d{4}-\d{4}-\d{4})\b"),
        "PII_DATA",
        "Detected potential Social Security or Credit Card number in draft.",
    ),
]


def evaluate_safety_policy(content: str, topic: str) -> SafetyCheckResult:
    """
    Evaluates draft content against Phase 8 safety constraints.
    Returns SafetyCheckResult with requires_manual_review=True if high stakes are detected.
    """
    full_text = f"{topic}\n{content}"

    for pattern, category, reason in HIGH_STAKES_PATTERNS:
        match = pattern.search(full_text)
        if match:
            return SafetyCheckResult(
                is_safe=False,
                requires_manual_review=True,
                category=category,
                reason=f"{reason} (Matched: '{match.group(0)}')",
            )

    return SafetyCheckResult(is_safe=True, requires_manual_review=False)
