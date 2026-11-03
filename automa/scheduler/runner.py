"""
Persistent Scheduler and Autonomous Job Runner for Automa (Phase 7).
Manages APScheduler jobs, overdue post recovery, bounded exponential backoff retries,
and concurrency locks.
"""

from __future__ import annotations
import logging
import random
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from automa.config import get_settings, DATA_DIR, load_platforms_config
from automa.db.repository import PostRepository, PostRecord
from automa.engine.generator import ContentEngine
from automa.notifications.notifier import Notifier
from automa.publishers.direct import get_publisher
from automa.publishers.base import BasePublisher

logger = logging.getLogger("automa.scheduler.runner")


class SchedulerRunner:
    def __init__(
        self,
        repo: Optional[PostRepository] = None,
        publisher: Optional[BasePublisher] = None,
        engine: Optional[ContentEngine] = None,
        notifier: Optional[Notifier] = None,
    ):
        self.repo = repo or PostRepository()
        self.publisher = publisher or get_publisher()
        self.engine = engine or ContentEngine(repo=self.repo)
        self.notifier = notifier or Notifier()
        self.settings = get_settings()
        self.global_cfg, self.platforms = load_platforms_config()
        self.lock_file = DATA_DIR / "automa_runner.lock"

    def _acquire_concurrency_lock(self) -> bool:
        """Simple cross-process lock using file creation."""
        try:
            if self.lock_file.exists():
                # Check for stale lock (older than 10 minutes)
                mtime = self.lock_file.stat().st_mtime
                if (time.time() - mtime) > 600:
                    logger.warning("Cleaning up stale lock file.")
                    self.lock_file.unlink(missing_ok=True)
                else:
                    return False
            self.lock_file.touch(exist_ok=False)
            return True
        except Exception:
            return False

    def _release_concurrency_lock(self) -> None:
        try:
            self.lock_file.unlink(missing_ok=True)
        except Exception:
            pass

    def compute_exponential_backoff(self, retry_count: int, base_seconds: int = 300, max_seconds: int = 10800) -> datetime:
        """
        Computes bounded exponential backoff with full jitter:
        delay = min(max_seconds, base_seconds * (2 ** (retry_count - 1))) + jitter
        """
        exponent = max(0, retry_count - 1)
        raw_delay = min(max_seconds, base_seconds * (2 ** exponent))
        jitter = random.uniform(0, 30.0)
        total_delay = raw_delay + jitter
        return datetime.now(timezone.utc) + timedelta(seconds=total_delay)

    def recover_overdue_posts(self) -> int:
        """
        Recovers scheduled posts that were missed during system downtime.
        If missed within 12 hours, schedules immediate publishing.
        If older than 24 hours, safely bumps to next scheduled window.
        """
        now = datetime.now(timezone.utc)
        overdue_posts = self.repo.get_overdue_posts(now.isoformat())
        recovered_count = 0

        for post in overdue_posts:
            try:
                sched_time = datetime.fromisoformat(post.scheduled_at)
                delay_hours = (now - sched_time).total_seconds() / 3600.0

                if delay_hours <= 12.0:
                    # Missed recently during sleep/reboot: publish in upcoming cycle
                    logger.info("Recovering recently overdue post %s (Missed by %.1f hours)", post.id, delay_hours)
                    recovered_count += 1
                else:
                    # Too stale: reschedule into fresh future slot
                    new_sched = now + timedelta(hours=2)
                    post.scheduled_at = new_sched.isoformat()
                    self.repo.save_post(post)
                    self.repo.log_audit_event(
                        event_type="OVERDUE_RESCHEDULED",
                        post_id=post.id,
                        details=f"Post was overdue by {delay_hours:.1f} hours. Rescheduled to {new_sched.isoformat()}",
                    )
                    recovered_count += 1
            except Exception as e:
                logger.error("Error processing overdue post %s: %s", post.id, e)

        return recovered_count

    def process_due_posts(self, force: bool = False) -> Dict[str, Any]:
        """
        Queries all due SCHEDULED and RETRY_PENDING posts, invokes publisher,
        and transitions state machine atomically.
        If force=True, dispatches all scheduled posts immediately regardless of future time.
        """
        if not self._acquire_concurrency_lock():
            logger.info("Another process is currently holding the runner lock. Skipping cycle.")
            return {"status": "LOCKED", "published": 0, "failed": 0}

        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            due_posts = self.repo.get_all_scheduled_posts() if force else self.repo.get_scheduled_due_posts(now_iso)

            published_count = 0
            failed_count = 0

            for post in due_posts:
                logger.info("Publishing due post %s to %s", post.id, post.platform)
                res = self.publisher.publish(post)

                if res.success:
                    self.repo.update_post_status(
                        post_id=post.id,
                        status="PUBLISHED",
                        external_id=res.external_post_id,
                    )
                    self.repo.log_audit_event(
                        event_type="POST_PUBLISHED",
                        post_id=post.id,
                        details=f"Published to {post.platform}. External ID: {res.external_post_id}",
                    )
                    self.notifier.notify_routine_success(post.id, post.platform, res.external_post_id or "")
                    published_count += 1

                else:
                    # Failure handling
                    if res.is_transient_error:
                        new_retry_count = post.retry_count + 1
                        if new_retry_count < post.max_retries:
                            next_retry = self.compute_exponential_backoff(new_retry_count)
                            post.retry_count = new_retry_count
                            post.status = "RETRY_PENDING"
                            post.next_retry_at = next_retry.isoformat()
                            post.last_error = res.error_message
                            self.repo.save_post(post)
                            self.repo.log_audit_event(
                                event_type="PUBLISH_RETRY_SCHEDULED",
                                post_id=post.id,
                                details=f"Transient failure (Attempt {new_retry_count}/{post.max_retries}): {res.error_message}. Next retry: {next_retry.isoformat()}",
                            )
                            self.notifier.notify_post_failed(post.id, post.platform, post.topic, res.error_message or "", retries_exhausted=False)
                        else:
                            # Max retries exceeded
                            self.repo.update_post_status(post_id=post.id, status="FAILED", last_error=res.error_message)
                            self.repo.log_audit_event(
                                event_type="POST_FAILED_PERMANENT",
                                post_id=post.id,
                                details=f"Max retries ({post.max_retries}) exhausted. Error: {res.error_message}",
                            )
                            self.notifier.notify_post_failed(post.id, post.platform, post.topic, res.error_message or "", retries_exhausted=True)
                            failed_count += 1
                    else:
                        # Permanent error (auth failure, content policy, missing media)
                        self.repo.update_post_status(post_id=post.id, status="FAILED", last_error=res.error_message)
                        self.repo.log_audit_event(
                            event_type="POST_FAILED_PERMANENT",
                            post_id=post.id,
                            details=f"Permanent failure: {res.error_message}",
                        )
                        self.notifier.notify_post_failed(post.id, post.platform, post.topic, res.error_message or "", retries_exhausted=True)
                        failed_count += 1

            # Check if scheduled queue is now empty
            queue_counts = self.repo.get_queue_counts()
            if queue_counts.get("SCHEDULED", 0) == 0:
                self.notifier.notify_queue_exhausted()

            return {"status": "SUCCESS", "published": published_count, "failed": failed_count}

        finally:
            self._release_concurrency_lock()

    def publish_post_by_id(self, post_id: str) -> Dict[str, Any]:
        """
        Publishes a specific post immediately by ID without waiting for scheduled window.
        """
        post = self.repo.get_post_by_id(post_id)
        if not post:
            return {"success": False, "error": f"Post '{post_id}' not found."}

        logger.info("Directly publishing post %s to %s", post.id, post.platform)
        res = self.publisher.publish(post)

        if res.success:
            self.repo.update_post_status(
                post_id=post.id,
                status="PUBLISHED",
                external_id=res.external_post_id,
            )
            self.repo.log_audit_event(
                event_type="POST_PUBLISHED",
                post_id=post.id,
                details=f"Direct published to {post.platform}. External ID: {res.external_post_id}",
            )
            self.notifier.notify_routine_success(post.id, post.platform, res.external_post_id or "")
            return {
                "success": True,
                "post_id": post.id,
                "platform": post.platform,
                "external_id": res.external_post_id,
            }
        else:
            self.repo.update_post_status(
                post_id=post.id,
                status="FAILED",
                last_error=res.error_message,
            )
            self.repo.log_audit_event(
                event_type="POST_FAILED",
                post_id=post.id,
                details=f"Direct publishing failed: {res.error_message}",
            )
            return {
                "success": False,
                "post_id": post.id,
                "platform": post.platform,
                "error": res.error_message,
            }

    def run_generation_cycle(self) -> Dict[str, Any]:
        """Wrapper for scheduled generation with concurrency lock."""
        if not self._acquire_concurrency_lock():
            logger.info("Runner is locked. Skipping generation run.")
            return {"status": "LOCKED"}

        try:
            return self.engine.run_scheduled_generation()
        finally:
            self._release_concurrency_lock()

    def start_daemon(self, blocking: bool = True) -> Any:
        """
        Starts the persistent scheduler daemon.
        Configures generation jobs (Monday & Thursday 06:00 UTC)
        and publishing worker (every 10 minutes).
        """
        scheduler_cls = BlockingScheduler if blocking else BackgroundScheduler
        scheduler = scheduler_cls(timezone=self.global_cfg.timezone)

        # 1. Recover any overdue jobs upon startup
        recovered = self.recover_overdue_posts()
        if recovered > 0:
            logger.info("Recovered %d overdue posts on startup.", recovered)

        # 2. Add Content Generation Jobs (Mondays and Thursdays at 06:00 UTC)
        scheduler.add_job(
            func=self.run_generation_cycle,
            trigger=CronTrigger(day_of_week="mon,thu", hour=6, minute=0, timezone="UTC"),
            id="job_content_generation",
            name="Scheduled Content Generation",
            replace_existing=True,
            misfire_grace_time=3600,
        )

        # 3. Add Publishing Worker (runs every 10 minutes to process scheduled & retry posts)
        scheduler.add_job(
            func=self.process_due_posts,
            trigger=IntervalTrigger(minutes=10, timezone="UTC"),
            id="job_publishing_worker",
            name="Publishing Queue Worker",
            replace_existing=True,
            misfire_grace_time=300,
        )

        logger.info(
            "Automa Persistent Scheduler started (Timezone: %s). "
            "Running independent of interactive IDE.",
            self.global_cfg.timezone,
        )

        if blocking:
            try:
                scheduler.start()
            except (KeyboardInterrupt, SystemExit):
                logger.info("Scheduler received shutdown signal. Exiting cleanly.")
                self._release_concurrency_lock()
        else:
            scheduler.start()
            return scheduler
