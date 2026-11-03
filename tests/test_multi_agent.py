"""
Unit and Integration Tests for Automa Multi-Agent Content Intelligence System.
Tests Agent A (Discovery), Agent B (Verification), Agent C (Ranking),
Agent D (Simplification), Agent E (Strategy), Agent F (Copywriting), and the Pipeline Orchestrator.
"""

import pytest
import tempfile
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

from automa.db.schema import init_db
from automa.db.repository import (
    PostRepository,
    DiscoveredItemRecord,
    VerifiedSourceRecord,
    TopicRankingRecord,
    ResearchDistillationRecord,
    ContentAngleRecord,
)
from automa.agents.discovery import ResearchDiscoveryAgent
from automa.agents.verification import SourceVerificationAgent
from automa.agents.ranking import TopicRankingAgent, ScoringWeights
from automa.agents.simplification import ResearchSimplificationAgent
from automa.agents.strategist import ContentStrategistAgent
from automa.agents.copywriter import PlatformCopywritingAgent
from automa.agents.orchestrator import ContentIntelligencePipeline


@pytest.fixture
def temp_repo(tmp_path):
    db_file = tmp_path / "test_intel.db"
    init_db(db_file)
    return PostRepository(db_path=db_file)


def test_discovery_agent_fallback_and_save(temp_repo):
    """Verifies that Agent A saves discovered items and falls back safely to curated breakthroughs."""
    agent = ResearchDiscoveryAgent(repo=temp_repo, timeout_seconds=1)
    # Query with empty sources to test fallback insertion
    res = agent.execute({"sources": []})

    assert res["success"] is True
    items = temp_repo.get_discovered_items()
    assert len(items) >= 3
    assert any("vllm" in i.title.lower() for i in items)


def test_verification_agent_factual_and_hype_flags(temp_repo):
    """Verifies that Agent B detects sensationalized claims and isolates verified facts."""
    agent_b = SourceVerificationAgent(repo=temp_repo)

    # Item with clean factual content
    clean_item = DiscoveredItemRecord(
        id="item_clean",
        title="PagedAttention: Virtual Memory Paging for KV Cache Management",
        url="https://arxiv.org/abs/2309.06180",
        source_type="arxiv",
        abstract="Introduces paged memory management for Key-Value caches in LLM serving to reduce fragmentation.",
        discovered_at=datetime.now(timezone.utc).isoformat(),
    )
    temp_repo.save_discovered_item(clean_item)

    # Item with sensationalized clickbait hype
    hype_item = DiscoveredItemRecord(
        id="item_hype",
        title="New Model Destroys All Other AI with 100x Faster Performance and Human-Level AGI",
        url="https://example.com/unverified-hype",
        source_type="hackernews",
        abstract="This breakthrough replaces all software engineers and achieves 100% accurate results.",
        discovered_at=datetime.now(timezone.utc).isoformat(),
    )
    temp_repo.save_discovered_item(hype_item)

    # Verify clean item
    rec_clean = agent_b.verify_item(clean_item)
    assert rec_clean.is_verified is True
    assert rec_clean.requires_human_review is False
    assert len(rec_clean.confirmed_facts) > 0

    # Verify hype item
    rec_hype = agent_b.verify_item(hype_item)
    assert rec_hype.is_verified is False
    assert rec_hype.requires_human_review is True
    assert "Sensationalized claims detected" in rec_hype.review_reason


def test_ranking_agent_6_dimension_scoring(temp_repo):
    """Verifies that Agent C calculates the 6-dimension scores and applies recency decay."""
    ranking_agent = TopicRankingAgent(repo=temp_repo)

    item = DiscoveredItemRecord(
        id="item_vllm_test",
        title="vLLM: High-Throughput and Memory-Efficient LLM Serving with PagedAttention",
        url="https://github.com/vllm-project/vllm",
        source_type="github",
        primary_category="Python",
        authors="vLLM Team",
        abstract="High-throughput LLM serving engine with PagedAttention reducing memory waste.",
        raw_metadata={"stars": 40000, "forks": 5000},
        published_at=datetime.now(timezone.utc).isoformat(),
        discovered_at=datetime.now(timezone.utc).isoformat(),
    )
    temp_repo.save_discovered_item(item)

    score_record = ranking_agent.score_topic(item, recent_post_topics=[])

    assert score_record.total_score >= 70.0
    assert score_record.score_recency >= 80.0
    assert score_record.score_accessibility >= 80.0  # GitHub source
    assert score_record.score_usefulness >= 80.0  # Serving & throughput practical topic


