"""
Configuration Loader & Knowledge Base Parser for Automa.
Reads brand.md, platforms.yaml, and markdown knowledge files.
"""

from __future__ import annotations
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
KNOWLEDGE_DIR = BASE_DIR / "knowledge"
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
CONTENT_DIR = BASE_DIR / "content"

# Ensure runtime directories exist
for directory in [DATA_DIR, LOGS_DIR, CONTENT_DIR / "queue", CONTENT_DIR / "published", CONTENT_DIR / "rejected"]:
    directory.mkdir(parents=True, exist_ok=True)

# Load environment variables
load_dotenv(BASE_DIR / ".env")


class PlatformConstraints(BaseModel):
    max_characters: Optional[int] = 3000
    min_characters: Optional[int] = 100
    optimal_character_range: Optional[List[int]] = [500, 1500]
    max_characters_per_tweet: Optional[int] = 280
    allow_threads: Optional[bool] = False
    max_thread_tweets: Optional[int] = 5
    max_caption_characters: Optional[int] = 2200
    optimal_caption_range: Optional[List[int]] = [300, 800]
    max_hashtags: int = 3
    max_emojis: int = 2
    allow_external_links: bool = True
    require_media: bool = False
    default_aspect_ratio: Optional[str] = "1:1"


class PlatformStyleGuidelines(BaseModel):
    structure: str = ""
    prohibited_phrases: List[str] = Field(default_factory=list)


class PlatformConfig(BaseModel):
    enabled: bool = True
    name: str
    target_posts_per_week: int = 2
    min_spacing_hours: int = 24
    preferred_days: List[str] = Field(default_factory=list)
    preferred_times_utc: List[str] = Field(default_factory=list)
    constraints: PlatformConstraints = Field(default_factory=PlatformConstraints)
    style_guidelines: PlatformStyleGuidelines = Field(default_factory=PlatformStyleGuidelines)


class GlobalConfig(BaseModel):
    timezone: str = "UTC"
    conservative_weekly_cap: int = 5
    min_inter_platform_spacing_hours: int = 4
    max_auto_revisions: int = 2
    min_passing_score: int = 85


class BrandingConfig(BaseModel):
    """Configurable branding for generated editorial cards."""
    brand_name: str = "AUTOMA"
    brand_subtitle: str = "AUTONOMOUS ENGINEERING"
    brand_footer: str = "AUTOMA"
    accent_primary: str = "#2563eb"
    accent_secondary: str = "#06b6d4"


def get_branding() -> BrandingConfig:
    """Load branding configuration from environment variables."""
    return BrandingConfig(
        brand_name=os.getenv("BRAND_NAME", "AUTOMA"),
        brand_subtitle=os.getenv("BRAND_SUBTITLE", "AUTONOMOUS ENGINEERING"),
        brand_footer=os.getenv("BRAND_FOOTER", "AUTOMA"),
        accent_primary=os.getenv("BRAND_ACCENT_PRIMARY", "#2563eb"),
        accent_secondary=os.getenv("BRAND_ACCENT_SECONDARY", "#06b6d4"),
    )


class AppSettings(BaseModel):
    dry_run: bool = True
    environment: str = "development"
    timezone: str = "UTC"
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-2.5-flash"
    publisher_type: str = "dry_run"
    postiz_base_url: str = "https://api.postiz.com/public/v1"
    postiz_api_key: Optional[str] = None
    postiz_linkedin_integration_id: Optional[str] = None
    postiz_x_integration_id: Optional[str] = None
    postiz_instagram_integration_id: Optional[str] = None
    notification_webhook_url: Optional[str] = None
    notify_on_failure: bool = True
    notify_on_review_needed: bool = True
    notify_on_success: bool = False
    web_host: str = "127.0.0.1"
    web_port: int = 8080
    allowed_origins: str = ""


def get_settings() -> AppSettings:
    """Load settings from environment variables."""
    return AppSettings(
        dry_run=os.getenv("DRY_RUN", "true").lower() in ("true", "1", "yes"),
        environment=os.getenv("ENVIRONMENT", "development"),
        timezone=os.getenv("TIMEZONE", "UTC"),
        gemini_api_key=os.getenv("GEMINI_API_KEY"),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        publisher_type=os.getenv("PUBLISHER_TYPE", "dry_run").lower(),
        postiz_base_url=os.getenv("POSTIZ_BASE_URL", "https://api.postiz.com/public/v1").rstrip("/"),
        postiz_api_key=os.getenv("POSTIZ_API_KEY"),
        postiz_linkedin_integration_id=os.getenv("POSTIZ_LINKEDIN_INTEGRATION_ID"),
        postiz_x_integration_id=os.getenv("POSTIZ_X_INTEGRATION_ID"),
        postiz_instagram_integration_id=os.getenv("POSTIZ_INSTAGRAM_INTEGRATION_ID"),
        notification_webhook_url=os.getenv("NOTIFICATION_WEBHOOK_URL"),
        notify_on_failure=os.getenv("NOTIFY_ON_FAILURE", "true").lower() in ("true", "1", "yes"),
        notify_on_review_needed=os.getenv("NOTIFY_ON_REVIEW_NEEDED", "true").lower() in ("true", "1", "yes"),
        notify_on_success=os.getenv("NOTIFY_ON_SUCCESS", "false").lower() in ("true", "1", "yes"),
        web_host=os.getenv("WEB_HOST", "0.0.0.0" if os.getenv("ENVIRONMENT") == "production" else "127.0.0.1"),
        web_port=int(os.getenv("PORT", os.getenv("WEB_PORT", "8080"))),
        allowed_origins=os.getenv("ALLOWED_ORIGINS", ""),
    )


def load_platforms_config() -> tuple[GlobalConfig, Dict[str, PlatformConfig]]:
    """Loads and parses platforms.yaml."""
    platforms_file = CONFIG_DIR / "platforms.yaml"
    if not platforms_file.exists():
        return GlobalConfig(), {}

    with open(platforms_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    global_data = data.get("global", {})
    global_cfg = GlobalConfig(**global_data)

    platforms_data = data.get("platforms", {})
    platforms: Dict[str, PlatformConfig] = {}
    for name, p_data in platforms_data.items():
        platforms[name] = PlatformConfig(**p_data)

    return global_cfg, platforms


def load_brand_manifest() -> str:
    """Reads brand.md content."""
    brand_file = CONFIG_DIR / "brand.md"
    if not brand_file.exists():
        return "Brand manifest file missing."
    with open(brand_file, "r", encoding="utf-8") as f:
        return f.read()


def load_knowledge_base() -> Dict[str, str]:
    """Reads all markdown files in the knowledge directory."""
    knowledge: Dict[str, str] = {}
    if not KNOWLEDGE_DIR.exists():
        return knowledge

    for md_file in KNOWLEDGE_DIR.glob("*.md"):
        with open(md_file, "r", encoding="utf-8") as f:
            knowledge[md_file.stem] = f.read()

    return knowledge
