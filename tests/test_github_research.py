"""
tests/test_github_research.py
-----------------------------
Comprehensive tests for GitHub research extraction, provenance tracking,
multi-style visual card rendering, and platform content differentiation.
"""

from pathlib import Path
from automa.research.github import GitHubResearchService
from automa.media.card_generator import VisualCardGenerator, VisualBrief
from automa.db.repository import DiscoveredItemRecord, ResearchDistillationRecord, ContentAngleRecord
from automa.agents.copywriter import PlatformCopywritingAgent
from automa.config import PlatformConfig, PlatformConstraints


def test_github_research_service_enrichment():
    service = GitHubResearchService()
    mock_item = {
        "full_name": "vllm-project/vllm",
        "html_url": "https://github.com/vllm-project/vllm",
        "description": "A high-throughput and memory-efficient inference and serving engine for LLMs",
        "stargazers_count": 42000,
        "forks_count": 6500,
        "language": "Python",
        "license": {"spdx_id": "Apache-2.0"},
        "topics": ["llm", "inference", "pagedattention"],
    }
    mock_readme = """
# vLLM
vLLM is a high-throughput and memory-efficient LLM serving engine.

## Key Features
- State-of-the-art serving throughput
- Efficient management of attention key and value memory with PagedAttention
- Continuous batching of incoming requests
- Chunked prefill for low-latency streaming

## Benchmark
Demonstrated up to 24x higher throughput compared to Hugging Face Transformers.
```python
from vllm import LLM, SamplingParams
llm = LLM(model="meta-llama/Llama-3-8B")
```
"""
    insight = service.extract_research_insight(mock_item, mock_readme, "https://raw.githubusercontent.com/vllm-project/vllm/HEAD/README.md")
    assert insight is not None
    assert insight["project_name"] == "VLLM"
    assert "GitHub Repo:" not in insight["headline_title"]
    assert len(insight["key_features"]) >= 3
    assert insight["license"] == "Apache-2.0"
    assert insight["stars"] == 42000
    assert "provenance" in insight
    assert insight["provenance"]["readme_url"] == "https://raw.githubusercontent.com/vllm-project/vllm/HEAD/README.md"


def test_multi_style_visual_card_generation():
    gen = VisualCardGenerator()
    styles = ["SWISS_MINIMAL", "ARCHITECTURE_FLOW", "BENCHMARK_METRIC", "TECHNICAL_SPLIT"]

    for style in styles:
        brief = VisualBrief(
            topic="vLLM: High-Throughput Serving with PagedAttention",
            headline="vLLM: High-Throughput Serving",
            core_insight="PagedAttention manages attention KV cache in non-contiguous memory blocks.",
            art_direction=style,
            supporting_points=["Memory waste reduced from 80% to under 4%.", "Dynamic block allocation on demand."],
            metric_highlight="24x",
            metric_label="THROUGHPUT MULTIPLIER",
            source_name="GitHub:vllm-project/vllm",
            platform="linkedin",
            post_id=f"test_run_{style.lower()}",
        )
        out_path = gen.generate_from_brief(brief)
        assert out_path.exists()
        assert out_path.stat().st_size > 10000  # At least 10KB of real graphic data
        out_path.unlink(missing_ok=True)


def test_copywriter_eliminates_repo_title_and_differentiates():
    agent = PlatformCopywritingAgent()
    item = DiscoveredItemRecord(
        id="disc_vllm_test",
        title="vLLM: High-Throughput Serving with PagedAttention",
        url="https://github.com/vllm-project/vllm",
        source_type="github",
        primary_category="Python",
        raw_metadata={
            "project_name": "vLLM",
            "key_features": ["PagedAttention KV cache paging", "Continuous batching"],
            "benchmarks": ["24x throughput"],
            "license": "Apache-2.0",
        },
        discovered_at="2026-10-31T00:00:00Z",
    )
    distillation = ResearchDistillationRecord(
        id="dist_test",
        discovered_item_id=item.id,
        problem="KV cache fragmentation wastes 60-80% of GPU VRAM in production serving.",
        why_it_matters="GPU memory capacity is the primary barrier to serving concurrency.",
        core_idea="PagedAttention dynamically allocates non-contiguous physical pages for tokens.",
        what_is_new="Eliminates internal memory fragmentation down to under 4%.",
        results_and_conditions="Achieves up to 24x higher throughput than standard transformer baselines.",
        limitations="Requires custom CUDA kernel memory management.",
        code_and_paper_links=["https://github.com/vllm-project/vllm"],
        distilled_at="2026-10-31T00:00:00Z",
    )

    linkedin_text = agent._generate_initial_draft("linkedin", item, distillation, None)
    x_text = agent._generate_initial_draft("x", item, distillation, None)
    ig_text = agent._generate_initial_draft("instagram", item, distillation, None)

    # 1. No "GitHub Repo:" prefix anywhere
    assert "GitHub Repo:" not in linkedin_text
    assert "GitHub Repo:" not in x_text
    assert "GitHub Repo:" not in ig_text

    # 2. X post is strictly <= 280 chars
    assert len(x_text) <= 280

    # 3. Instagram has NO "link in bio"
    assert "link in bio" not in ig_text.lower()

    # 4. Content is distinct across platforms
    assert linkedin_text != x_text
    assert linkedin_text != ig_text
    assert x_text != ig_text

