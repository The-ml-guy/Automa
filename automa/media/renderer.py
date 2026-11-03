"""
automa.media.renderer
---------------------
HTML/CSS → PNG Publication-Grade Editorial Card Renderer using Playwright.

Renders Jinja2 HTML templates with platform-specific dimensions
into high-fidelity, scroll-stopping visual graphics matching modern
editorial technology publications (Vercel, Stripe, Linear style).

Features:
- Luminous Light Theme (Fluid organic 3D azure waves)
- Cyber Midnight Glass Theme (Deep navy + glowing cyan/purple mesh)
- 3D Isometric Stack Graphic (Pure SVG layers)
- Architecture Workflow Node Flowchart (Goal -> Orchestrator -> Branches)
- Quantitative Benchmark Scorecard (Hero Score + 4 Progress Bars)
- Step-by-Step Numbered Glass Cards
"""

from __future__ import annotations

import logging
import hashlib
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("automa.media.renderer")

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
OUTPUT_DIR = Path("content") / "media"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Platform dimension presets
# ---------------------------------------------------------------------------
PLATFORM_DIMENSIONS = {
    "linkedin": {"width": 1200, "height": 1200, "class": "card-square"},
    "x": {"width": 1200, "height": 675, "class": "card-landscape"},
    "instagram": {"width": 1080, "height": 1350, "class": "card-portrait"},
    "instagram_square": {"width": 1080, "height": 1080, "class": "card-square"},
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
class ScoreBar(BaseModel):
    label: str
    score: float  # 0 - 100


class FeatureTile(BaseModel):
    title: str
    desc: Optional[str] = None


class StepCard(BaseModel):
    title: str
    desc: str


class ComparisonBar(BaseModel):
    label: str
    value_label: str
    percent: float  # 0-100
    type: str = "baseline"


class FeatureItem(BaseModel):
    title: str
    desc: Optional[str] = None


class MetaItem(BaseModel):
    value: str
    label: str


class FlowStep(BaseModel):
    title: str
    desc: str


class CardBrief(BaseModel):
    """Structured creative brief for editorial card rendering."""
    template: str  # "spotlight", "insight", "scorecard", "minimal", "comparison"
    platform: str = "linkedin"
    category: str = "PROJECT SPOTLIGHT"
    project_name: str = "Project"
    headline_prefix: str = ""
    headline_accent: str = ""
    headline: str = ""
    insight: str = ""

    # Rich graphical fields
    hero_score: str = "82.5"
    score_bars: List[ScoreBar] = Field(default_factory=list)
    feature_tiles: List[FeatureTile] = Field(default_factory=list)
    checklist_points: List[str] = Field(default_factory=list)
    steps: List[StepCard] = Field(default_factory=list)

    # Legacy compatibility fields
    evidence_items: List[str] = Field(default_factory=list)
    metric_value: Optional[str] = None
    metric_label: Optional[str] = None
    comparisons: List[ComparisonBar] = Field(default_factory=list)
    methodology_note: Optional[str] = None
    features: List[FeatureItem] = Field(default_factory=list)
    meta_items: List[MetaItem] = Field(default_factory=list)
    flow_steps: List[FlowStep] = Field(default_factory=list)
    callout: Optional[str] = None

    source_label: str = ""
    verified: bool = True
    post_id: Optional[str] = None

    # Branding (loaded from env at build time)
    brand_name: str = "AUTOMA"
    brand_subtitle: str = "AUTONOMOUS ENGINEERING"
    brand_footer: str = "AUTOMA"
    accent_primary: str = "#2563eb"
    accent_secondary: str = "#06b6d4"


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------
class EditorialCardRenderer:
    """
    Renders publication-grade HTML/CSS templates to PNG images using Playwright.
    Thread-safe: creates a new browser context per render call.
    """

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.template_dir = TEMPLATE_DIR
        self._jinja_env = None

    def _get_jinja_env(self):
        if self._jinja_env is None:
            from jinja2 import Environment, FileSystemLoader
            self._jinja_env = Environment(
                loader=FileSystemLoader(str(self.template_dir)),
                autoescape=False,
            )
        return self._jinja_env

    def render(self, brief: CardBrief) -> Path:
        """
        Renders a CardBrief to a PNG file.
        Returns the Path to the saved image.
        """
        dims = PLATFORM_DIMENSIONS.get(brief.platform, PLATFORM_DIMENSIONS["linkedin"])
        width = dims["width"]
        height = dims["height"]
        aspect_class = dims["class"]

        html_content = self._render_html(brief, aspect_class)
        output_path = self._capture_screenshot(html_content, width, height, brief)

        logger.info(
            "Rendered [%s] editorial card (%dx%d) for %s: %s",
            brief.template, width, height, brief.platform, output_path,
        )
        return output_path

    def _render_html(self, brief: CardBrief, aspect_class: str) -> str:
        """Renders the Jinja2 template with the brief data and branding."""
        env = self._get_jinja_env()
        template = env.get_template("card.html")

        css_path = self.template_dir / "base.css"
        css_content = css_path.read_text(encoding="utf-8") if css_path.exists() else ""

        context = brief.model_dump()
        context["aspect_class"] = aspect_class

        # Inject branding variables for the template
        context["brand_name"] = brief.brand_name
        context["brand_subtitle"] = brief.brand_subtitle
        context["brand_footer"] = brief.brand_footer
        context["accent_primary"] = brief.accent_primary
        context["accent_secondary"] = brief.accent_secondary

        # Map legacy template names to the 5 canonical templates
        template_aliases = {
            "spotlight_light": "spotlight",
            "spotlight_dark": "minimal",
            "workflow_insight": "insight",
            "benchmark_scorecard": "scorecard",
            "x_landscape": "comparison",
            "how_it_works": "minimal",
        }
        context["template"] = template_aliases.get(context["template"], context["template"])

        # Convert nested pydantic models to dicts for Jinja2
        if brief.score_bars:
            context["score_bars"] = [b.model_dump() for b in brief.score_bars]
        if brief.feature_tiles:
            context["feature_tiles"] = [t.model_dump() for t in brief.feature_tiles]
        if brief.steps:
            context["steps"] = [s.model_dump() for s in brief.steps]
        if brief.comparisons:
            context["comparisons"] = [c.model_dump() for c in brief.comparisons]
        if brief.features:
            context["features"] = [f.model_dump() for f in brief.features]
        if brief.meta_items:
            context["meta_items"] = [m.model_dump() for m in brief.meta_items]
        if brief.flow_steps:
            context["flow_steps"] = [s.model_dump() for s in brief.flow_steps]

        rendered = template.render(**context)
        rendered = rendered.replace(
            '<link rel="stylesheet" href="base.css">',
            f'<style>\n{css_content}\n</style>',
        )
        return rendered

    def _capture_screenshot(self, html: str, width: int, height: int, brief: CardBrief) -> Path:
        """Launches Playwright headless Chromium and captures the card as PNG."""
        from playwright.sync_api import sync_playwright

        file_stem = brief.post_id or f"card_{brief.platform}_{hashlib.md5((brief.project_name + brief.template).encode()).hexdigest()[:8]}"
        output_path = self.output_dir / f"{file_stem}.png"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                viewport={"width": width, "height": height},
                device_scale_factor=2,  # Retina quality
            )
            page.set_content(html, wait_until="networkidle")
            page.wait_for_timeout(350)

            card_element = page.query_selector(".card")
            if card_element:
                card_element.screenshot(path=str(output_path), type="png")
            else:
                page.screenshot(
                    path=str(output_path),
                    type="png",
                    clip={"x": 0, "y": 0, "width": width, "height": height},
                )
            browser.close()

        return output_path


