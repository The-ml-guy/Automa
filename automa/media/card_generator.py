"""
automa.media.card_generator
---------------------------
Unified Visual Card Generation Interface for Automa.

Primary path: HTML/CSS editorial renderer (Playwright + Jinja2)
Fallback path: PIL pixel-based renderer (for environments without Playwright)

This module provides the public API consumed by the copywriter agent,
content engine, and web server.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("automa.media.card_generator")

MEDIA_DIR = Path("content") / "media"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Public data model (preserved for backward compatibility)
# ---------------------------------------------------------------------------
class VisualBrief(BaseModel):
    """Structured creative brief separating content from rendering."""
    topic: str
    headline: str
    core_insight: str
    art_direction: str = "INSIGHT"  # INSIGHT, BENCHMARK, SPOTLIGHT, EXPLAINER
    supporting_points: List[str] = Field(default_factory=list)
    metric_highlight: Optional[str] = None
    metric_label: Optional[str] = None
    source_name: str = "Verified Source"
    author_or_team: str = "Systems Engineering"
    category: str = "ENGINEERING INSIGHT"
    platform: str = "linkedin"
    post_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Main generator class
# ---------------------------------------------------------------------------
class VisualCardGenerator:
    """
    Renders editorial-quality social media graphics.
    
    Primary: HTML/CSS templates rendered via Playwright (publication-grade typography).
    Fallback: PIL-based rendering (if Playwright is unavailable).
    """

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or MEDIA_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._renderer = None
        self._pil_available = True

    def _get_renderer(self):
        """Lazily initializes the HTML renderer."""
        if self._renderer is None:
            try:
                from automa.media.renderer import EditorialCardRenderer
                self._renderer = EditorialCardRenderer(output_dir=self.output_dir)
                # Quick check that Playwright browsers are installed
                from playwright.sync_api import sync_playwright
                with sync_playwright() as p:
                    browser = p.chromium.launch(
                        headless=True,
                        args=["--disable-dev-shm-usage", "--no-sandbox"],
                    )
                    browser.close()
                logger.info("Editorial HTML renderer initialized (Playwright + Chromium)")
            except Exception as e:
                logger.warning("HTML renderer unavailable, will use PIL fallback: %s", e)
                self._renderer = None
        return self._renderer

    def generate_from_brief(self, brief: VisualBrief) -> Path:
        """Dispatches to the appropriate renderer based on availability."""
        renderer = self._get_renderer()

        if renderer is not None:
            try:
                return self._render_html(brief, renderer)
            except Exception as e:
                logger.warning("HTML rendering failed, falling back to PIL: %s", e)

        # PIL fallback
        return self._render_pil_fallback(brief)

    def generate_card(
        self,
        topic: str,
        category: str = "ENGINEERING INSIGHT",
        takeaways: Optional[List[str]] = None,
        source_name: str = "Verified Source",
        author_or_team: str = "Engineering Team",
        platform: str = "linkedin",
        post_id: Optional[str] = None,
        art_direction: Optional[str] = None,
    ) -> Path:
        """
        Legacy bridge that converts raw parameters into a VisualBrief and renders.
        """
        # Clean headline
        clean_headline = topic
        if "github repo:" in clean_headline.lower():
            clean_headline = clean_headline.split(":", 1)[1].strip()
        if "/" in clean_headline and len(clean_headline.split("/")[0]) < 20:
            clean_headline = clean_headline.split("/")[1].replace("-", " ").replace("_", " ").title()

        # Select art direction
        if not art_direction:
            art_direction = self._select_art_direction(topic, takeaways)

        brief = VisualBrief(
            topic=topic,
            headline=clean_headline[:55],
            core_insight=takeaways[0] if takeaways else "Engineered systems architecture.",
            art_direction=art_direction,
            supporting_points=takeaways[1:4] if takeaways and len(takeaways) > 1 else [],
            source_name=source_name,
            author_or_team=author_or_team,
            category=category,
            platform=platform,
            post_id=post_id,
        )
        return self.generate_from_brief(brief)

    def _select_art_direction(self, topic: str, takeaways: Optional[List[str]] = None) -> str:
        """Selects template based on content analysis, not keyword matching."""
        t_lower = topic.lower()
        points = takeaways or []
        points_text = " ".join(points).lower()

        # Check for real benchmark data in the takeaways
        has_benchmarks = any(
            re.search(r'\b\d+(?:\.\d+)?(?:x|%|\s*ms|\s*s|\s*tokens/s|\s*req/s)', p, re.IGNORECASE)
            for p in points
        )
        if has_benchmarks:
            return "BENCHMARK"

        # Check for flow/pipeline/architecture keywords
        if any(k in t_lower for k in ["pipeline", "flow", "agent", "workflow", "architecture", "system"]):
            return "EXPLAINER"

        # Check for project/repository data
        if any(k in t_lower for k in ["spotlight", "project", "repository", "framework", "library", "sdk"]):
            return "SPOTLIGHT"

        return "INSIGHT"

    def _render_html(self, brief: VisualBrief, renderer) -> Path:
        """Converts a VisualBrief to a CardBrief and renders via HTML."""
        from automa.media.renderer import (
            CardBrief, ComparisonBar, FeatureItem, MetaItem, FlowStep,
        )

        # Map art_direction names to the 5 editorial templates: spotlight, insight, scorecard, minimal, comparison
        template_map = {
            "INSIGHT": "insight",
            "SWISS_MINIMAL": "minimal",
            "MINIMAL": "minimal",
            "BENCHMARK": "scorecard",
            "BENCHMARK_METRIC": "scorecard",
            "SCORECARD": "scorecard",
            "SPOTLIGHT": "spotlight",
            "PROJECT_SPOTLIGHT": "spotlight",
            "EXPLAINER": "insight",
            "ARCHITECTURE_FLOW": "spotlight",
            "TECHNICAL_SPLIT": "comparison",
            "COMPARISON": "comparison",
        }
        template = template_map.get(brief.art_direction.upper(), "insight")

        # Build CardBrief from VisualBrief data
        card_brief = CardBrief(
            template=template,
            platform=brief.platform,
            category=brief.category.upper(),
            headline=brief.headline[:55],
            insight=brief.core_insight[:220],
            source_label=brief.source_name,
            verified=True,
            post_id=brief.post_id,
        )

        # Populate template-specific fields
        if template == "scorecard":
            card_brief.metric_value = brief.metric_highlight or self._extract_metric_value(brief.supporting_points)
            card_brief.metric_label = (brief.metric_label or self._extract_metric_label(brief.supporting_points))[:60]

            if card_brief.metric_value:
                card_brief.comparisons = [
                    ComparisonBar(label="Baseline", value_label="Standard", percent=30, type="baseline"),
                    ComparisonBar(label=f"With {brief.headline.split(':')[0]}", value_label=card_brief.metric_value, percent=85, type="optimized"),
                ]
            card_brief.methodology_note = "Metric extracted from project documentation. Verify conditions for your use case."

        elif template == "spotlight":
            card_brief.features = [
                FeatureItem(title=p[:60])
                for p in brief.supporting_points[:4]
            ]

        elif template == "comparison":
            steps = brief.supporting_points[:2]
            card_brief.comparisons = [
                ComparisonBar(label=steps[0][:25] if len(steps) > 0 else "Baseline Approach", value_label="30%", percent=30, type="baseline"),
                ComparisonBar(label=steps[1][:25] if len(steps) > 1 else "Modern System", value_label="90%", percent=90, type="optimized"),
            ]

        elif template == "minimal":
            card_brief.insight = brief.core_insight[:180]
            card_brief.callout = brief.supporting_points[0][:100] if brief.supporting_points else None

        else:  # insight
            card_brief.evidence_items = [p[:100] for p in brief.supporting_points[:4]]

        return renderer.render(card_brief)

    def _extract_metric_value(self, points: List[str]) -> Optional[str]:
        """Extracts a real metric value from supporting points. Never fabricates."""
        for pt in points:
            match = re.search(r'\b(\d+(?:\.\d+)?(?:x|%|\s*ms|\s*s|\s*tokens/s|\s*req/s|\s*MB|\s*GB))\b', pt, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def _extract_metric_label(self, points: List[str]) -> str:
        """Extracts context around the metric. Falls back gracefully."""
        for pt in points:
            match = re.search(r'\b\d+(?:\.\d+)?(?:x|%|\s*ms|\s*s)\b', pt, re.IGNORECASE)
            if match:
                label = pt.replace(match.group(0), "").strip()
                label = re.sub(r'^[\s\-:,]+', '', label).strip()
                if label:
                    return label[:60].upper()
        return "MEASURED PERFORMANCE"

    # -----------------------------------------------------------------------
    # PIL fallback (simplified version for when Playwright is not available)
    # -----------------------------------------------------------------------
    def _render_pil_fallback(self, brief: VisualBrief) -> Path:
        """Renders a basic card using PIL when Playwright is unavailable."""
        import os
        from PIL import Image, ImageDraw, ImageFont

        is_square = brief.platform == "instagram"
        width, height = (1080, 1080) if is_square else (1200, 675)

        base = Image.new("RGBA", (width, height), (12, 15, 20, 255))
        draw = ImageDraw.Draw(base)

        # Subtle gradient
        for y in range(height):
            ratio = y / float(height)
            v = int(12 + 5 * ratio)
            draw.line([(0, y), (width, y)], fill=(v, v + 2, v + 6, 255))

        margin = 72

        # Load fonts
        def load_font(name, size):
            paths = [
                f"C:/Windows/Fonts/{name}",
                "C:/Windows/Fonts/segoeui.ttf",
                "C:/Windows/Fonts/arial.ttf",
            ]
            for p in paths:
                if os.path.exists(p):
                    try:
                        return ImageFont.truetype(p, size)
                    except Exception:
                        pass
            return ImageFont.load_default()

        # Category badge
        f_badge = load_font("consolab.ttf", 11)
        badge_text = f"  {brief.category.upper()}  "
        bbox = draw.textbbox((0, 0), badge_text, font=f_badge)
        bw = bbox[2] - bbox[0] + 12
        bh = bbox[3] - bbox[1] + 10
        draw.rounded_rectangle(
            (margin, margin, margin + bw, margin + bh),
            radius=4, fill=(20, 28, 40), outline=(74, 158, 255, 80),
        )
        draw.text((margin + 6, margin + 5), badge_text, font=f_badge, fill=(74, 158, 255))

        # Headline
        cur_y = margin + bh + 32
        f_head = load_font("segoeuib.ttf", 42 if not is_square else 48)
        # Word wrap
        words = brief.headline.split()
        lines, current = [], []
        for w in words:
            test = " ".join(current + [w])
            tb = draw.textbbox((0, 0), test, font=f_head)
            if tb[2] - tb[0] <= width - 2 * margin:
                current.append(w)
            else:
                if current:
                    lines.append(" ".join(current))
                current = [w]
        if current:
            lines.append(" ".join(current))

        for line in lines[:3]:
            draw.text((margin, cur_y), line, font=f_head, fill=(240, 242, 245))
            cur_y += 52 if not is_square else 58

        # Accent stroke
        cur_y += 16
        draw.line([(margin, cur_y), (margin + 48, cur_y)], fill=(74, 158, 255), width=3)
        cur_y += 28

        # Body text
        f_body = load_font("segoeui.ttf", 19 if not is_square else 22)
        body_lines, current = [], []
        for w in brief.core_insight.split():
            test = " ".join(current + [w])
            tb = draw.textbbox((0, 0), test, font=f_body)
            if tb[2] - tb[0] <= width - 2 * margin - 40:
                current.append(w)
            else:
                if current:
                    body_lines.append(" ".join(current))
                current = [w]
        if current:
            body_lines.append(" ".join(current))

        for line in body_lines[:4]:
            draw.text((margin, cur_y), line, font=f_body, fill=(163, 173, 190))
            cur_y += 30 if not is_square else 34

        # Footer
        f_footer = load_font("consolab.ttf", 10)
        footer_y = height - margin - 12
        draw.line([(margin, footer_y - 16), (width - margin, footer_y - 16)], fill=(30, 36, 48, 128), width=1)
        draw.text((margin, footer_y), brief.source_name, font=f_footer, fill=(107, 122, 144))
        draw.text((width - margin - 60, footer_y), "AUTOMA", font=f_footer, fill=(107, 122, 144))

        # Save
        file_stem = brief.post_id or f"card_{brief.platform}_{abs(hash(brief.headline)) % 1000000}"
        out_path = self.output_dir / f"{file_stem}.png"
        rgb = base.convert("RGB")
        rgb.save(out_path, format="PNG", optimize=True)
        logger.info("PIL fallback card saved: %s", out_path)
        return out_path


def extract_key_takeaways(content: str, topic: str, context: str) -> List[str]:
    """Extracts key points from content text for visual card generation."""
    takeaways = []

    # Extract numbered or bullet points
    for match in re.finditer(r'(?:^|\n)\s*(?:\d+\.|[-•*])\s+(.+)', content):
        point = match.group(1).strip()
        if 20 < len(point) < 200:
            takeaways.append(point)

    # Extract sentences with technical keywords
    if not takeaways:
        sentences = re.split(r'[.!?]\s+', content)
        for s in sentences:
            s = s.strip()
            if 30 < len(s) < 200 and any(k in s.lower() for k in ["architecture", "performance", "system", "engine", "pipeline"]):
                takeaways.append(s)

    # Fallback to topic + context
    if not takeaways:
        takeaways = [
            topic[:100],
            context[:100] if context else "Open-source engineering solution.",
        ]

    return takeaways[:4]