def test_research_simplification_7_questions(temp_repo):
    """Verifies that Agent D accurately extracts the 7-question breakdown."""
    agent_d = ResearchSimplificationAgent(repo=temp_repo)

    item = DiscoveredItemRecord(
        id="item_distill_test",
        title="vLLM: High-Throughput Serving with PagedAttention",
        url="https://github.com/vllm-project/vllm",
        source_type="github",
        abstract="Virtual memory paging for KV cache management.",
        discovered_at=datetime.now(timezone.utc).isoformat(),
    )
    temp_repo.save_discovered_item(item)

    distillation = agent_d.distill(item)

    assert distillation.problem != ""
    assert distillation.why_it_matters != ""
    assert distillation.core_idea != ""
    assert distillation.what_is_new != ""
    assert distillation.results_and_conditions != ""
    assert distillation.limitations != ""
    assert item.url in distillation.code_and_paper_links


def test_content_strategist_angles(temp_repo):
    """Verifies that Agent E formulates tailored angles for LinkedIn and X."""
    strategist = ContentStrategistAgent(repo=temp_repo)

    item = DiscoveredItemRecord(
        id="item_strat_test",
        title="PagedAttention for LLMs",
        url="https://github.com/vllm-project/vllm",
        source_type="github",
        discovered_at=datetime.now(timezone.utc).isoformat(),
    )
    temp_repo.save_discovered_item(item)

    strat_li = strategist.determine_strategy(item, None, "linkedin")
    strat_x = strategist.determine_strategy(item, None, "x")

    assert strat_li.target_platform == "linkedin"
    assert len(strat_li.candidate_angles) >= 5
    assert strat_x.target_platform == "x"
    assert strat_x.selected_angle in ["open_source_spotlight", "technical_insight"]


def test_platform_copywriting_and_quality_gate(temp_repo):
    """Verifies that Agent F drafts compliant posts that pass the Quality Gate."""
    copywriter = PlatformCopywritingAgent(repo=temp_repo)

    item = DiscoveredItemRecord(
        id="item_copy_test",
        title="PagedAttention and Memory Management in LLMs",
        url="https://github.com/vllm-project/vllm",
        source_type="github",
        discovered_at=datetime.now(timezone.utc).isoformat(),
    )
    temp_repo.save_discovered_item(item)

    # Test LinkedIn copy
    cfg_li = copywriter.platforms.get("linkedin")
    post_li = copywriter.craft_post(
        platform="linkedin",
        platform_cfg=cfg_li,
        item=item,
        distillation=None,
        angle_record=None,
        existing_fingerprints=[],
        recent_texts=[],
    )

    assert post_li is not None
    assert post_li.quality_score >= 85
    assert post_li.status == "SCHEDULED"
    assert "https://github.com/vllm-project/vllm" in post_li.content
    assert post_li.quality_report.get("hashtag_count", 0) <= 3


def test_end_to_end_pipeline(temp_repo):
    """Verifies that ContentIntelligencePipeline executes all 6 stages end-to-end."""
    pipeline = ContentIntelligencePipeline(repo=temp_repo)
    # Seed an item so discovery runs smoothly
    seed_item = DiscoveredItemRecord(
        id="item_pipeline_seed",
        title="Speculative Decoding for High-Throughput LLM Inference",
        url="https://arxiv.org/abs/2211.17192",
        source_type="arxiv",
        abstract="Draft model speculative execution achieves 2x speedups with identical output distribution.",
        discovered_at=datetime.now(timezone.utc).isoformat(),
    )
    temp_repo.save_discovered_item(seed_item)

    res = pipeline.run_full_pipeline(
        discovery_limit_per_source=2,
        target_platforms=["linkedin", "x"],
    )

    assert res["success"] is True
    assert res["pipeline_run_id"].startswith("pipeline_")
    assert res["posts_scheduled_count"] >= 1

    # Verify posts exist in database
    scheduled_posts = temp_repo.get_all_scheduled_posts()
    assert len(scheduled_posts) >= 1
    scheduled_topics = [p.topic for p in scheduled_posts]
    assert any(res["topic_chosen"] in t for t in scheduled_topics)