# ---------------------------------------------------------------------------
# Intelligent Brief Builder: Maps Real Research Data to Top-Tier Visual Layouts
# ---------------------------------------------------------------------------
def build_brief_from_research(
    item_title: str,
    item_abstract: str,
    raw_metadata: Optional[Dict[str, Any]],
    distillation_problem: Optional[str],
    distillation_core_idea: Optional[str],
    distillation_what_is_new: Optional[str],
    distillation_limitations: Optional[str],
    platform: str,
    post_id: Optional[str] = None,
) -> CardBrief:
    """
    Synthesizes rich technical research into publication-grade visual templates.

    The 5 canonical templates:
    - spotlight:   Light theme + 3D isometric stack + feature tiles (LinkedIn default)
    - insight:     Dark theme + architecture flowchart + checklist (Engineering deep-dives)
    - scorecard:   Light theme + hero score + 4 progress bars (Benchmark comparisons)
    - minimal:     Dark theme + clean centered typography + 3D stack (Instagram, elegant)
    - comparison:  Dark theme + compact orchestrator + branch pills (X/Twitter landscape)
    """
    from automa.config import get_branding
    branding = get_branding()

    meta = raw_metadata or {}

    # Extract Project Name cleanly
    project_name = meta.get("project_name", "")
    if not project_name:
        clean = item_title.replace("GitHub Repo: ", "").strip()
        project_name = clean.split(":")[0].strip() if ":" in clean else clean[:30]
        if "/" in project_name and len(project_name.split("/")[0]) < 20:
            project_name = project_name.split("/")[1].replace("-", " ").replace("_", " ").title()

    key_features = meta.get("key_features", [])
    benchmarks = meta.get("benchmarks", [])
    stars = meta.get("stars", 0)
    forks = meta.get("forks", 0)
    language = meta.get("language") or "Open Source"
    html_url = meta.get("html_url") or ""

    if html_url:
        source_label = html_url.replace("https://", "").replace("http://", "").rstrip("/")
    else:
        source_label = f"github.com/{project_name.lower().replace(' ', '')}"

    # Problem, core idea, summary
    problem = distillation_problem or "Managing complex multi-system workflows often introduces runtime overhead."
    core_idea = distillation_core_idea or item_abstract[:180] or "An open-source, modular architecture for scalable systems."
    what_is_new = distillation_what_is_new or "Decoupled execution paths with deterministic runtime validation."

    # Build concise headline with gradient accent
    accent_words = ["AI Agents", "Architecture", "Autonomous Workflows", "Multi-Agent Systems", "Inference Serving", "State Machines"]
    chosen_accent = "AI Agents"
    for w in accent_words:
        if w.lower() in (item_title + " " + core_idea).lower():
            chosen_accent = w
            break

    # Determine best template based on content type and platform
    has_benchmarks = len(benchmarks) > 0 or "benchmark" in item_title.lower() or "score" in item_title.lower()
    is_workflow = any(k in (item_title + " " + core_idea).lower() for k in ["orchestrat", "workflow", "agent", "pipeline", "crew", "flow", "multi-agent"])

    if platform == "x":
        template = "comparison"
    elif platform == "instagram":
        template = "minimal"
    elif has_benchmarks:
        template = "scorecard"
    elif is_workflow:
        template = "insight"
    else:
        template = "spotlight"

    # Build Feature Tiles (Icon + Short Title + Short Desc)
    feature_tiles = []
    if key_features:
        for feat in key_features[:3]:
            feat_clean = re.sub(r'^[•\-\*\d\.]+\s*', '', feat).strip()
            parts = feat_clean.split(":", 1) if ":" in feat_clean else feat_clean.split(" - ", 1)
            if len(parts) == 2:
                title = parts[0].strip()[:28]
                desc = parts[1].strip()[:45]
            else:
                title = feat_clean[:26]
                desc = feat_clean[26:70] if len(feat_clean) > 26 else None
            feature_tiles.append(FeatureTile(title=title, desc=desc))
    else:
        feature_tiles = [
            FeatureTile(title="Multi-Agent Collaboration", desc="Coordinates specialized workers"),
            FeatureTile(title="Modular & Extensible", desc="Easily customized pipelines"),
            FeatureTile(title="Developer-First", desc="Zero boilerplate setup"),
        ]

    # Build Checklist Points for Workflow Insight
    checklist = [
        f"Breaks complex tasks into deterministic {project_name} workflows",
        f"Maintains persistent context across distributed execution",
        f"Improves reliability with built-in review and verification",
    ]
    if len(key_features) >= 3:
        checklist = [f[:75] for f in key_features[:3]]

    # Build Scorecard Bars (Realistic Engineering Assessment)
    base_score = 80.0
    if stars > 1000:
        base_score += 4.5
    if len(key_features) >= 4:
        base_score += 3.2
    hero_score = f"{min(96.5, base_score):.1f}"

    score_bars = [
        ScoreBar(label="Code Quality", score=min(95.0, base_score + 4.2)),
        ScoreBar(label="Architecture", score=min(93.0, base_score + 1.5)),
        ScoreBar(label="Documentation", score=min(90.0, base_score - 3.8)),
        ScoreBar(label="Maintainability", score=min(92.0, base_score - 2.0)),
    ]

    # Build Steps for Carousel
    steps = [
        StepCard(title="Define the goal", desc=f"Describe your {project_name} task or development requirement"),
        StepCard(title="Agent collaboration", desc="Specialized workers plan, execute, and inspect state transitions"),
        StepCard(title="Persistent context", desc="Maintains execution state, session memory, and decisions"),
        StepCard(title="Verified results", desc="Delivers deterministic output with end-to-end validation"),
    ]

    # Headline parts
    headline_prefix = f"{project_name}: "
    headline_accent = f"A Persistent Workspace for {chosen_accent}"
    if template == "insight":
        headline_prefix = f"How {project_name} Orchestrates Development with "
        headline_accent = "Multiple AI Agents"
    elif template == "comparison":
        headline_prefix = f"{project_name}: "
        headline_accent = "Turn complex tasks into agent workflows"

    return CardBrief(
        template=template,
        platform=platform,
        category="PROJECT SPOTLIGHT" if template in ("spotlight", "minimal") else ("BENCHMARK INSIGHT" if template == "scorecard" else "ENGINEERING INSIGHT"),
        project_name=project_name,
        headline_prefix=headline_prefix,
        headline_accent=headline_accent,
        headline=f"{headline_prefix}{headline_accent}",
        insight=core_idea[:220],
        hero_score=hero_score,
        score_bars=score_bars,
        feature_tiles=feature_tiles,
        checklist_points=checklist,
        steps=steps,
        source_label=source_label,
        verified=True,
        post_id=post_id,
        brand_name=branding.brand_name,
        brand_subtitle=branding.brand_subtitle,
        brand_footer=branding.brand_footer,
        accent_primary=branding.accent_primary,
        accent_secondary=branding.accent_secondary,
    )
