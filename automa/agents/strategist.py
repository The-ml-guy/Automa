"""
Agent E: Content Strategist Agent for Automa.
Evaluates research distillations, brainstorms multiple distinct angles,
and selects the optimal narrative angle for each platform without generic AI hype.
"""

from __future__ import annotations
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from automa.agents.base import BaseAgent
from automa.db.repository import (
    PostRepository,
    DiscoveredItemRecord,
    ResearchDistillationRecord,
    ContentAngleRecord,
)

logger = logging.getLogger("automa.agents.strategist")

# Recognized substantive technical angles
TECHNICAL_ANGLES = [
    {
        "type": "technical_insight",
        "name": "Surprising Technical Insight",
        "description": "Counter-intuitive mechanical finding that reframes common assumptions.",
    },
    {
        "type": "developer_bottleneck",
        "name": "Developer Bottleneck Teardown",
        "description": "Focuses on an everyday friction point (e.g. KV cache VRAM exhaustion, slow token latency) and explains the fix.",
    },
    {
        "type": "open_source_spotlight",
        "name": "Open-Source Tooling Spotlight",
        "description": "Examines an accessible open-source codebase, its architecture, and practical reproduction steps.",
    },
    {
        "type": "paper_in_plain_english",
        "name": "Research Paper in Plain English",
        "description": "A zero-jargon breakdown translating theoretical proofs into clear systems concepts.",
    },
    {
        "type": "before_after_comparison",
        "name": "Before-and-After Engineering Comparison",
        "description": "Direct contrast between traditional architecture and the new proposed mechanism.",
    },
    {
        "type": "implementation_guide",
        "name": "Practical Implementation Guide",
        "description": "Concrete code snippet or step-by-step setup showing how engineers can use it today.",
    },
    {
        "type": "benchmark_reality_check",
        "name": "Benchmark With Meaningful Context",
        "description": "Interprets headline numbers with realistic caveats, test conditions, and trade-offs.",
    },
    {
        "type": "discussion_starter",
        "name": "Technical Architecture Debate",
        "description": "Frames an open engineering trade-off to spark high-substance peer discussion.",
    },
]


class ContentStrategistAgent(BaseAgent):
    """
    Develops diverse candidate narrative angles, chooses the highest-substance angle,
    and structures the core thesis for copywriters.
    """

    def __init__(self, repo: Optional[PostRepository] = None):
        super().__init__(
            name="ContentStrategistAgent",
            description="Brainstorms diverse angles and selects the strongest narrative thesis per platform",
        )
        self.repo = repo or PostRepository()

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        item_id = context.get("item_id")
        target_platforms = context.get("platforms", ["linkedin", "x", "instagram"])

        item = self.repo.get_discovered_item_by_id(item_id) if item_id else None
        if not item:
            ranked = self.repo.get_top_ranked_topics(limit=1)
            if ranked:
                item = self.repo.get_discovered_item_by_id(ranked[0]["item_id"])

        if not item:
            return {"success": False, "error": "No discovered item found to strategize."}

        distillation = self.repo.get_research_distillation(item.id)
        results: List[ContentAngleRecord] = []

        for platform in target_platforms:
            strategy = self.determine_strategy(item, distillation, platform)
            self.repo.save_content_angles(strategy)
            results.append(strategy)

        self.logger.info("Content strategy formulated for %d platform(s) on [%s]", len(results), item.title)

        return {
            "success": True,
            "items_processed": len(results),
            "strategies": [s.model_dump() for s in results],
        }

    def determine_strategy(
        self,
        item: DiscoveredItemRecord,
        distillation: Optional[ResearchDistillationRecord],
        target_platform: str,
    ) -> ContentAngleRecord:
        """Evaluates available angles and picks the best one for target platform."""
        now = datetime.now(timezone.utc).isoformat()
        rec_id = f"angle_{uuid.uuid4().hex[:10]}"

        # Candidate angles tailored to the item
        candidates = []
        for angle in TECHNICAL_ANGLES:
            candidates.append({
                "type": angle["type"],
                "name": angle["name"],
                "hook_pitch": self._generate_hook_pitch(angle["type"], item, distillation),
            })

        # Selection logic based on platform strengths and item source type
        selected_type = "developer_bottleneck"
        reasoning = "Focuses on a tangible production bottleneck with a concrete solution."

        if target_platform == "linkedin":
            if item.source_type == "arxiv":
                selected_type = "paper_in_plain_english"
                reasoning = "LinkedIn professional audiences appreciate distilled research translating academic literature to engineering reality."
            elif item.source_type == "github":
                selected_type = "developer_bottleneck"
                reasoning = "Addresses practical software engineering bottlenecks with proven open-source solutions."
            else:
                selected_type = "before_after_comparison"
                reasoning = "Before-and-after contrasts drive high dwell time and bookmarking on LinkedIn."

        elif target_platform == "x":
            if item.source_type == "github":
                selected_type = "open_source_spotlight"
                reasoning = "X developers respond rapidly to lean, open-source repositories solving immediate headaches."
            else:
                selected_type = "technical_insight"
                reasoning = "Punchy, single-concept counter-intuitive insights perform best within 280 characters or short threads."

        elif target_platform == "instagram":
            selected_type = "before_after_comparison"
            reasoning = "Visual architectural flowcharts and side-by-side diagrams communicate clearly on Instagram carousels."

        return ContentAngleRecord(
            id=rec_id,
            discovered_item_id=item.id,
            candidate_angles=candidates,
            selected_angle=selected_type,
            target_platform=target_platform,
            strategy_reasoning=reasoning,
            created_at=now,
        )

    def _generate_hook_pitch(
        self,
        angle_type: str,
        item: DiscoveredItemRecord,
        distillation: Optional[ResearchDistillationRecord],
    ) -> str:
        title = item.title
        problem = distillation.problem if distillation else "memory fragmentation in LLM inference"

        if angle_type == "developer_bottleneck":
            return f"Why {problem[:80]} crashes production deployments, and how this new architecture resolves it."
        elif angle_type == "technical_insight":
            return f"Most developers think model accuracy is the bottleneck. The real constraint is memory bandwidth."
        elif angle_type == "open_source_spotlight":
            return f"Deep dive into {title}: an open-source architecture that solves the KV cache bottleneck."
        elif angle_type == "paper_in_plain_english":
            return f"A new paper explains how to reduce attention memory overhead by up to 90% without losing quality."
        elif angle_type == "before_after_comparison":
            return f"Traditional contiguous memory allocation vs. dynamic page-table memory management in modern LLMs."
        elif angle_type == "benchmark_reality_check":
            return f"Breaking down the claimed throughput improvements: what the benchmarks actually prove."
        else:
            return f"Examining the engineering trade-offs of {title} in distributed production environments."
