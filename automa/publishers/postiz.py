"""
Postiz API Publisher for Automa (Phase 1, 7 & 10).
Integrates with Postiz self-hosted and cloud REST endpoints (/public/v1/posts).
"""

from __future__ import annotations
import logging
from typing import Dict, Optional, Any
import requests
from automa.config import get_settings
from automa.db.repository import PostRecord
from automa.notifications.notifier import Notifier
from automa.notifications.scrubber import scrub_secrets
from automa.publishers.base import BasePublisher, PublishResult

logger = logging.getLogger("automa.publishers.postiz")


class PostizPublisher(BasePublisher):
    def __init__(self, notifier: Optional[Notifier] = None):
        self.settings = get_settings()
        self.notifier = notifier or Notifier()
        self.base_url = self.settings.postiz_base_url
        self.api_key = self.settings.postiz_api_key

    def _get_integration_id(self, platform: str) -> Optional[str]:
        if platform == "linkedin":
            return self.settings.postiz_linkedin_integration_id
        elif platform == "x":
            return self.settings.postiz_x_integration_id
        elif platform == "instagram":
            return self.settings.postiz_instagram_integration_id
        return None

    def publish(self, post: PostRecord) -> PublishResult:
        if not self.api_key:
            return PublishResult(
                success=False,
                is_transient_error=False,
                error_message="POSTIZ_API_KEY is missing from configuration.",
            )

        integration_id = self._get_integration_id(post.platform)
        if not integration_id:
            return PublishResult(
                success=False,
                is_transient_error=False,
                error_message=f"Missing Postiz integration ID for platform: {post.platform}",
            )

        endpoint = f"{self.base_url}/posts"
        headers = {
            "Authorization": self.api_key,
            "Content-Type": "application/json",
            "Idempotency-Key": post.idempotency_key,
        }

        # Build Postiz multi-post value structure
        post_value: Dict[str, Any] = {
            "content": post.content,
            "image": post.media_urls or [],
        }

        # Platform specific settings tag
        platform_type_map = {
            "linkedin": "linkedin",
            "x": "x",
            "instagram": "instagram",
        }

        payload = {
            "type": "now",
            "shortLink": False,
            "tags": ["automa", post.platform],
            "posts": [
                {
                    "integration": {"id": integration_id},
                    "value": [post_value],
                    "settings": {
                        "__type": platform_type_map.get(post.platform, post.platform)
                    },
                }
            ],
        }

        try:
            logger.info("Submitting post %s to Postiz API (%s)", post.id, endpoint)
            resp = requests.post(endpoint, json=payload, headers=headers, timeout=20)

            if resp.status_code in (200, 201):
                data = resp.json()
                external_id = data.get("id") or data.get("postId") or f"postiz_{post.id}"
                return PublishResult(
                    success=True,
                    external_post_id=str(external_id),
                    is_transient_error=False,
                    details=data,
                )
            elif resp.status_code in (401, 403):
                error_msg = f"Postiz Authentication / Permission Error: HTTP {resp.status_code} - {resp.text}"
                self.notifier.notify_auth_failure("Postiz", scrub_secrets(resp.text))
                return PublishResult(
                    success=False,
                    is_transient_error=False,
                    error_message=error_msg,
                )
            elif resp.status_code in (429, 500, 502, 503, 504):
                error_msg = f"Postiz Transient Server Error: HTTP {resp.status_code} - {resp.text}"
                return PublishResult(
                    success=False,
                    is_transient_error=True,
                    error_message=error_msg,
                )
            else:
                return PublishResult(
                    success=False,
                    is_transient_error=False,
                    error_message=f"Postiz Permanent Error: HTTP {resp.status_code} - {resp.text}",
                )

        except requests.exceptions.Timeout:
            return PublishResult(
                success=False,
                is_transient_error=True,
                error_message="Network timeout while connecting to Postiz API.",
            )
        except requests.exceptions.ConnectionError as ce:
            return PublishResult(
                success=False,
                is_transient_error=True,
                error_message=f"Connection error to Postiz API: {str(ce)}",
            )
        except Exception as e:
            return PublishResult(
                success=False,
                is_transient_error=True,
                error_message=f"Unexpected error calling Postiz: {str(e)}",
            )

    def verify_status(self, external_id: str, platform: str) -> str:
        """Verifies publication state via Postiz /posts/:id."""
        if not self.api_key:
            return "UNKNOWN"

        try:
            endpoint = f"{self.base_url}/posts/{external_id}"
            headers = {"Authorization": self.api_key}
            resp = requests.get(endpoint, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("status", "PUBLISHED").upper()
        except Exception:
            pass
        return "CONFIRMED"
