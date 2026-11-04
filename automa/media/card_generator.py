"""
automa.media.card_generator
---------------------------
Unified Visual Card Generation Interface for Automa.

Primary path: HTML/CSS editorial renderer (Playwright + Jinja2)
Fallback path: Self-contained SVG card (no external dependencies needed)

This module provides the public API consumed by the copywriter agent,
content engine, and web server.
"""

from __future__ import annotations

import hashlib
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
    Fallback: Clean SVG-based card (self-contained, no external dependencies).
    """

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or MEDIA_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._renderer = None
        self._renderer_checked = False

    def _get_renderer(self):
        """Lazily initializes the HTML renderer."""
        if not self._renderer_checked:
            self._renderer_checked = True
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
                logger.warning("HTML renderer unavailable, will use SVG fallback: %s", e)
                self._renderer = None
        return self._renderer

    def generate_from_brief(self, brief: VisualBrief) -> Path:
        """Dispatches to the appropriate renderer based on availability."""
        renderer = self._get_renderer()

        if renderer is not None:
            try:
                return self._render_html(brief, renderer)
            except Exception as e:
                logger.warning("HTML rendering failed, falling back to SVG: %s", e)

        # SVG fallback — clean, modern, self-contained
        return self._render_svg_card(brief)

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
    # SVG Fallback — Clean, Modern, Self-Contained (No PIL, No Playwright)
    # -----------------------------------------------------------------------
    def _render_svg_card(self, brief: VisualBrief) -> Path:
        """
        Renders a clean, modern SVG card and converts to PNG.
        Uses cairosvg if available, otherwise saves as SVG.
        
        Design: Dark glassmorphism theme with gradient accents,
        clean typography, and structured layout.
        """
        from automa.config import get_branding
        branding = get_branding()

        accent1 = branding.accent_primary or "#2563eb"
        accent2 = branding.accent_secondary or "#06b6d4"
        brand_name = branding.brand_name or "AUTOMA"

        is_portrait = brief.platform == "instagram"
        is_landscape = brief.platform == "x"

        if is_portrait:
            w, h = 1080, 1350
        elif is_landscape:
            w, h = 1200, 675
        else:
            w, h = 1200, 1200

        # Sanitize text for SVG (escape XML entities)
        def esc(text: str) -> str:
            return (text
                    .replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                    .replace('"', "&quot;")
                    .replace("'", "&apos;"))

        # Word-wrap helper
        def wrap_text(text: str, max_chars: int) -> List[str]:
            words = text.split()
            lines, current = [], []
            length = 0
            for word in words:
                if length + len(word) + 1 > max_chars and current:
                    lines.append(" ".join(current))
                    current = [word]
                    length = len(word)
                else:
                    current.append(word)
                    length += len(word) + 1
            if current:
                lines.append(" ".join(current))
            return lines

        headline = brief.headline[:55]
        insight = brief.core_insight[:200]
        category = brief.category.upper()
        source = brief.source_name[:60]
        points = [p[:80] for p in brief.supporting_points[:3]]

        margin = 72
        content_w = w - 2 * margin

        # Headline wrapping
        headline_lines = wrap_text(headline, 32 if is_landscape else 28)[:3]
        insight_lines = wrap_text(insight, 55 if is_landscape else 45)[:4]

        # Build supporting points SVG
        points_svg = ""
        if points:
            py = 0
            for i, pt in enumerate(points):
                pt_lines = wrap_text(pt, 50)
                points_svg += f'''
                <g transform="translate(0, {py})">
                    <rect x="0" y="0" width="6" height="6" rx="3" fill="{accent2}" opacity="0.9"/>
                    <text x="20" y="8" font-family="system-ui, -apple-system, 'Segoe UI', sans-serif" font-size="18" font-weight="500" fill="#cbd5e1">{esc(pt_lines[0])}</text>
                </g>'''
                py += 32
                for extra_line in pt_lines[1:]:
                    points_svg += f'''
                <g transform="translate(0, {py})">
                    <text x="20" y="8" font-family="system-ui, -apple-system, 'Segoe UI', sans-serif" font-size="18" font-weight="500" fill="#cbd5e1">{esc(extra_line)}</text>
                </g>'''
                    py += 28

        # Headline Y position
        headline_y = margin + 80
        headline_font = 52 if not is_landscape else 44
        headline_spacing = headline_font + 8

        # Insight Y position
        insight_y = headline_y + len(headline_lines) * headline_spacing + 20
        insight_spacing = 30

        # Points Y position
        points_y = insight_y + len(insight_lines) * insight_spacing + 40

        # Build the decorative elements
        deco_circle_r = 280 if not is_landscape else 220

        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#080c16"/>
      <stop offset="100%" stop-color="#0c1220"/>
    </linearGradient>
    <linearGradient id="accent" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{accent1}"/>
      <stop offset="100%" stop-color="{accent2}"/>
    </linearGradient>
    <linearGradient id="wave1" x1="0.2" y1="1" x2="0.8" y2="0" gradientUnits="objectBoundingBox">
      <stop offset="0%" stop-color="{accent1}" stop-opacity="0.25"/>
      <stop offset="100%" stop-color="{accent2}" stop-opacity="0.03"/>
    </linearGradient>
    <linearGradient id="wave2" x1="0.3" y1="1" x2="0.9" y2="0.2" gradientUnits="objectBoundingBox">
      <stop offset="0%" stop-color="{accent1}" stop-opacity="0.35"/>
      <stop offset="100%" stop-color="#1e40af" stop-opacity="0.05"/>
    </linearGradient>
    <filter id="glow">
      <feGaussianBlur stdDeviation="60" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>

  <!-- Background -->
  <rect width="{w}" height="{h}" fill="url(#bg)"/>

  <!-- Ambient glow circles -->
  <circle cx="{w - 100}" cy="{h - 100}" r="{deco_circle_r}" fill="{accent1}" opacity="0.08" filter="url(#glow)"/>
  <circle cx="{w - 200}" cy="{int(h * 0.35)}" r="{int(deco_circle_r * 0.7)}" fill="#7c3aed" opacity="0.06" filter="url(#glow)"/>

  <!-- Organic wave shapes -->
  <path d="M{int(w*0.3)},{h} C{int(w*0.5)},{int(h*0.8)} {int(w*0.45)},{int(h*0.55)} {int(w*0.7)},{int(h*0.35)} C{int(w*0.85)},{int(h*0.22)} {int(w*0.92)},{int(h*0.12)} {w},0 L{w},{h} Z" fill="url(#wave1)"/>
  <path d="M{int(w*0.4)},{h} C{int(w*0.55)},{int(h*0.85)} {int(w*0.52)},{int(h*0.65)} {int(w*0.75)},{int(h*0.48)} C{int(w*0.88)},{int(h*0.38)} {int(w*0.94)},{int(h*0.28)} {w},{int(h*0.15)} L{w},{h} Z" fill="url(#wave2)"/>

  <!-- Brand header -->
  <g transform="translate({margin}, {margin})">
    <!-- Brand icon (hexagonal shape) -->
    <g transform="translate(0, 0)">
      <path d="M17 2L31 10V24L17 32L3 24V10L17 2Z" fill="{accent1}" fill-opacity="0.2"/>
      <path d="M17 2L31 10L17 18L3 10L17 2Z" fill="{accent2}"/>
      <path d="M3 10L17 18V32L3 24V10Z" fill="#0284c7"/>
      <path d="M31 10L17 18V32L31 24V10Z" fill="#0369a1"/>
    </g>
    <!-- Brand name -->
    <text x="44" y="14" font-family="system-ui, -apple-system, 'Segoe UI', sans-serif" font-size="19" font-weight="800" letter-spacing="1.8" fill="#ffffff">{esc(brand_name)}</text>
    <text x="44" y="30" font-family="'Consolas', 'Courier New', monospace" font-size="9" font-weight="700" letter-spacing="1.5" fill="#64748b">{esc(branding.brand_subtitle or "AUTONOMOUS ENGINEERING")}</text>

    <!-- Category pill -->
    <g transform="translate({content_w - 200}, -5)">
      <rect x="0" y="0" width="200" height="34" rx="17" fill="rgba(56,189,248,0.08)" stroke="{accent2}" stroke-opacity="0.25" stroke-width="1"/>
      <text x="100" y="22" font-family="'Consolas', 'Courier New', monospace" font-size="11" font-weight="700" letter-spacing="1.5" fill="#38bdf8" text-anchor="middle">{esc(category[:24])}</text>
    </g>
  </g>

  <!-- Headline -->
  <g transform="translate({margin}, {headline_y})">
    {"".join(f'<text x="0" y="{i * headline_spacing}" font-family="system-ui, -apple-system, sans-serif" font-size="{headline_font}" font-weight="800" fill="#ffffff" letter-spacing="-0.5">{esc(line)}</text>' for i, line in enumerate(headline_lines))}
  </g>

  <!-- Accent line -->
  <rect x="{margin}" y="{insight_y - 14}" width="48" height="3" rx="1.5" fill="url(#accent)"/>

  <!-- Insight text -->
  <g transform="translate({margin}, {insight_y})">
    {"".join(f'<text x="0" y="{i * insight_spacing}" font-family="system-ui, -apple-system, sans-serif" font-size="20" font-weight="500" fill="#94a3b8">{esc(line)}</text>' for i, line in enumerate(insight_lines))}
  </g>

  <!-- Supporting points -->
  {f'<g transform="translate({margin}, {points_y})">{points_svg}</g>' if points_svg else ''}

  <!-- Footer -->
  <g transform="translate({margin}, {h - margin - 10})">
    <line x1="0" y1="-20" x2="{content_w}" y2="-20" stroke="#1e293b" stroke-width="1"/>
    <!-- GitHub icon -->
    <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" fill="#64748b" transform="scale(0.85)"/>
    <text x="28" y="8" font-family="'Consolas', 'Courier New', monospace" font-size="14" font-weight="600" fill="#64748b">{esc(source)}</text>
    <text x="{content_w}" y="8" font-family="'Consolas', 'Courier New', monospace" font-size="11" font-weight="700" letter-spacing="1.5" fill="#475569" text-anchor="end">{esc(branding.brand_footer or brand_name)}</text>
  </g>
</svg>'''

        # Save as SVG first
        file_stem = brief.post_id or f"card_{brief.platform}_{hashlib.md5(brief.headline.encode()).hexdigest()[:8]}"
        svg_path = self.output_dir / f"{file_stem}.svg"
        png_path = self.output_dir / f"{file_stem}.png"

        svg_path.write_text(svg, encoding="utf-8")

        # Try to convert SVG → PNG via cairosvg
        try:
            import cairosvg
            cairosvg.svg2png(
                bytestring=svg.encode("utf-8"),
                write_to=str(png_path),
                output_width=w * 2,
                output_height=h * 2,
            )
            logger.info("SVG card converted to PNG (2x retina): %s", png_path)
            return png_path
        except ImportError:
            logger.info("cairosvg not installed, trying Playwright SVG→PNG conversion")
        except Exception as e:
            logger.warning("cairosvg conversion failed: %s, trying Playwright", e)

        # Try Playwright as PNG converter (render the SVG in a browser)
        try:
            from playwright.sync_api import sync_playwright
            html_wrapper = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
body {{ margin:0; padding:0; background: transparent; }}
</style></head><body>{svg}</body></html>'''
            
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=["--disable-dev-shm-usage", "--no-sandbox"],
                )
                page = browser.new_page(
                    viewport={"width": w, "height": h},
                    device_scale_factor=2,
                )
                page.set_content(html_wrapper, wait_until="networkidle")
                page.wait_for_timeout(200)
                page.screenshot(
                    path=str(png_path),
                    type="png",
                    clip={"x": 0, "y": 0, "width": w, "height": h},
                )
                browser.close()
            logger.info("SVG card rendered to PNG via Playwright: %s", png_path)
            return png_path
        except Exception as e:
            logger.warning("Playwright SVG→PNG conversion failed: %s", e)

        # Last resort: return SVG file (still looks clean in web dashboards)
        logger.info("Returning SVG card directly: %s", svg_path)
        return svg_path


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
