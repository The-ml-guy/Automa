"""
Notification Dispatcher and Digest Generator for Automa.
Routes actionable alerts and weekly/daily digests while enforcing secret scrubbing.
"""

from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Any
import requests
from automa.config import get_settings, LOGS_DIR
from automa.notifications.scrubber import scrub_secrets

# Configure file and console logging
LOG_FILE = LOGS_DIR / "automa.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(str(LOG_FILE), encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("automa")


class Notifier:
    def __init__(self):
        self.settings = get_settings()

    def _send_webhook(self, title: str, message: str, level: str = "INFO", fields: Optional[Dict[str, str]] = None) -> bool:
        """Sends a scrubbed JSON payload to the configured webhook URL."""
        if not self.settings.notification_webhook_url:
            return False

        clean_title = scrub_secrets(title)
        clean_msg = scrub_secrets(message)
        clean_fields = {k: scrub_secrets(str(v)) for k, v in (fields or {}).items()}

        payload = {
            "title": f"[{level}] {clean_title}",
            "text": clean_msg,
            "level": level,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": clean_fields,
        }

        try:
            resp = requests.post(
                self.settings.notification_webhook_url,
                json=payload,
                timeout=10,
                headers={"Content-Type": "application/json"},
            )
            return resp.status_code in (200, 204)
        except Exception as e:
            logger.error("Failed to send webhook notification: %s", scrub_secrets(str(e)))
            return False

    def notify_action_required(self, alert_type: str, title: str, details: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Fires an alert when human intervention is strictly required."""
        msg = f"[ACTION REQUIRED: {alert_type}] {title}\n{details}"
        logger.warning(scrub_secrets(msg))
        self._send_webhook(
            title=f"Action Required: {alert_type}",
            message=details,
            level="WARNING",
            fields={"Type": alert_type, **(context or {})},
        )

    def notify_auth_failure(self, service: str, error: str) -> None:
        """Called when platform authentication or permissions expire."""
        self.notify_action_required(
            alert_type="AUTH_EXPIRED",
            title=f"Authentication Failure on {service}",
            details=f"The credentials or access token for {service} have expired or been rejected. Error: {error}",
            context={"Service": service},
        )

    def notify_post_failed(self, post_id: str, platform: str, topic: str, error: str, retries_exhausted: bool) -> None:
        """Called when a post fails. Alerts user if max retries have been exhausted."""
        if retries_exhausted and self.settings.notify_on_failure:
            self.notify_action_required(
                alert_type="PUBLISH_FAILED",
                title=f"Post on {platform} Exhausted Retries",
                details=f"Post ID: {post_id}\nTopic: {topic}\nError: {error}\nMarked as FAILED.",
                context={"PostID": post_id, "Platform": platform},
            )
        else:
            logger.info("Transient publish failure for %s (will retry): %s", post_id, scrub_secrets(error))

    def notify_manual_review_needed(self, post_id: str, platform: str, topic: str, reason: str) -> None:
        """Called when safety policy flags a high-stakes draft."""
        if self.settings.notify_on_review_needed:
            self.notify_action_required(
                alert_type="MANUAL_REVIEW_REQUIRED",
                title=f"Draft requires manual review: {topic}",
                details=f"Draft for {platform} flagged by autonomous safety policy.\nReason: {reason}\nPost ID: {post_id}",
                context={"PostID": post_id, "Platform": platform, "Reason": reason},
            )

    def notify_queue_exhausted(self) -> None:
        """Called when scheduled queue has zero posts remaining."""
        self.notify_action_required(
            alert_type="QUEUE_EXHAUSTED",
            title="Content Queue is Empty",
            details="All scheduled posts have been published. Next scheduled generation run will populate new drafts.",
        )

    def notify_routine_success(self, post_id: str, platform: str, external_id: str) -> None:
        """Logs routine publication. Webhook only sent if NOTIFY_ON_SUCCESS=true."""
        logger.info("Successfully published post %s on %s (External ID: %s)", post_id, platform, external_id)
        if self.settings.notify_on_success:
            self._send_webhook(
                title=f"Published to {platform}",
                message=f"Post {post_id} published successfully. External ID: {external_id}",
                level="INFO",
                fields={"PostID": post_id, "Platform": platform, "ExternalID": external_id},
            )

    def generate_digest(self, published_posts: list, failed_posts: list, skipped_runs: int, health_status: str) -> str:
        """Generates a concise markdown digest report."""
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        report = [
            f"# Automa Publishing Digest — {now_str}",
            f"- **System Health**: {health_status}",
            f"- **Published Posts**: {len(published_posts)}",
            f"- **Failed Posts**: {len(failed_posts)}",
            f"- **Skipped Slots**: {skipped_runs}",
            "",
            "### Published Posts Summary",
        ]
        if published_posts:
            for p in published_posts:
                report.append(f"- **[{p.platform.upper()}]** {p.topic} (ID: `{p.id}`, Published: {p.published_at})")
        else:
            report.append("_No posts published in this window._")

        report.append("")
        report.append("### Issues & Failures")
        if failed_posts:
            for f in failed_posts:
                report.append(f"- **[{f.platform.upper()}]** {f.topic} — Error: `{scrub_secrets(f.last_error or 'Unknown')}`")
        else:
            report.append("_Zero failures._")

        return "\n".join(report)
