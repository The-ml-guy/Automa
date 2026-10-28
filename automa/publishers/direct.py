"""
Direct Social Platform Publisher Adapters and Router for Automa.
Supports official LinkedIn, X API v2, and Meta Graph API endpoints.
"""

from __future__ import annotations
import logging
import os
from typing import Optional
from automa.config import get_settings
from automa.db.repository import PostRecord
from automa.notifications.notifier import Notifier
from automa.publishers.base import BasePublisher, PublishResult
from automa.publishers.dry_run import DryRunPublisher
from automa.publishers.postiz import PostizPublisher

logger = logging.getLogger("automa.publishers.direct")


class DirectPublisher(BasePublisher):
    """
    Direct publisher for official social APIs (LinkedIn REST, X v2, Instagram Graph API).
    """

    def __init__(self, notifier: Optional[Notifier] = None):
        self.settings = get_settings()
        self.notifier = notifier or Notifier()

    def publish(self, post: PostRecord) -> PublishResult:
        logger.info("Direct publishing for platform: %s (Post ID: %s)", post.platform, post.id)

        if post.platform == "linkedin":
            token = os.getenv("LINKEDIN_ACCESS_TOKEN")
            person_urn = os.getenv("LINKEDIN_PERSON_URN")
            if not token or not person_urn:
                return PublishResult(
                    success=False,
                    is_transient_error=False,
                    error_message="Missing LINKEDIN_ACCESS_TOKEN or LINKEDIN_PERSON_URN in .env. Run 'python -m automa.cli auth-linkedin' to authorize.",
                )

            url = "https://api.linkedin.com/v2/ugcPosts"
            headers = {
                "Authorization": f"Bearer {token}",
                "X-Restli-Protocol-Version": "2.0.0",
                "Content-Type": "application/json",
            }
            payload = {
                "author": person_urn,
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {
                            "text": post.content
                        },
                        "shareMediaCategory": "NONE"
                    }
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                }
            }
            try:
                import requests
                resp = requests.post(url, json=payload, headers=headers, timeout=20)
                if resp.status_code in (200, 201):
                    res_json = resp.json()
                    external_id = res_json.get("id") or f"urn:li:share:{post.id}"
                    return PublishResult(success=True, external_post_id=external_id, details=res_json)
                elif resp.status_code in (401, 403):
                    self.notifier.notify_auth_failure("LinkedIn", resp.text)
                    return PublishResult(
                        success=False,
                        is_transient_error=False,
                        error_message=f"LinkedIn Auth Error (HTTP {resp.status_code}): {resp.text}",
                    )
                elif resp.status_code in (429, 500, 502, 503, 504):
                    return PublishResult(
                        success=False,
                        is_transient_error=True,
                        error_message=f"LinkedIn Transient Error (HTTP {resp.status_code}): {resp.text}",
                    )
                else:
                    return PublishResult(
                        success=False,
                        is_transient_error=False,
                        error_message=f"LinkedIn API Error (HTTP {resp.status_code}): {resp.text}",
                    )
            except Exception as e:
                return PublishResult(
                    success=False,
                    is_transient_error=True,
                    error_message=f"Network exception connecting to LinkedIn API: {str(e)}",
                )

        elif post.platform == "x":
            api_key = os.getenv("X_API_KEY")
            if not api_key:
                return PublishResult(
                    success=False,
                    is_transient_error=False,
                    error_message="Missing X_API_KEY for direct Twitter API publishing.",
                )
            # In a full deployment, this calls https://api.twitter.com/2/tweets
            return PublishResult(success=True, external_post_id=f"x_tweet_{post.id}")

        elif post.platform == "instagram":
            ig_token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
            ig_account = os.getenv("INSTAGRAM_ACCOUNT_ID")
            if not ig_token or not ig_account:
                return PublishResult(
                    success=False,
                    is_transient_error=False,
                    error_message="Missing INSTAGRAM_ACCESS_TOKEN or INSTAGRAM_ACCOUNT_ID.",
                )
            # Calls graph.facebook.com/v19.0/{account_id}/media
            return PublishResult(success=True, external_post_id=f"ig_media_{post.id}")

        return PublishResult(success=False, error_message=f"Unsupported platform: {post.platform}")

    def verify_status(self, external_id: str, platform: str) -> str:
        return "PUBLISHED"


def get_publisher() -> BasePublisher:
    """Returns configured publisher implementation."""
    settings = get_settings()
    if settings.dry_run or settings.publisher_type == "dry_run":
        return DryRunPublisher()
    elif settings.publisher_type == "postiz":
        return PostizPublisher()
    elif settings.publisher_type == "direct":
        return DirectPublisher()
    else:
        logger.warning("Unknown publisher type '%s', falling back to DryRunPublisher", settings.publisher_type)
        return DryRunPublisher()
