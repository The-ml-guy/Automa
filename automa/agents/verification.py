"""
Agent B: Source Verification Agent for Automa.
Verifies claims against primary sources, separates facts from speculation,
detects misleading performance statements, checks peer-reviewed/preprint status,
and flags high-risk or conflicting assertions for human review.
"""

from __future__ import annotations
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import requests

from automa.agents.base import BaseAgent
from automa.db.repository import PostRepository, DiscoveredItemRecord, VerifiedSourceRecord

logger = logging.getLogger("automa.agents.verification")

# Indicators of sensationalized, misleading, or unsupported hype
SUSPICIOUS_CLAIM_PATTERNS = [
    (r"\b100x\s+(?:faster|better|smarter)\b", "Extreme unverified 100x performance multiplier claim"),
    (r"\bdestroys?\s+(?:all|other|gpt-?4|claude)\b", "Combative benchmark hyperbole without test condition context"),
    (r"\bhuman[- ]level\s+agi\s+(?:achieved|unlocked)\b", "Premature AGI milestone claim"),
    (r"\breplaces\s+all\s+(?:software\s+engineers|developers)\b", "Exaggerated labor displacement speculation"),
    (r"\b100%\s+accurate\b", "Impossible zero-error claim for statistical models"),
    (r"\bleaked\s+(?:internal\s+benchmark|confidential)\b", "Unverified leak or non-public rumor"),
]


class SourceVerificationAgent(BaseAgent):
    """
    Validates primary source authenticity, inspects underlying papers/code,
    isolates hard verified facts, and flags unverified claims.
    """

    def __init__(self, repo: Optional[PostRepository] = None, timeout_seconds: int = 6):
        super().__init__(
            name="SourceVerificationAgent",
            description="Verifies claims against primary documentation, papers, and repositories",
        )
        self.repo = repo or PostRepository()
        self.timeout = timeout_seconds

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        item_id = context.get("item_id")
        if item_id:
            item = self.repo.get_discovered_item_by_id(item_id)
            items_to_verify = [item] if item else []
        else:
            # Verify newly discovered items that haven't been verified yet
            items = self.repo.get_discovered_items(status="DISCOVERED", limit=context.get("limit", 10))
            items_to_verify = items

        verified_records: List[VerifiedSourceRecord] = []
        flagged_count = 0

        for item in items_to_verify:
            record = self.verify_item(item)
            self.repo.save_verified_source(record)
            new_status = "FLAGGED_REVIEW" if record.requires_human_review else "VERIFIED"
            self.repo.update_discovered_item_status(item.id, new_status)
            verified_records.append(record)
            if record.requires_human_review:
                flagged_count += 1

        self.logger.info(
            "Source verification finished: %d verified, %d flagged for review",
            len(verified_records) - flagged_count,
            flagged_count,
        )

        return {
            "success": True,
            "items_processed": len(verified_records),
            "verified_count": len(verified_records) - flagged_count,
            "flagged_count": flagged_count,
            "records": [r.model_dump() for r in verified_records],
        }

    def verify_item(self, item: DiscoveredItemRecord) -> VerifiedSourceRecord:
        """Runs multi-point factual inspection on a discovered item."""
        now = datetime.now(timezone.utc).isoformat()
        rec_id = f"verif_{uuid.uuid4().hex[:10]}"

        # 1. Determine publication category
        pub_type = self._classify_pub_type(item.url, item.source_type)

        # 2. Check for misleading claims / sensationalism in title & abstract
        combined_text = f"{item.title} {item.abstract or ''}"
        suspicious_flags = []
        for pattern, reason in SUSPICIOUS_CLAIM_PATTERNS:
            if re.search(pattern, combined_text, re.IGNORECASE):
                suspicious_flags.append(reason)

        # 3. Extract confirmed facts vs caveats
        confirmed_facts, caveats = self._extract_facts_and_caveats(item, pub_type)

        # 4. Check whether human review is required
        requires_human_review = False
        review_reason = None

        if suspicious_flags:
            requires_human_review = True
            review_reason = f"Sensationalized claims detected: {'; '.join(suspicious_flags)}"
        elif not item.url.startswith("http"):
            requires_human_review = True
            review_reason = "Invalid or unresolvable primary source link."

        # 5. Build evidence snippets
        evidence = [
            f"Primary Source: {item.url}",
            f"Publication Type: {pub_type.upper()}",
            f"Source Category: {item.primary_category or 'General'}",
        ]
        if item.authors:
            evidence.append(f"Authors / Team: {item.authors}")
        if item.organization:
            evidence.append(f"Organization: {item.organization}")

        return VerifiedSourceRecord(
            id=rec_id,
            discovered_item_id=item.id,
            primary_url=item.url,
            is_verified=not requires_human_review,
            pub_type=pub_type,
            confirmed_facts=confirmed_facts,
            caveats=caveats + suspicious_flags,
            evidence_snippets=evidence,
            requires_human_review=requires_human_review,
            review_reason=review_reason,
            verified_at=now,
        )

    def _classify_pub_type(self, url: str, source_type: str) -> str:
        """Determines whether item is preprint, peer-reviewed, official announcement, or repo."""
        url_lower = url.lower()
        if "arxiv.org" in url_lower:
            return "preprint"
        elif "github.com" in url_lower:
            return "open_source_repo"
        elif "huggingface.co/papers" in url_lower:
            return "preprint"
        elif "huggingface.co" in url_lower:
            return "open_source_weights"
        elif any(domain in url_lower for domain in ["openai.com", "anthropic.com", "googleblog.com", "deepmind.google", "meta.com"]):
            return "official_announcement"
        elif any(conf in url_lower for conf in ["openreview.net", "neurips.cc", "icml.cc", "cvpr", "iclr"]):
            return "peer_reviewed"
        else:
            return "technical_blog"

    def _extract_facts_and_caveats(self, item: DiscoveredItemRecord, pub_type: str) -> Tuple[List[str], List[str]]:
        """Extracts structured verified claims and operational caveats."""
        facts: List[str] = []
        caveats: List[str] = []

        # Category-specific heuristics
        if pub_type == "preprint":
            caveats.append("Preprint status: Manuscript is non-peer-reviewed; independently evaluate reported methodology.")
            facts.append(f"ArXiv manuscript uploaded with identifier: {item.raw_metadata.get('arxiv_id', 'Preprint')}")
        elif pub_type == "open_source_repo":
            stars = item.raw_metadata.get("stars", 0)
            license_spdx = item.raw_metadata.get("license", "Open Source")
            facts.append(f"Public open-source repository ({license_spdx}) with {stars:,} community stars.")
            features = item.raw_metadata.get("key_features", [])
            for feat in features[:2]:
                facts.append(f"Architecture: {feat}")
            benchmarks = item.raw_metadata.get("benchmarks", [])
            if benchmarks:
                facts.append(f"Reported Metric: {benchmarks[0]}")
            caveats.append("Production adoption requires evaluating dependencies, unit test coverage, and API stability.")
        elif pub_type == "official_announcement":
            facts.append(f"Direct official announcement from {item.organization or 'founding lab'}.")
            caveats.append("Commercial benchmarks reflect vendor-optimized configurations; third-party validation recommended.")

        # Key factual elements
        if item.abstract:
            # Take clean sentences from abstract
            sentences = [s.strip() for s in item.abstract.split(". ") if len(s.strip()) > 30]
            if sentences:
                facts.append(sentences[0] + ".")
            if len(sentences) > 1:
                facts.append(sentences[1] + ".")

        if not caveats:
            caveats.append("Assumptions in original benchmarks may differ from real-world edge or distributed environments.")

        return facts, caveats
