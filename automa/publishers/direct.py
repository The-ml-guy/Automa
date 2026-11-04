"""
Direct Social Platform Publisher Adapters and Router for Automa.
Supports official LinkedIn, X API v2, and Meta Graph API endpoints.
"""

from __future__ import annotations
import logging
import os
from pathlib import Path
from typing import Optional, Dict, Any
from automa.config import get_settings, BASE_DIR, CONTENT_DIR
from automa.db.repository import PostRecord
from automa.notifications.notifier import Notifier
from automa.publishers.base import BasePublisher, PublishResult
from automa.publishers.dry_run import DryRunPublisher
from automa.publishers.postiz import PostizPublisher

logger = logging.getLogger("automa.publishers.direct")


def _clean_env(val: Optional[str]) -> Optional[str]:
    """Strips leading/trailing whitespace and quotes that may be introduced via UI pasting."""
    if not val:
        return None
    val = val.strip().strip('"').strip("'").strip()
    return val if val else None


def _clean_token(val: Optional[str]) -> Optional[str]:
    """Cleans a token string, stripping quotes, whitespace, and any accidental 'Bearer ' prefix."""
    cleaned = _clean_env(val)
    if not cleaned:
        return None
    if cleaned.lower().startswith("bearer "):
        cleaned = cleaned[7:].strip()
    return cleaned


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
            token = _clean_token(os.getenv("LINKEDIN_ACCESS_TOKEN"))
            person_urn = _clean_env(os.getenv("LINKEDIN_PERSON_URN"))
            if not token or not person_urn:
                return PublishResult(
                    success=False,
                    is_transient_error=False,
                    error_message="Missing LINKEDIN_ACCESS_TOKEN or LINKEDIN_PERSON_URN in .env. Run 'python -m automa.cli auth-linkedin' to authorize.",
                )

            # Check for local image attachment
            image_urn = None
            if post.media_urls:
                for m_url in post.media_urls:
                    resolved_path = Path(m_url)
                    if not resolved_path.is_absolute():
                        resolved_path = BASE_DIR / resolved_path
                    if resolved_path.exists():
                        image_urn = self._upload_linkedin_image(token, person_urn, str(resolved_path))
                        if image_urn:
                            break

            share_content: Dict[str, Any] = {
                "shareCommentary": {
                    "text": post.content
                },
                "shareMediaCategory": "IMAGE" if image_urn else "NONE"
            }
            if image_urn:
                share_content["media"] = [
                    {
                        "status": "READY",
                        "description": {"text": post.topic[:200]},
                        "media": image_urn,
                        "title": {"text": post.topic[:200]},
                    }
                ]

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
                    "com.linkedin.ugc.ShareContent": share_content
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
            api_key = _clean_env(os.getenv("X_API_KEY"))
            api_secret = _clean_env(os.getenv("X_API_SECRET"))
            access_token = _clean_token(os.getenv("X_ACCESS_TOKEN"))
            access_secret = _clean_env(os.getenv("X_ACCESS_SECRET"))
            if not all([api_key, api_secret, access_token, access_secret]):
                return PublishResult(
                    success=False,
                    is_transient_error=False,
                    error_message="Missing X API credentials in .env (requires X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET).",
                )

            try:
                import requests
                from requests_oauthlib import OAuth1
                auth = OAuth1(api_key, api_secret, access_token, access_secret)
                url = "https://api.twitter.com/2/tweets"

                # Check for local image attachment for X
                x_media_id = None
                if post.media_urls:
                    for m_url in post.media_urls:
                        resolved_path = Path(m_url)
                        if not resolved_path.is_absolute():
                            resolved_path = BASE_DIR / resolved_path
                        if resolved_path.exists():
                            x_media_id = self._upload_x_image(auth, str(resolved_path))
                            if x_media_id:
                                break

                # If post has multiple thread items, post as threaded reply chain
                if post.thread_items and len(post.thread_items) > 1:
                    first_payload: Dict[str, Any] = {"text": post.thread_items[0]}
                    if x_media_id:
                        first_payload["media"] = {"media_ids": [x_media_id]}
                    first_resp = requests.post(url, json=first_payload, auth=auth, timeout=20)
                    if first_resp.status_code not in (200, 201):
                        return PublishResult(
                            success=False,
                            is_transient_error=first_resp.status_code in (429, 500, 502, 503),
                            error_message=f"X API Error (HTTP {first_resp.status_code}): {first_resp.text}",
                        )
                    first_id = first_resp.json().get("data", {}).get("id", f"x_{post.id}")
                    prev_id = first_id

                    for item in post.thread_items[1:]:
                        r_payload = {"text": item, "reply": {"in_reply_to_tweet_id": prev_id}}
                        r_resp = requests.post(url, json=r_payload, auth=auth, timeout=20)
                        if r_resp.status_code in (200, 201):
                            prev_id = r_resp.json().get("data", {}).get("id", prev_id)

                    return PublishResult(success=True, external_post_id=first_id, details={"first_id": first_id})
                else:
                    payload: Dict[str, Any] = {"text": post.content}
                    if x_media_id:
                        payload["media"] = {"media_ids": [x_media_id]}
                    resp = requests.post(url, json=payload, auth=auth, timeout=20)
                    if resp.status_code in (200, 201):
                        data = resp.json()
                        tweet_id = data.get("data", {}).get("id", f"x_{post.id}")
                        return PublishResult(success=True, external_post_id=tweet_id, details=data)
                    elif resp.status_code in (401, 403):
                        self.notifier.notify_auth_failure("X (Twitter)", resp.text)
                        return PublishResult(
                            success=False,
                            is_transient_error=False,
                            error_message=f"X Auth/Permission Error (HTTP {resp.status_code}): {resp.text}",
                        )
                    elif resp.status_code in (429, 500, 502, 503, 504):
                        return PublishResult(
                            success=False,
                            is_transient_error=True,
                            error_message=f"X Transient Rate-Limit/Error (HTTP {resp.status_code}): {resp.text}",
                        )
                    else:
                        return PublishResult(
                            success=False,
                            is_transient_error=False,
                            error_message=f"X API Error (HTTP {resp.status_code}): {resp.text}",
                        )
            except Exception as e:
                return PublishResult(
                    success=False,
                    is_transient_error=True,
                    error_message=f"Network exception connecting to X API: {str(e)}",
                )

        elif post.platform == "instagram":
            ig_token = _clean_token(os.getenv("INSTAGRAM_ACCESS_TOKEN"))
            ig_account = _clean_env(os.getenv("INSTAGRAM_ACCOUNT_ID"))
            if not ig_token or not ig_account:
                return PublishResult(
                    success=False,
                    is_transient_error=False,
                    error_message="Missing INSTAGRAM_ACCESS_TOKEN or INSTAGRAM_ACCOUNT_ID in .env.",
                )

            # Determine public image URL
            image_url = None
            if post.media_urls:
                for url in post.media_urls:
                    if url.startswith("http://") or url.startswith("https://"):
                        image_url = url
                        break

            # If no direct HTTP URL, resolve local media card via Cloudflare Tunnel
            if not image_url:
                from automa.tunnel import get_tunnel_url, start_tunnel
                tunnel_url = get_tunnel_url() or start_tunnel()

                if post.media_urls:
                    for url in post.media_urls:
                        filename = Path(url).name
                        media_file = CONTENT_DIR / "media" / filename
                        if not media_file.exists():
                            media_file = BASE_DIR / "content" / "media" / filename
                        if media_file.exists() and tunnel_url:
                            image_url = f"{tunnel_url.rstrip('/')}/media/{filename}"
                            break

                # If no media exists yet, auto-render editorial card
                if not image_url and tunnel_url:
                    try:
                        from automa.media.renderer import build_brief_from_research, EditorialCardRenderer
                        renderer = EditorialCardRenderer()
                        card_brief = build_brief_from_research(
                            item_title=post.topic,
                            item_abstract=post.content[:300] if post.content else "",
                            raw_metadata=None,
                            distillation_problem=None,
                            distillation_core_idea=post.content[:200] if post.content else None,
                            distillation_what_is_new=None,
                            distillation_limitations=None,
                            platform="instagram",
                            post_id=post.id,
                        )
                        card_path = renderer.render(card_brief)
                        post.media_urls = [str(card_path)]
                        filename = Path(card_path).name
                        image_url = f"{tunnel_url.rstrip('/')}/media/{filename}"
                    except Exception as err:
                        logger.warning("Could not auto-render Instagram card: %s", err)

            # Fallback high-resolution architectural image asset if local placeholder
            if not image_url:
                image_url = "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=1080&q=80"

            api_host = os.getenv("INSTAGRAM_API_HOST", "graph.facebook.com")
            container_url = f"https://{api_host}/v20.0/{ig_account}/media"
            publish_url = f"https://{api_host}/v20.0/{ig_account}/media_publish"

            try:
                import requests
                # Step 1: Create Media Container
                c_payload = {
                    "image_url": image_url,
                    "caption": post.content,
                    "access_token": ig_token,
                }
                c_resp = requests.post(container_url, data=c_payload, timeout=30)
                if c_resp.status_code not in (200, 201):
                    return PublishResult(
                        success=False,
                        is_transient_error=c_resp.status_code in (429, 500, 502, 503),
                        error_message=f"Instagram Container Error (HTTP {c_resp.status_code}): {c_resp.text}",
                    )

                creation_id = c_resp.json().get("id")

                # Step 1.5: Wait for Meta container readiness
                import time
                status_url = f"https://{api_host}/v20.0/{creation_id}?fields=status_code&access_token={ig_token}"
                for _ in range(12):
                    time.sleep(2)
                    try:
                        s_resp = requests.get(status_url, timeout=10)
                        if s_resp.status_code == 200:
                            s_data = s_resp.json()
                            s_code = s_data.get("status_code")
                            if s_code == "FINISHED":
                                break
                            elif s_code == "ERROR":
                                return PublishResult(
                                    success=False,
                                    is_transient_error=False,
                                    error_message=f"Instagram Container Processing Failed: {s_resp.text}",
                                )
                    except Exception:
                        pass

                # Step 2: Publish Container
                p_payload = {
                    "creation_id": creation_id,
                    "access_token": ig_token,
                }
                p_resp = requests.post(publish_url, data=p_payload, timeout=30)
                if p_resp.status_code in (200, 201):
                    media_id = p_resp.json().get("id")
                    return PublishResult(success=True, external_post_id=media_id, details=p_resp.json())
                else:
                    return PublishResult(
                        success=False,
                        is_transient_error=p_resp.status_code in (429, 500, 502, 503),
                        error_message=f"Instagram Publish Error (HTTP {p_resp.status_code}): {p_resp.text}",
                    )
            except Exception as e:
                return PublishResult(
                    success=False,
                    is_transient_error=True,
                    error_message=f"Network exception connecting to Instagram API: {str(e)}",
                )

        return PublishResult(success=False, error_message=f"Unsupported platform: {post.platform}")

    def _upload_linkedin_image(self, token: str, person_urn: str, image_path: str) -> Optional[str]:
        """
        Registers upload and pushes binary image asset to LinkedIn UGC media service.
        Returns the asset URN on success, or None on failure.
        """
        try:
            import requests
            reg_url = "https://api.linkedin.com/v2/assets?action=registerUpload"
            headers = {
                "Authorization": f"Bearer {token}",
                "X-Restli-Protocol-Version": "2.0.0",
                "Content-Type": "application/json",
            }
            reg_payload = {
                "registerUploadRequest": {
                    "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                    "owner": person_urn,
                    "serviceRelationships": [
                        {
                            "relationshipType": "OWNER",
                            "identifier": "urn:li:userGeneratedContent",
                        }
                    ],
                }
            }
            reg_resp = requests.post(reg_url, json=reg_payload, headers=headers, timeout=20)
            if reg_resp.status_code not in (200, 201):
                logger.warning("LinkedIn registerUpload failed (%s): %s", reg_resp.status_code, reg_resp.text)
                return None

            reg_data = reg_resp.json()
            upload_url = reg_data["value"]["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
            asset_urn = reg_data["value"]["asset"]

            with open(image_path, "rb") as f:
                img_bytes = f.read()

            up_headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "image/png",
            }
            up_resp = requests.post(upload_url, data=img_bytes, headers=up_headers, timeout=30)
            if up_resp.status_code in (200, 201):
                logger.info("Successfully uploaded LinkedIn image asset: %s", asset_urn)
                return asset_urn
            else:
                logger.warning("LinkedIn binary upload failed (%s): %s", up_resp.status_code, up_resp.text)
                return None
        except Exception as e:
            logger.warning("Exception during LinkedIn image upload: %s", e)
            return None

    def _upload_x_image(self, auth: Any, image_path: str) -> Optional[str]:
        """
        Uploads image binary to Twitter v1.1 upload endpoint.
        Returns media_id_string on success, or None on failure.
        """
        try:
            import requests
            upload_url = "https://upload.twitter.com/1.1/media/upload.json"
            with open(image_path, "rb") as f:
                files = {"media": f}
                resp = requests.post(upload_url, files=files, auth=auth, timeout=30)

            if resp.status_code in (200, 201):
                media_id = resp.json().get("media_id_string")
                logger.info("Successfully uploaded X image asset: %s", media_id)
                return media_id
            else:
                logger.warning("X media upload failed (%s): %s", resp.status_code, resp.text)
                return None
        except Exception as e:
            logger.warning("Exception during X media upload: %s", e)
            return None

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
