"""
Automa Auto-Start Entry Point.
Runs the full pipeline once on startup, then starts the web dashboard + scheduler daemon.
Designed to be triggered by Windows Task Scheduler at logon.
"""

from __future__ import annotations
import logging
import sys
import threading
import time
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from automa.config import get_settings, BASE_DIR
from automa.db.schema import init_db
from automa.db.repository import PostRepository
from automa.engine.generator import ContentEngine
from automa.scheduler.runner import SchedulerRunner
from automa.web.server import run_dashboard_server

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(BASE_DIR / "data" / "automa_autostart.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("automa.autostart")


def run_startup_pipeline():
    """Run a content generation cycle on startup to create fresh posts."""
    try:
        logger.info("=== STARTUP PIPELINE: Beginning content generation ===")
        engine = ContentEngine()
        result = engine.run_scheduled_generation(force=True)
        logger.info(
            "Startup pipeline complete: status=%s, scheduled=%s, generated=%s",
            result.get("status"),
            result.get("scheduled_count", 0),
            result.get("generated_count", 0),
        )
    except Exception as e:
        logger.error("Startup pipeline failed (non-fatal): %s", e, exc_info=True)


def run_web_server():
    """Run the web dashboard in a background thread."""
    try:
        settings = get_settings()
        host = settings.web_host if hasattr(settings, "web_host") else "127.0.0.1"
        port = settings.web_port if hasattr(settings, "web_port") else 8080
        logger.info("Starting web dashboard at http://%s:%s", host, port)
        run_dashboard_server(host=host, port=port)
    except Exception as e:
        logger.error("Web server crashed: %s", e, exc_info=True)


def run_scheduler_daemon():
    """Run the APScheduler daemon (blocking) — generation + publishing jobs."""
    try:
        logger.info("Starting scheduler daemon...")
        runner = SchedulerRunner()
        runner.start_daemon(blocking=True)
    except Exception as e:
        logger.error("Scheduler daemon crashed: %s", e, exc_info=True)


def main():
    logger.info("=" * 60)
    logger.info("  AUTOMA AUTO-START — %s", time.strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("=" * 60)

    # Initialize database
    init_db()

    # Step 1: Run the content pipeline once to generate fresh posts
    run_startup_pipeline()

    # Step 2: Start web dashboard in background thread
    web_thread = threading.Thread(target=run_web_server, daemon=True, name="automa-web")
    web_thread.start()
    logger.info("Web dashboard thread started.")

    # Small delay to let the web server bind
    time.sleep(2)

    # Step 3: Start scheduler daemon (blocking — keeps process alive)
    # This runs content generation on Mon/Thu at 06:00 UTC
    # and the publishing worker every 10 minutes
    run_scheduler_daemon()


if __name__ == "__main__":
    main()

