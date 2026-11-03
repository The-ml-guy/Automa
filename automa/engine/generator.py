"""
Autonomous Content Engine Orchestrator for Automa (Phases 3, 4, 5, 6, 7).
Selects topics, drafts platform-specific content, drives deterministic quality gate
and auto-revisions, and assigns conservative schedule slots.
"""

from __future__ import annotations
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from automa.config import (
    load_brand_manifest,
    load_platforms_config,
    load_knowledge_base,
    get_settings,
    PlatformConfig,
    CONTENT_DIR,
)
from automa.db.repository import PostRepository, PostRecord
from automa.engine.providers import get_ai_provider, BaseAIProvider
from automa.gate.quality_gate import QualityGate, QualityGateVerdict

logger = logging.getLogger("automa.engine.generator")


class ContentEngine:
    def __init__(self, repo: Optional[PostRepository] = None, provider: Optional[BaseAIProvider] = None):
        self.repo = repo or PostRepository()
        self.provider = provider or get_ai_provider()
        self.settings = get_settings()
        self.global_cfg, self.platforms = load_platforms_config()
        self.brand_manifest = load_brand_manifest()
        self.knowledge = load_knowledge_base()
        self.gate = QualityGate(
            min_passing_score=self.global_cfg.min_passing_score,
            max_revisions=self.global_cfg.max_auto_revisions,
        )

    def _select_topic(self, recent_posts: List[PostRecord]) -> Optional[Tuple[str, str]]:
        """
        Picks a fresh, useful, defensible engineering topic from intelligence rankings
        or brand knowledge base that has not been recently scheduled.
        Returns (topic_name, topic_context) or None if no fresh topic is available.
        """
        recent_topics = [p.topic.lower() for p in recent_posts[:15]]

        # 1. Prioritize live multi-agent intelligence rankings if available
        ranked_topics = self.repo.get_top_ranked_topics(limit=10)
        for r in ranked_topics:
            title = r.get("title", "")
            if title and title.lower() not in recent_topics:
                distillation = self.repo.get_research_distillation(r.get("item_id", ""))
                context = (
                    f"AI Intelligence ({r.get('source_type', '').upper()}) Score: {r.get('total_score', 0)}/100. "
                    f"Abstract: {r.get('abstract', '')[:200]}... "
                    f"Core Idea: {distillation.core_idea if distillation else 'Systems-level breakthrough'}."
                )
                return title, context

        candidate_topics = [
            (
                "Assistive Edge AI with Project Lighthouse",
                "Project: PROJ-003 (Assistive Computer Vision, AWS YOLOv8 training, ONNX/TFLite edge quantization, Flutter TTS dialogue).",
            ),
            (
                "Machine Learning Algorithms From Scratch in Python",
                "Project: PROJ-004 (100projects: 100+ modular ML algorithms from scratch in pure Python, vectorization mechanics, avoiding framework bloat).",
            ),
            (
                "Cron Schedulers vs Persistent State Machines",
                "Experiences: EXP-001 (Cron job overlap, concurrent locks, heartbeats) and Opinions: OPIN-003.",
            ),
            (
                "High-Performance SQLite WAL Concurrency",
                "Experiences: EXP-002 (WAL mode, busy_timeout, read/write concurrency) and Code Snippet: EX-002.",
            ),
            (
                "Idempotent Webhook Consumer Architecture",
                "Experiences: EXP-003 (At-least-once delivery, unique constraints, duplicate prevention) and Snippet: EX-003.",
            ),
            (
                "Exponential Backoff With Full Jitter",
                "Snippet: EX-001 and Sources: SRC-002 (Thundering herd prevention in distributed APIs).",
            ),
            (
                "Deterministic Quality Gates in AI Pipelines",
                "Opinions: OPIN-002 (Why models shouldn't grade themselves; pairing stochastic LLMs with regex and lint checks).",
            ),
        ]

        for topic_name, context in candidate_topics:
            if topic_name.lower() not in recent_topics:
                return topic_name, context

        # If all recent candidates have been posted recently, return the least recent one
        return candidate_topics[0]

    def _calculate_next_schedule_time(self, platform: str, platform_cfg: PlatformConfig, recent_posts: List[PostRecord]) -> datetime:
        """
        Calculates the next appropriate scheduled time based on platform spacing and preferred hours.
        Enforces minimum spacing between posts on the same platform and conservative weekly limits.
        """
        now = datetime.now(timezone.utc)
        min_spacing_hours = platform_cfg.min_spacing_hours

        # Find latest scheduled or published post on this platform
        latest_time = now
        for p in recent_posts:
            if p.platform == platform and p.scheduled_at:
                try:
                    p_time = datetime.fromisoformat(p.scheduled_at)
                    if p_time > latest_time:
                        latest_time = p_time
                except Exception:
                    pass

        # Candidate is at least min_spacing_hours after latest scheduled post
        target_time = max(now + timedelta(hours=2), latest_time + timedelta(hours=min_spacing_hours))

        # Align to preferred UTC time if available
        if platform_cfg.preferred_times_utc:
            pref_hour, pref_minute = map(int, platform_cfg.preferred_times_utc[0].split(":"))
            candidate = target_time.replace(hour=pref_hour, minute=pref_minute, second=0, microsecond=0)
            if candidate < target_time:
                candidate += timedelta(days=1)
            target_time = candidate

        return target_time

    def _build_generation_prompt(self, platform: str, topic: str, topic_context: str, revision_critique: Optional[str] = None) -> str:
        """Constructs an anti-slop, platform-specific generation prompt."""
        p_cfg = self.platforms.get(platform)
        style = p_cfg.style_guidelines.structure if p_cfg else ""

        prompt = f"""
You are writing an original, highly substantive post for the following platform:
PLATFORM: {platform.upper()}

TOPIC: {topic}
VERIFIED KNOWLEDGE & CONTEXT:
{topic_context}

STYLE INSTRUCTIONS FOR {platform.upper()}:
{style}

MANDATORY EDITORIAL STANDARDS:
- Lead directly with a concrete technical observation or practical lesson. No clickbait hooks.
- Provide a clear, defensible explanation or architecture breakdown.
- Do NOT use generic buzzwords (NO: 'delve', 'game-changer', 'testament', 'skyrocket', 'buckle up', 'revolutionize', 'supercharge', 'unleash', 'in today's fast-paced world').
- Do NOT invent personal stories, client revenue claims, or fake statistics.
- Limit emojis to at most 1 or 2.
- Limit hashtags to at most 2 or 3 relevant technical tags.
"""
        if revision_critique:
            prompt += f"""
PREVIOUS DRAFT CRITIQUE (You MUST fix these issues):
{revision_critique}
"""
        return prompt

    def generate_post_for_platform(
        self,
        platform: str,
        topic: str,
        topic_context: str,
        existing_fingerprints: List[str],
        recent_texts: List[str],
    ) -> Optional[PostRecord]:
        """
        Generates, validates, and refines a post for a specific platform.
        Runs auto-revision up to 2 times if the quality gate rejects it.
        """
        platform_cfg = self.platforms.get(platform)
        if not platform_cfg or not platform_cfg.enabled:
            return None

        post_id = f"post_{platform}_{uuid.uuid4().hex[:8]}"
        created_at = datetime.now(timezone.utc).isoformat()
        revision_critique: Optional[str] = None
        verdict: Optional[QualityGateVerdict] = None
        current_content = ""
        media_urls = []
        media_prompt = None

        # Generate editorial visual card for ALL platforms
        has_media = False
        try:
            from automa.media.renderer import build_brief_from_research, EditorialCardRenderer
            renderer = EditorialCardRenderer()

            # Get distillation if available
            item = None
            ranked = self.repo.get_top_ranked_topics(limit=1)
            if ranked:
                item = self.repo.get_discovered_item_by_id(ranked[0].get("item_id", ""))
            distillation = self.repo.get_research_distillation(ranked[0].get("item_id", "")) if ranked else None

            raw_meta = item.raw_metadata if (item and isinstance(item.raw_metadata, dict)) else {}

            card_brief = build_brief_from_research(
                item_title=topic,
                item_abstract=topic_context[:300],
                raw_metadata=raw_meta,
                distillation_problem=distillation.problem if distillation else None,
                distillation_core_idea=distillation.core_idea if distillation else topic_context[:200],
                distillation_what_is_new=distillation.what_is_new if distillation else None,
                distillation_limitations=distillation.limitations if distillation else None,
                platform=platform,
                post_id=post_id,
            )
            card_path = renderer.render(card_brief)
            media_urls = [str(card_path)]
            media_prompt = f"Editorial Card [{card_brief.template}]: {topic}"
            has_media = True
            logger.info("Generated editorial card for %s: %s", platform, card_path)
        except Exception as e:
            logger.warning("Editorial renderer failed for %s, trying PIL fallback: %s", platform, e)
            try:
                from automa.media.card_generator import VisualCardGenerator, extract_key_takeaways
                card_gen = VisualCardGenerator()
                takeaways = extract_key_takeaways("", topic, topic_context)
                card_path = card_gen.generate_card(
                    topic=topic,
                    category="ENGINEERING INSIGHT",
                    takeaways=takeaways,
                    platform=platform,
                    post_id=post_id,
                )
                media_urls = [str(card_path)]
                media_prompt = f"Technical Card: {topic}"
                has_media = True
            except Exception as e2:
                logger.warning("All card generation failed for %s: %s", platform, e2)
                if platform == "instagram":
                    media_prompt = f"Architecture Diagram: {topic}"
                    has_media = True

        # Generation and auto-revision loop (up to max_auto_revisions attempts)
        for attempt in range(self.global_cfg.max_auto_revisions + 1):
            prompt = self._build_generation_prompt(platform, topic, topic_context, revision_critique)
            system_instruction = (
                f"You are a Senior Systems Architect writing for your personal brand. "
                f"Strictly adhere to the brand manifest: {self.brand_manifest[:500]}... "
                f"Prioritize clarity, technical rigor, and zero fluff."
            )

            current_content = self.provider.generate_text(prompt, system_instruction=system_instruction)

            # Evaluate with Deterministic Quality Gate
            verdict = self.gate.evaluate_draft(
                content=current_content,
                topic=topic,
                platform=platform,
                platform_cfg=platform_cfg,
                existing_fingerprints=existing_fingerprints,
                recent_post_texts=recent_texts,
                current_revision=attempt,
                has_media=has_media,
            )

            if verdict.status in ("APPROVED", "MANUAL_REVIEW_REQUIRED", "REJECTED"):
                break
            elif verdict.status == "REVISE":
                logger.info("Draft for %s required revision (Attempt %d): %s", platform, attempt + 1, verdict.revision_feedback)
                revision_critique = verdict.revision_feedback

        if not verdict:
            return None

        # Re-render card with finalized content if possible
        if has_media and current_content:
            try:
                from automa.media.card_generator import VisualCardGenerator, extract_key_takeaways
                card_gen = VisualCardGenerator()
                takeaways = extract_key_takeaways(current_content, topic, topic_context)
                card_path = card_gen.generate_card(
                    topic=topic,
                    category="ENGINEERING INSIGHT",
                    takeaways=takeaways,
                    platform=platform,
                    post_id=post_id,
                )
                media_urls = [str(card_path)]
            except Exception as e:
                logger.warning("Refining card with final content failed: %s", e)

        # Handle X threads if content has multiple tweet markers
        thread_items = []
        if platform == "x" and "\n---\n" in current_content:
            thread_items = [t.strip() for t in current_content.split("\n---\n") if t.strip()]

        # Determine target schedule time
        recent_posts = self.repo.get_recent_posts(limit=20)
        target_schedule_time = self._calculate_next_schedule_time(platform, platform_cfg, recent_posts)

        # Map quality status to persistent queue status
        final_status = "SCHEDULED" if verdict.passed else verdict.status

        post_record = PostRecord(
            id=post_id,
            platform=platform,
            status=final_status,
            topic=topic,
            content=current_content,
            thread_items=thread_items,
            media_urls=media_urls,
            media_prompt=media_prompt,
            quality_score=verdict.score,
            quality_report={
                "score": verdict.score,
                "passed": verdict.passed,
                "hard_failures": verdict.hard_failures,
                "warnings": verdict.warnings,
                "emoji_count": verdict.rule_result.emoji_count,
                "hashtag_count": verdict.rule_result.hashtag_count,
                "similarity": verdict.rule_result.highest_similarity,
                "dimension_scores": verdict.dimension_scores,
                "remediation_advice": verdict.remediation_advice,
            },
            revision_count=verdict.rule_result.errors and attempt or 0,
            fingerprint=verdict.fingerprint,
            idempotency_key=f"idemp_{post_id}_{verdict.fingerprint[:12]}",
            scheduled_at=target_schedule_time.isoformat() if final_status == "SCHEDULED" else None,
            requires_manual_review=verdict.status == "MANUAL_REVIEW_REQUIRED",
            manual_review_reason=verdict.safety_result.reason,
            created_at=created_at,
            updated_at=created_at,
        )

        # Save to SQLite repository
        self.repo.save_post(post_record)
        self.repo.log_audit_event(
            event_type=f"POST_{final_status}",
            post_id=post_id,
            details=f"Platform: {platform}, Topic: {topic}, Score: {verdict.score}, Status: {final_status}",
        )

        # Save rejected or approved payload file
        if final_status == "REJECTED":
            rej_path = CONTENT_DIR / "rejected" / f"{post_id}.json"
            with open(rej_path, "w", encoding="utf-8") as f:
                f.write(post_record.model_dump_json(indent=2))

        return post_record

    def run_scheduled_generation(self, force: bool = False) -> Dict[str, Any]:
        """
        Executes a scheduled generation run across all enabled platforms.
        Enforces conservative weekly limits and skips run if appropriate.
        """
        run_id = f"gen_run_{uuid.uuid4().hex[:8]}"
        start_time = datetime.now(timezone.utc).isoformat()
        logger.info("Starting content generation run %s (force=%s)", run_id, force)

        recent_posts = self.repo.get_recent_posts(limit=50)

        # Check weekly cap
        one_week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        posts_last_week = [p for p in recent_posts if p.created_at >= one_week_ago and p.status in ("SCHEDULED", "PUBLISHED")]
        if not force and len(posts_last_week) >= self.global_cfg.conservative_weekly_cap:
            reason = f"Weekly publishing cap reached ({len(posts_last_week)}/{self.global_cfg.conservative_weekly_cap} posts this week). Skipping generation."
            logger.info(reason)
            self.repo.record_generation_run(
                run_id=run_id,
                started_at=start_time,
                completed_at=datetime.now(timezone.utc).isoformat(),
                status="SKIPPED",
                topic_chosen="N/A",
                reason=reason,
                posts_generated=0,
                posts_scheduled=0,
                details={"weekly_count": len(posts_last_week)},
            )
            return {"status": "SKIPPED", "reason": reason}

        # 1. Primary Path: Execute End-to-End Multi-Agent Content Intelligence Pipeline
        try:
            from automa.agents.orchestrator import ContentIntelligencePipeline
            pipeline = ContentIntelligencePipeline(repo=self.repo)
            enabled_platforms = [p for p, cfg in self.platforms.items() if cfg.enabled]
            pipe_res = pipeline.run_full_pipeline(
                discovery_limit_per_source=3,
                target_platforms=enabled_platforms or ["linkedin", "x", "instagram"],
            )
            if pipe_res.get("success") and pipe_res.get("posts_created"):
                posts = pipe_res.get("posts_created", [])
                sched_cnt = pipe_res.get("posts_scheduled_count", 0)
                status_str = "SUCCESS" if sched_cnt > 0 else "PARTIAL"
                self.repo.record_generation_run(
                    run_id=run_id,
                    started_at=start_time,
                    completed_at=datetime.now(timezone.utc).isoformat(),
                    status=status_str,
                    topic_chosen=pipe_res.get("topic_chosen", "Multi-Agent Discovery"),
                    reason=None,
                    posts_generated=len(posts),
                    posts_scheduled=sched_cnt,
                    details=pipe_res.get("steps", {}),
                )
                return {
                    "status": status_str,
                    "topic": pipe_res.get("topic_chosen"),
                    "generated_count": len(posts),
                    "scheduled_count": sched_cnt,
                    "posts": posts,
                    "pipeline_run_id": pipe_res.get("pipeline_run_id"),
                }
        except Exception as e:
            logger.warning("Multi-agent intelligence pipeline run failed, falling back to local generator: %s", e)

        # 2. Fallback Path: Local Content Selection & Generation
        topic_info = self._select_topic(recent_posts)
        if not topic_info:
            reason = "No sufficiently good, defensible idea available in knowledge base. Skipping slot per editorial standards."
            logger.info(reason)
            self.repo.record_generation_run(
                run_id=run_id,
                started_at=start_time,
                completed_at=datetime.now(timezone.utc).isoformat(),
                status="SKIPPED",
                topic_chosen="N/A",
                reason=reason,
                posts_generated=0,
                posts_scheduled=0,
                details={},
            )
            return {"status": "SKIPPED", "reason": reason}

        topic_name, topic_context = topic_info
        existing_fingerprints = [p.fingerprint for p in recent_posts]
        recent_texts = [p.content for p in recent_posts[:20]]

        generated_posts = []
        scheduled_count = 0

        # Generate separate, tailored versions for each platform
        for platform_name, p_cfg in self.platforms.items():
            if not p_cfg.enabled:
                continue
            post = self.generate_post_for_platform(
                platform=platform_name,
                topic=topic_name,
                topic_context=topic_context,
                existing_fingerprints=existing_fingerprints,
                recent_texts=recent_texts,
            )
            if post:
                generated_posts.append(post)
                if post.status == "SCHEDULED":
                    scheduled_count += 1
                existing_fingerprints.append(post.fingerprint)
                recent_texts.append(post.content)

        completion_time = datetime.now(timezone.utc).isoformat()
        status = "SUCCESS" if scheduled_count > 0 else "PARTIAL"

        self.repo.record_generation_run(
            run_id=run_id,
            started_at=start_time,
            completed_at=completion_time,
            status=status,
            topic_chosen=topic_name,
            reason=f"Generated {len(generated_posts)} platform drafts, scheduled {scheduled_count}.",
            posts_generated=len(generated_posts),
            posts_scheduled=scheduled_count,
            details={"post_ids": [p.id for p in generated_posts]},
        )

        return {
            "run_id": run_id,
            "status": status,
            "topic": topic_name,
            "generated_count": len(generated_posts),
            "scheduled_count": scheduled_count,
            "posts": [p.model_dump() for p in generated_posts],
        }
