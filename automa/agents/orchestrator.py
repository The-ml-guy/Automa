"""
Multi-Agent Content Intelligence Pipeline Orchestrator for Automa.
Coordinates Agent A (Discovery), Agent B (Verification), Agent C (Ranking),
Agent D (Simplification), Agent E (Strategy), and Agent F (Copywriting) into an integrated workflow.
"""

from __future__ import annotations
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from automa.agents.discovery import ResearchDiscoveryAgent
from automa.agents.verification import SourceVerificationAgent
from automa.agents.ranking import TopicRankingAgent
from automa.agents.simplification import ResearchSimplificationAgent
from automa.agents.strategist import ContentStrategistAgent
from automa.agents.copywriter import PlatformCopywritingAgent
from automa.db.repository import PostRepository, DiscoveredItemRecord, PostRecord

logger = logging.getLogger("automa.agents.orchestrator")


class ContentIntelligencePipeline:
    """
    End-to-End Orchestrator running the complete autonomous multi-agent pipeline:
    Discover -> Verify -> Rank -> Simplify -> Strategize -> Copywrite & Lint -> Queue.
    """

    def __init__(self, repo: Optional[PostRepository] = None):
        self.repo = repo or PostRepository()
        self.discovery_agent = ResearchDiscoveryAgent(repo=self.repo)
        self.verification_agent = SourceVerificationAgent(repo=self.repo)
        self.ranking_agent = TopicRankingAgent(repo=self.repo)
        self.simplification_agent = ResearchSimplificationAgent(repo=self.repo)
        self.strategist_agent = ContentStrategistAgent(repo=self.repo)
        self.copywriter_agent = PlatformCopywritingAgent(repo=self.repo)

    def run_full_pipeline(
        self,
        discovery_limit_per_source: int = 5,
        target_platforms: Optional[List[str]] = None,
        top_k_topics: int = 1,
    ) -> Dict[str, Any]:
        """
        Executes the entire multi-agent intelligence cycle end-to-end.
        Returns detailed execution report and all created post records.
        """
        platforms = target_platforms or ["linkedin", "x", "instagram"]
        run_id = f"pipeline_{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()
        logger.info(">>> Starting Content Intelligence Pipeline Run [%s] <<<", run_id)

        # Step 1: Agent A — Discover
        logger.info("[Step 1/6] Running Research Discovery Agent...")
        disc_res = self.discovery_agent.execute({"limit_per_source": discovery_limit_per_source})

        # Step 2: Agent B — Verify
        logger.info("[Step 2/6] Running Source Verification Agent...")
        verif_res = self.verification_agent.execute({"limit": 15})

        # Step 3: Agent C — Rank & Score
        logger.info("[Step 3/6] Running Topic Ranking and Trend Agent...")
        rank_res = self.ranking_agent.execute({"limit": 25})

        top_candidates = rank_res.get("top_candidates", [])
        recent_posts = self.repo.get_recent_posts(limit=30)
        recent_topics = [p.topic.lower() for p in recent_posts]

        top_item = None
        top_score = 75.0

        # Select highest-ranked candidate that has not been posted recently
        for cand in top_candidates:
            cid = cand.get("discovered_item_id")
            if not cid:
                continue
            item_cand = self.repo.get_discovered_item_by_id(cid)
            if item_cand and item_cand.title.lower() not in recent_topics:
                top_item = item_cand
                top_score = cand.get("total_score", 75.0)
                break

        if not top_item:
            # Fallback to any discovered items not posted recently
            items = self.repo.get_discovered_items(limit=10)
            for itm in items:
                if itm.title.lower() not in recent_topics:
                    top_item = itm
                    break
            if not top_item and items:
                top_item = items[0]

        if not top_item:
            return {
                "success": False,
                "pipeline_run_id": run_id,
                "error": "No fresh items available in intelligence database to process.",
            }

        logger.info("Selected Top Ranked Topic: [%s] (Score: %.1f/100)", top_item.title, top_score)

        # Step 4: Agent D — Research Simplification (7-Question Framework)
        logger.info("[Step 4/6] Running Research Simplification Agent...")
        simp_res = self.simplification_agent.execute({"item_id": top_item.id})

        # Step 5: Agent E — Content Strategy & Angles
        logger.info("[Step 5/6] Running Content Strategist Agent...")
        strat_res = self.strategist_agent.execute({"item_id": top_item.id, "platforms": platforms})

        # Step 6: Agent F — Platform Copywriting & Quality Gate
        logger.info("[Step 6/6] Running Platform-Specific Copywriting Agent...")
        copy_res = self.copywriter_agent.execute({"item_id": top_item.id, "platforms": platforms})

        posts_scheduled = [p for p in copy_res.get("posts", []) if p.get("status") == "SCHEDULED"]
        posts_flagged = [p for p in copy_res.get("posts", []) if p.get("status") == "MANUAL_REVIEW_REQUIRED"]

        # Audit log entry
        self.repo.log_audit_event(
            event_type="PIPELINE_RUN_COMPLETED",
            post_id=posts_scheduled[0]["id"] if posts_scheduled else None,
            details=f"Pipeline {run_id} scheduled {len(posts_scheduled)} posts on topic: {top_item.title}",
        )

        logger.info(
            ">>> Pipeline Completed Successfully: %d Scheduled, %d Flagged for Review <<<",
            len(posts_scheduled),
            len(posts_flagged),
        )

        return {
            "success": True,
            "pipeline_run_id": run_id,
            "topic_chosen": top_item.title,
            "source_url": top_item.url,
            "topic_score": top_score,
            "steps": {
                "discovery": disc_res,
                "verification": verif_res,
                "ranking": rank_res,
                "simplification": simp_res,
                "strategy": strat_res,
                "copywriting": copy_res,
            },
            "posts_created": copy_res.get("posts", []),
            "posts_scheduled_count": len(posts_scheduled),
            "posts_review_count": len(posts_flagged),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
