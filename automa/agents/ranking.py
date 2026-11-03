"""
Agent C: Topic Ranking and Trend Agent for Automa.
Evaluates candidate topics using a configurable 6-dimension weighted scoring model (0-100),
applies recency decay, checks external signals (stars, upvotes, citations),
and enforces topic diversity and anti-repetition.
"""

from __future__ import annotations
import logging
import math
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from automa.agents.base import BaseAgent
from automa.db.repository import PostRepository, DiscoveredItemRecord, TopicRankingRecord
from automa.gate.rules import compute_jaccard_similarity

logger = logging.getLogger("automa.agents.ranking")


class ScoringWeights(BaseModel):
    recency_and_relevance: float = 0.20
    audience_usefulness: float = 0.20
    technical_significance: float = 0.20
    open_source_accessibility: float = 0.15
    credibility_and_source_quality: float = 0.15
    novelty_and_discussion: float = 0.10


class TopicRankingAgent(BaseAgent):
    """
    Ranks discovered intelligence candidates objectively using multi-signal scoring,
    anti-repetition guards, and decay curves.
    """

    def __init__(self, repo: Optional[PostRepository] = None, weights: Optional[ScoringWeights] = None):
        super().__init__(
            name="TopicRankingAgent",
            description="Scores and ranks AI/ML topics across 6 weighted technical dimensions",
        )
        self.repo = repo or PostRepository()
        self.weights = weights or ScoringWeights()

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        limit = context.get("limit", 20)
        verified_only = context.get("verified_only", True)

        # Retrieve items to score
        items = self.repo.get_discovered_items(limit=limit)
        recent_posts = self.repo.get_recent_posts(limit=25)
        recent_post_topics = [p.topic for p in recent_posts]

        rankings: List[TopicRankingRecord] = []

        for item in items:
            ranking = self.score_topic(item, recent_post_topics)
            self.repo.save_topic_ranking(ranking)
            self.repo.update_discovered_item_status(item.id, "RANKED")
            rankings.append(ranking)

        # Sort by total score descending
        rankings.sort(key=lambda r: r.total_score, reverse=True)

        self.logger.info("Scored and ranked %d candidate topics. Top score: %.1f", len(rankings), rankings[0].total_score if rankings else 0)

        return {
            "success": True,
            "items_processed": len(rankings),
            "top_candidates": [r.model_dump() for r in rankings[:10]],
        }

    def score_topic(self, item: DiscoveredItemRecord, recent_post_topics: List[str]) -> TopicRankingRecord:
        """Calculates deterministic 0-100 score across the 6 dimensions."""
        now = datetime.now(timezone.utc)
        rec_id = f"rank_{uuid.uuid4().hex[:10]}"

        # 1. Recency & Relevance (0 - 100)
        score_recency = self._compute_recency_score(item.published_at, now)

        # 2. Audience Usefulness (0 - 100)
        # Evaluates practical applicability to practicing engineers/developers
        score_usefulness = self._compute_usefulness_score(item)

        # 3. Technical Significance (0 - 100)
        # Measures architectural depth, algorithm breakthroughs, benchmarks
        score_significance = self._compute_significance_score(item)

        # 4. Open-Source Accessibility (0 - 100)
        # Higher for reproducible code, weights, public datasets, or GitHub repos
        score_accessibility = self._compute_accessibility_score(item)

        # 5. Credibility & Source Quality (0 - 100)
        # Primary source validity, reputation of authors/orgs, paper vs blog
        score_credibility = self._compute_credibility_score(item)

        # 6. Novelty & Discussion Potential (0 - 100)
        # Counter-intuitive insights, engineering trade-offs, debate value
        score_novelty = self._compute_novelty_score(item, recent_post_topics)

        # Compute weighted total
        raw_total = (
            (score_recency * self.weights.recency_and_relevance)
            + (score_usefulness * self.weights.audience_usefulness)
            + (score_significance * self.weights.technical_significance)
            + (score_accessibility * self.weights.open_source_accessibility)
            + (score_credibility * self.weights.credibility_and_source_quality)
            + (score_novelty * self.weights.novelty_and_discussion)
        )

        # Anti-repetition deduplication penalty against recent posts
        deduplication_penalty = 0.0
        for topic in recent_post_topics:
            sim = compute_jaccard_similarity(item.title, topic)
            if sim > 0.40:
                deduplication_penalty = max(deduplication_penalty, (sim - 0.40) * 50.0)

        final_score = max(0.0, min(100.0, raw_total - deduplication_penalty))

        notes = []
        if deduplication_penalty > 0:
            notes.append(f"Anti-repetition penalty: -{deduplication_penalty:.1f} pts (similarity with recent posts)")
        if score_accessibility >= 85:
            notes.append("High practical accessibility (open code / reproducible weights)")
        if score_recency >= 90:
            notes.append("Fresh publication (< 48h)")

        signals = {
            "source_type": item.source_type,
            "raw_metadata": item.raw_metadata,
            "deduplication_penalty": round(deduplication_penalty, 2),
        }

        return TopicRankingRecord(
            id=rec_id,
            discovered_item_id=item.id,
            total_score=round(final_score, 2),
            score_recency=round(score_recency, 1),
            score_usefulness=round(score_usefulness, 1),
            score_significance=round(score_significance, 1),
            score_accessibility=round(score_accessibility, 1),
            score_credibility=round(score_credibility, 1),
            score_novelty=round(score_novelty, 1),
            signals=signals,
            notes="; ".join(notes) if notes else "Standard technical evaluation passed",
            ranked_at=now.isoformat(),
        )

    def _compute_recency_score(self, published_at_iso: Optional[str], now: datetime) -> float:
        """Applies exponential decay: 100 for today, decaying gradually over 14 days."""
        if not published_at_iso:
            return 70.0
        try:
            clean_iso = published_at_iso.replace("Z", "+00:00")
            pub_date = datetime.fromisoformat(clean_iso)
            if pub_date.tzinfo is None:
                pub_date = pub_date.replace(tzinfo=timezone.utc)
            delta_hours = max(0.0, (now - pub_date).total_seconds() / 3600.0)

            # Half-life of 72 hours (3 days)
            decay = math.exp(-0.693 * (delta_hours / 72.0))
            return max(20.0, min(100.0, 100.0 * decay))
        except Exception:
            return 75.0

    def _compute_usefulness_score(self, item: DiscoveredItemRecord) -> float:
        text = f"{item.title} {item.abstract or ''}".lower()
        score = 65.0

        # Highly practical topics for practicing engineers
        if any(term in text for term in ["vllm", "inference", "quantization", "fine-tuning", "lora", "rag", "deployment", "optimization"]):
            score += 20.0
        if any(term in text for term in ["benchmarks", "latency", "throughput", "memory", "cache", "eval"]):
            score += 10.0
        if "github" in item.source_type or "pagedattention" in text:
            score += 5.0

        return min(100.0, score)

    def _compute_significance_score(self, item: DiscoveredItemRecord) -> float:
        text = f"{item.title} {item.abstract or ''}".lower()
        score = 60.0

        # Architectural or mathematical breakthroughs
        if any(term in text for term in ["attention", "transformer", "diffusion", "latent", "architecture", "mechanics"]):
            score += 15.0
        if any(term in text for term in ["state-of-the-art", "sota", "breakthrough", "scaling law", "speculative"]):
            score += 15.0

        # External signals
        meta = item.raw_metadata or {}
        stars = meta.get("stars", 0)
        upvotes = meta.get("upvotes", 0)
        score_hn = meta.get("score", 0)

        if stars > 5000 or upvotes > 50 or score_hn > 100:
            score += 10.0

        return min(100.0, score)

    def _compute_accessibility_score(self, item: DiscoveredItemRecord) -> float:
        score = 50.0
        if item.source_type == "github" or "github.com" in item.url:
            score += 45.0
        elif item.source_type == "huggingface":
            score += 40.0
        elif item.source_type == "arxiv":
            score += 30.0  # Open access paper, but code may or may not be attached
            if "code" in (item.abstract or "").lower():
                score += 15.0

        return min(100.0, score)

    def _compute_credibility_score(self, item: DiscoveredItemRecord) -> float:
        score = 70.0
        text = f"{item.title} {item.abstract or ''} {item.organization or ''} {item.authors or ''}".lower()

        # Respected AI organizations & universities
        top_labs = ["deepmind", "google", "meta", "berkeley", "stanford", "mit", "cmu", "openai", "anthropic", "microsoft", "hugging face", "deepseek"]
        if any(lab in text for lab in top_labs):
            score += 20.0

        if item.source_type in ("arxiv", "github"):
            score += 10.0

        return min(100.0, score)

    def _compute_novelty_score(self, item: DiscoveredItemRecord, recent_post_topics: List[str]) -> float:
        score = 75.0
        # Check against recent posts
        for past_topic in recent_post_topics:
            sim = compute_jaccard_similarity(item.title, past_topic)
            if sim > 0.50:
                score -= 40.0
                break
            elif sim > 0.30:
                score -= 20.0

        return max(20.0, min(100.0, score))
