"""
Test suite for the new Editorial Card Renderer.
Tests all 4 templates, all 3 platform dimensions,
and the brief builder from research data.
"""

import pytest
import sys
import os
from pathlib import Path

# Ensure automa is importable
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestEditorialRenderer:
    """Tests the HTML/CSS → PNG editorial renderer."""

    def test_renderer_imports(self):
        """Verify all renderer components import correctly."""
        from automa.media.renderer import (
            EditorialCardRenderer, CardBrief, ComparisonBar,
            FeatureItem, MetaItem, FlowStep,
            build_brief_from_research,
            PLATFORM_DIMENSIONS,
        )
        assert "linkedin" in PLATFORM_DIMENSIONS
        assert "x" in PLATFORM_DIMENSIONS
        assert "instagram" in PLATFORM_DIMENSIONS

    def test_insight_template_linkedin(self):
        """Test Engineering Insight template for LinkedIn (square 1200x1200)."""
        from automa.media.renderer import EditorialCardRenderer, CardBrief

        renderer = EditorialCardRenderer(output_dir=Path("content/media"))
        brief = CardBrief(
            template="insight",
            platform="linkedin",
            category="ENGINEERING INSIGHT",
            headline="LiteLLM: Unified Multi-Provider Gateway",
            insight="Enterprise teams managing multiple LLM providers face inconsistent SDK interfaces. LiteLLM normalizes 100+ provider APIs into a single OpenAI-compatible interface with automatic retries and fallbacks.",
            evidence_items=[
                "Supports 100+ LLM providers through unified call interface",
                "OpenAI-compatible input/output format standardization",
                "Built-in retry logic with cross-provider fallback routing",
                "Consolidated spend tracking and rate limit management",
            ],
            source_label="github.com/BerriAI/litellm",
            verified=True,
            post_id="test_insight_linkedin",
        )
        path = renderer.render(brief)
        assert path.exists(), f"Expected image at {path}"
        assert path.stat().st_size > 10_000, "Image file too small"
        print(f"  ✓ Insight template (LinkedIn): {path} ({path.stat().st_size:,} bytes)")

    def test_benchmark_template_x(self):
        """Test Benchmark Breakdown template for X (landscape 1200x675)."""
        from automa.media.renderer import EditorialCardRenderer, CardBrief, ComparisonBar

        renderer = EditorialCardRenderer(output_dir=Path("content/media"))
        brief = CardBrief(
            template="benchmark",
            platform="x",
            category="VERIFIED BENCHMARK",
            headline="vLLM PagedAttention Performance",
            insight="PagedAttention reduces KV cache memory waste from 60-80% to under 4%, enabling dramatically higher throughput for LLM inference serving.",
            metric_value="24x",
            metric_label="THROUGHPUT IMPROVEMENT",
            comparisons=[
                ComparisonBar(label="Standard Inference", value_label="1.0x", percent=25, type="baseline"),
                ComparisonBar(label="With PagedAttention", value_label="24x", percent=92, type="optimized"),
            ],
            methodology_note="Benchmark from vLLM paper. Results measured under high-concurrency batch serving conditions.",
            source_label="github.com/vllm-project/vllm",
            verified=True,
            post_id="test_benchmark_x",
        )
        path = renderer.render(brief)
        assert path.exists(), f"Expected image at {path}"
        assert path.stat().st_size > 10_000, "Image file too small"
        print(f"  ✓ Benchmark template (X): {path} ({path.stat().st_size:,} bytes)")

    def test_spotlight_template_instagram(self):
        """Test Project Spotlight template for Instagram (portrait 1080x1350)."""
        from automa.media.renderer import EditorialCardRenderer, CardBrief, FeatureItem, MetaItem

        renderer = EditorialCardRenderer(output_dir=Path("content/media"))
        brief = CardBrief(
            template="spotlight",
            platform="instagram",
            category="PROJECT SPOTLIGHT",
            headline="LangChain: LLM Application Framework",
            insight="LangChain provides composable building blocks for constructing LLM-powered applications, from simple prompt chains to complex multi-agent systems.",
            features=[
                FeatureItem(title="Composable Chain Architecture", desc="Build complex workflows from modular components"),
                FeatureItem(title="Multi-Provider Support", desc="Swap LLM backends without code changes"),
                FeatureItem(title="RAG Integration", desc="Built-in retrieval-augmented generation patterns"),
                FeatureItem(title="Agent Framework", desc="Autonomous tool-using agent construction"),
            ],
            meta_items=[
                MetaItem(value="95K", label="STARS"),
                MetaItem(value="15K", label="FORKS"),
                MetaItem(value="Python", label="LANGUAGE"),
                MetaItem(value="MIT", label="LICENSE"),
            ],
            source_label="github.com/langchain-ai/langchain",
            verified=True,
            post_id="test_spotlight_ig",
        )
        path = renderer.render(brief)
        assert path.exists(), f"Expected image at {path}"
        assert path.stat().st_size > 10_000, "Image file too small"
        print(f"  ✓ Spotlight template (Instagram): {path} ({path.stat().st_size:,} bytes)")

    def test_explainer_template_linkedin(self):
        """Test Technical Explainer template with flow diagram."""
        from automa.media.renderer import EditorialCardRenderer, CardBrief, FlowStep

        renderer = EditorialCardRenderer(output_dir=Path("content/media"))
        brief = CardBrief(
            template="explainer",
            platform="linkedin",
            category="TECHNICAL EXPLAINER",
            headline="Speculative Decoding Pipeline",
            insight="A lightweight draft model generates candidate tokens speculatively, then a single parallel forward pass through the primary LLM verifies them.",
            flow_steps=[
                FlowStep(title="Draft Generation", desc="Small model quickly proposes N candidate tokens"),
                FlowStep(title="Parallel Verification", desc="Primary LLM validates all candidates in one forward pass"),
                FlowStep(title="Accept or Reject", desc="Matching tokens accepted; first mismatch triggers resample"),
            ],
            callout="Delivers 2-3x latency reduction with mathematically identical output distributions.",
            source_label="arxiv.org/abs/2211.17192",
            verified=True,
            post_id="test_explainer_linkedin",
        )
        path = renderer.render(brief)
        assert path.exists(), f"Expected image at {path}"
        assert path.stat().st_size > 10_000, "Image file too small"
        print(f"  ✓ Explainer template (LinkedIn): {path} ({path.stat().st_size:,} bytes)")

    def test_brief_builder_with_benchmarks(self):
        """Test that build_brief_from_research selects benchmark scorecard when real benchmarks exist."""
        from automa.media.renderer import build_brief_from_research

        brief = build_brief_from_research(
            item_title="vLLM: High-Throughput LLM Serving",
            item_abstract="vLLM uses PagedAttention for efficient KV cache management.",
            raw_metadata={
                "project_name": "vLLM",
                "key_features": ["PagedAttention memory management", "Continuous batching", "CUDA graph optimization"],
                "benchmarks": ["24x throughput improvement under high concurrency"],
                "stars": 42000,
                "forks": 6500,
                "language": "Python",
                "license": "Apache-2.0",
                "html_url": "https://github.com/vllm-project/vllm",
                "provenance": {"source_type": "github_repository"},
            },
            distillation_problem="LLM inference serving wastes 60-80% of KV cache memory",
            distillation_core_idea="PagedAttention manages KV cache like virtual memory pages",
            distillation_what_is_new="Reduces memory waste to under 4%",
            distillation_limitations="Requires CUDA-capable GPU with sufficient VRAM",
            platform="linkedin",
            post_id="test_brief_benchmark",
        )
        assert brief.template in ("scorecard", "benchmark_scorecard"), f"Expected scorecard template, got {brief.template}"
        assert len(brief.score_bars) >= 4, "Should populate 4 score bars"
        print(f"  ✓ Brief builder selected {brief.template} template with {len(brief.score_bars)} bars")

    def test_brief_builder_spotlight(self):
        """Test that build_brief_from_research selects spotlight template when rich features exist."""
        from automa.media.renderer import build_brief_from_research

        brief = build_brief_from_research(
            item_title="LiteLLM: Call 100+ LLMs with the same interface",
            item_abstract="Unified interface for all LLM providers",
            raw_metadata={
                "project_name": "Litellm",
                "key_features": [
                    "Unified OpenAI-compatible API for 100+ LLM providers",
                    "Built-in retry and fallback routing across providers",
                    "Spend tracking and budget management per API key",
                    "Load balancing across multiple model deployments",
                ],
                "benchmarks": [],
                "stars": 15000,
                "forks": 1800,
                "language": "Python",
                "license": "MIT",
                "html_url": "https://github.com/BerriAI/litellm",
                "provenance": {"source_type": "github_repository"},
            },
            distillation_problem="Managing multiple LLM provider SDKs creates integration complexity",
            distillation_core_idea="Normalizes all LLM APIs into a single OpenAI-compatible interface",
            distillation_what_is_new="Automatic failover across providers without code changes",
            distillation_limitations=None,
            platform="linkedin",
            post_id="test_brief_spotlight",
        )
        assert brief.template in ("spotlight", "insight", "spotlight_light", "workflow_insight"), f"Expected spotlight or insight, got {brief.template}"
        assert len(brief.feature_tiles) >= 3 or len(brief.checklist_points) >= 3, "Should populate feature tiles or checklist"
        print(f"  ✓ Brief builder selected {brief.template}")

    def test_brief_builder_no_fabrication(self):
        """Test that the builder NEVER fabricates benchmarks when none exist."""
        from automa.media.renderer import build_brief_from_research

        brief = build_brief_from_research(
            item_title="My Simple Tool",
            item_abstract="A basic utility with no benchmarks",
            raw_metadata={
                "project_name": "Simple Tool",
                "key_features": ["Feature one", "Feature two"],
                "benchmarks": [],
                "stars": 50,
                "language": "JavaScript",
            },
            distillation_problem="Some problem",
            distillation_core_idea="Some solution",
            distillation_what_is_new="Something new",
            distillation_limitations=None,
            platform="x",
        )
        # Should NOT select benchmark template
        assert brief.template != "benchmark", f"Should not use benchmark template without real benchmarks, got {brief.template}"
        # Should not have invented metric values
        assert brief.metric_value is None, f"Should not fabricate metrics, got {brief.metric_value}"
        print(f"  ✓ No fabrication: template={brief.template}, metric_value={brief.metric_value}")

    def test_card_generator_backward_compat(self):
        """Test that the VisualCardGenerator backward-compatible interface works."""
        from automa.media.card_generator import VisualCardGenerator, VisualBrief

        gen = VisualCardGenerator(output_dir=Path("content/media"))
        brief = VisualBrief(
            topic="Test Topic",
            headline="Backward Compatibility Test",
            core_insight="This tests the legacy VisualBrief interface still works through the new renderer.",
            art_direction="INSIGHT",
            supporting_points=["Point 1: Architecture patterns", "Point 2: Performance gains"],
            source_name="test_source",
            platform="x",
            post_id="test_compat_card",
        )
        path = gen.generate_from_brief(brief)
        assert path.exists(), f"Expected image at {path}"
        assert path.stat().st_size > 5_000, "Image file too small"
        print(f"  ✓ Backward compat card: {path} ({path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

