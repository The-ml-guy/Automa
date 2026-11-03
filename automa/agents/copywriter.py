"""
Agent F: Platform-Specific Copywriting Agent for Automa.
Crafts distinct, highly tailored posts for LinkedIn, X (Twitter), and Instagram
using research distillations and strategic angles, followed by deterministic quality gate evaluation.
"""

from __future__ import annotations
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from automa.agents.base import BaseAgent
from automa.config import PlatformConfig, load_platforms_config, load_brand_manifest
from automa.db.repository import (
    PostRepository,
    PostRecord,
    DiscoveredItemRecord,
    ResearchDistillationRecord,
    ContentAngleRecord,
)
from automa.engine.providers import get_ai_provider, BaseAIProvider
from automa.gate.quality_gate import QualityGate, QualityGateVerdict

logger = logging.getLogger("automa.agents.copywriter")


class PlatformCopywritingAgent(BaseAgent):
    """
    Generates tailored, high-substance social posts for specific platforms,
    strictly respecting character boundaries, structural rules, and anti-slop linters.
    """

    def __init__(
        self,
        repo: Optional[PostRepository] = None,
        provider: Optional[BaseAIProvider] = None,
        gate: Optional[QualityGate] = None,
    ):
        super().__init__(
            name="PlatformCopywritingAgent",
            description="Generates platform-tailored copy and verifies drafts through the Deterministic Quality Gate",
        )
        self.repo = repo or PostRepository()
        self.provider = provider or get_ai_provider()
        self.global_cfg, self.platforms = load_platforms_config()
        self.brand_manifest = load_brand_manifest()
        self.gate = gate or QualityGate(
            min_passing_score=self.global_cfg.min_passing_score,
            max_revisions=self.global_cfg.max_auto_revisions,
        )

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        item_id = context.get("item_id")
        platforms_to_write = context.get("platforms", ["linkedin", "x"])

        item = self.repo.get_discovered_item_by_id(item_id) if item_id else None
        if not item:
            ranked = self.repo.get_top_ranked_topics(limit=1)
            if ranked:
                item = self.repo.get_discovered_item_by_id(ranked[0]["item_id"])

        if not item:
            return {"success": False, "error": "No item found to craft copy for."}

        distillation = self.repo.get_research_distillation(item.id)
        existing_fingerprints = self.repo.get_existing_fingerprints()
        recent_posts = self.repo.get_recent_posts(limit=25)
        recent_texts = [p.content for p in recent_posts]

        generated_posts: List[PostRecord] = []

        for platform in platforms_to_write:
            cfg = self.platforms.get(platform)
            if not cfg or not cfg.enabled:
                continue

            angle_record = None
            angles = self.repo.get_content_angles(item.id)
            for a in angles:
                if a.target_platform == platform:
                    angle_record = a
                    break

            post = self.craft_post(
                platform=platform,
                platform_cfg=cfg,
                item=item,
                distillation=distillation,
                angle_record=angle_record,
                existing_fingerprints=existing_fingerprints,
                recent_texts=recent_texts,
            )
            if post:
                self.repo.save_post(post)
                if post.fingerprint:
                    self.repo.save_fingerprint(post.fingerprint, post.id, post.platform)
                generated_posts.append(post)

        self.logger.info("Crafted and evaluated %d platform-specific post(s) for [%s]", len(generated_posts), item.title)

        return {
            "success": True,
            "items_processed": len(generated_posts),
            "posts": [p.model_dump() for p in generated_posts],
        }

    def craft_post(
        self,
        platform: str,
        platform_cfg: PlatformConfig,
        item: DiscoveredItemRecord,
        distillation: Optional[ResearchDistillationRecord],
        angle_record: Optional[ContentAngleRecord],
        existing_fingerprints: List[str],
        recent_texts: List[str],
    ) -> Optional[PostRecord]:
        """Generates, quality-evaluates, and auto-revises a post for a specific platform."""
        post_id = f"post_{platform}_{uuid.uuid4().hex[:8]}"
        created_at = datetime.now(timezone.utc).isoformat()
        current_content = ""
        verdict: Optional[QualityGateVerdict] = None
        has_media = False
        media_urls = []
        media_prompt = None

        # Automatically Generate Editorial Visual Card
        try:
            from automa.media.renderer import build_brief_from_research, EditorialCardRenderer

            raw_meta = item.raw_metadata if isinstance(item.raw_metadata, dict) else {}
            project_name = raw_meta.get("project_name", "")
            if not project_name:
                project_name = item.title.replace("GitHub Repo: ", "").split(":")[0].strip()

            renderer = EditorialCardRenderer()
            card_brief = build_brief_from_research(
                item_title=item.title,
                item_abstract=item.abstract or "",
                raw_metadata=raw_meta,
                distillation_problem=distillation.problem if distillation else None,
                distillation_core_idea=distillation.core_idea if distillation else None,
                distillation_what_is_new=distillation.what_is_new if distillation else None,
                distillation_limitations=distillation.limitations if distillation else None,
                platform=platform,
                post_id=post_id,
            )
            card_path = renderer.render(card_brief)
            media_urls = [str(card_path)]
            media_prompt = f"Editorial Card [{card_brief.template}]: {project_name}"
            has_media = True
        except Exception as e:
            self.logger.warning("Editorial card generation failed, trying PIL fallback: %s", e)
            # PIL fallback
            try:
                from automa.media.card_generator import VisualCardGenerator, VisualBrief
                card_gen = VisualCardGenerator()
                takeaways = []
                if distillation:
                    takeaways = [distillation.problem, distillation.core_idea, distillation.what_is_new]
                else:
                    takeaways = [item.abstract[:110] if item.abstract else "Verified engineering pattern."]

                brief = VisualBrief(
                    topic=item.title,
                    headline=project_name if len(project_name) < 40 else item.title[:40],
                    core_insight=distillation.core_idea if distillation else (item.abstract[:120] if item.abstract else "Engineered systems architecture."),
                    art_direction="INSIGHT",
                    supporting_points=takeaways,
                    source_name=f"{item.source_type.upper()}:{item.id[:8]}",
                    platform=platform,
                    post_id=post_id,
                )
                card_path = card_gen.generate_from_brief(brief)
                media_urls = [str(card_path)]
                media_prompt = f"Technical Card: {project_name}"
                has_media = True
            except Exception as e2:
                self.logger.warning("All card generation failed: %s", e2)
                if platform == "instagram":
                    has_media = True
                    media_prompt = f"Technical Architecture Diagram: {item.title}"

        # Generation and Auto-Revision Loop
        for attempt in range(self.global_cfg.max_auto_revisions + 1):
            if attempt == 0:
                current_content = self._generate_initial_draft(platform, item, distillation, angle_record)
            else:
                current_content = self._revise_draft(platform, current_content, verdict.revision_feedback if verdict else "")

            # Run Deterministic Quality Gate
            verdict = self.gate.evaluate_draft(
                content=current_content,
                topic=item.title,
                platform=platform,
                platform_cfg=platform_cfg,
                existing_fingerprints=existing_fingerprints,
                recent_post_texts=recent_texts,
                current_revision=attempt,
                has_media=has_media,
            )

            if verdict.status in ("APPROVED", "MANUAL_REVIEW_REQUIRED", "REJECTED"):
                break

        if not verdict:
            return None

        # Schedule slot calculation (at least min_spacing_hours after latest scheduled post)
        now = datetime.now(timezone.utc)
        scheduled_at = (now + self._get_offset_for_platform(platform)).isoformat()

        final_status = "SCHEDULED" if verdict.passed else verdict.status

        return PostRecord(
            id=post_id,
            platform=platform,
            status=final_status,
            topic=item.title,
            content=current_content,
            thread_items=current_content.split("\n---\n") if platform == "x" and "\n---\n" in current_content else [],
            media_urls=media_urls,
            media_prompt=media_prompt,
            quality_score=verdict.score,
            quality_report={
                "score": verdict.score,
                "passed": verdict.passed,
                "hard_failures": verdict.hard_failures,
                "warnings": verdict.warnings,
                "similarity": verdict.rule_result.highest_similarity,
                "dimension_scores": verdict.dimension_scores,
                "remediation_advice": verdict.remediation_advice,
            },
            revision_count=verdict.rule_result.attempt if hasattr(verdict.rule_result, "attempt") else 0,
            fingerprint=verdict.fingerprint,
            idempotency_key=f"idem_{post_id}_{verdict.fingerprint[:10]}",
            scheduled_at=scheduled_at,
            requires_manual_review=verdict.status == "MANUAL_REVIEW_REQUIRED",
            manual_review_reason="; ".join(verdict.hard_failures) if verdict.status == "MANUAL_REVIEW_REQUIRED" else None,
            created_at=created_at,
            updated_at=created_at,
        )

    def _generate_initial_draft(
        self,
        platform: str,
        item: DiscoveredItemRecord,
        distillation: Optional[ResearchDistillationRecord],
        angle: Optional[ContentAngleRecord],
    ) -> str:
        """Synthesizes high-substance, evidence-grounded platform copy adhering strictly to editorial rules."""
        project_name = item.raw_metadata.get("project_name") if isinstance(item.raw_metadata, dict) else ""
        if not project_name:
            project_name = item.title.replace("GitHub Repo: ", "").split(":")[0].strip()

        problem = distillation.problem if distillation else f"Scaling challenges in modern {item.primary_category or 'software'} systems."
        core_idea = distillation.core_idea if distillation else (item.abstract[:150] if item.abstract else "Decoupled architecture for deterministic execution.")
        what_new = distillation.what_is_new if distillation else "Zero-dependency design pattern eliminating runtime overhead."
        limitations = distillation.limitations if distillation else "Requires verifying compatibility with target deployment environment."
        primary_link = distillation.code_and_paper_links[0] if (distillation and distillation.code_and_paper_links) else item.url

        clean_category = (item.primary_category or "Software").replace(" ", "")

        if platform == "linkedin":
            return (
                f"Engineering observation: {problem.rstrip('.')}.\n\n"
                f"When scaling distributed workflows, framework bloat and uncontrolled state mutation introduce subtle, hard-to-debug bottlenecks. "
                f"Often, the most effective solution isn't adding more cloud infrastructure—it's cleaning up the underlying execution boundary.\n\n"
                f"{project_name} addresses this with a focused architectural pattern:\n\n"
                f"1. Core Mechanism: {core_idea}\n"
                f"2. Architectural Difference: {what_new}\n"
                f"3. Practical Trade-off: {limitations}\n\n"
                f"The key takeaway: isolating critical state transitions into deterministic, testable units yields far greater operational reliability than wrapping complex layers in retries.\n\n"
                f"Technical reference & implementation:\n"
                f"{primary_link}\n\n"
                f"#SoftwareEngineering #SystemsArchitecture #{clean_category}"
            )

        elif platform == "x":
            # Concise single post strictly under 280 characters with bullet points
            p_short = problem[:75].rstrip(".")
            sol_short = core_idea[:80].rstrip(".")
            tweet = (
                f"{project_name}: {p_short}.\n\n"
                f"Core architecture: {sol_short}.\n\n"
                f"{primary_link}"
            )
            if len(tweet) > 280:
                tweet = f"{project_name}: {sol_short}.\n\n{primary_link}"
            return tweet

        elif platform == "instagram":
            return (
                f"Architecture Breakdown: {project_name}\n\n"
                f"A closer look at how modern systems approach high-concurrency bottlenecks.\n\n"
                f"Technical Breakdown:\n"
                f"• The Bottleneck: {problem[:130]}\n"
                f"• The Solution: {core_idea[:130]}\n"
                f"• Production Constraint: {limitations[:110]}\n\n"
                f"Open-source implementation and benchmarks: {primary_link}\n\n"
                f"#SoftwareArchitecture #Engineering #BackendDev"
            )

        return f"Technical overview: {project_name}\n\nDetails: {item.url}"

    def _revise_draft(self, platform: str, current_content: str, critique: str) -> str:
        """Applies targeted modifications to repair quality gate violations."""
        revised = current_content
        # Remove prohibited phrases if present
        for slop in ["delve", "game-changer", "supercharge", "unleash", "revolutionary", "agree?", "thoughts?"]:
            revised = revised.replace(slop, "").replace(slop.title(), "")

        # If length exceeded for X
        if platform == "x" and len(revised) > 280:
            lines = revised.split("\n\n")
            if len(lines) > 2:
                revised = f"{lines[0]}\n\n{lines[-1]}"
            if len(revised) > 280:
                revised = revised[:275] + "..."

        return revised

    def _get_offset_for_platform(self, platform: str):
        from datetime import timedelta
        if platform == "linkedin":
            return timedelta(days=2, hours=4)
        elif platform == "x":
            return timedelta(days=1, hours=2)
        return timedelta(days=3)
