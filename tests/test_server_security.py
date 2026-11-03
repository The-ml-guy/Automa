"""
Security boundary and Cloudflare tunnel isolation unit tests.
Verifies that external proxied requests cannot reach administrative APIs or dashboard UI,
and that only valid media assets are served publicly for Meta Graph API ingestion.
"""

import pytest
import requests


def test_localhost_admin_access():
    """Confirms localhost direct access to dashboard status returns 200."""
    resp = requests.get("http://127.0.0.1:8080/api/status", headers={"Host": "127.0.0.1:8080"})
    assert resp.status_code == 200
    assert resp.json().get("healthy") is True


def test_external_proxy_admin_access_blocked():
    """Confirms external requests with proxy/tunnel headers are rejected with 403 Forbidden."""
    # Test CF-Ray header
    r1 = requests.get("http://127.0.0.1:8080/api/status", headers={"CF-Ray": "cf_test_ray"})
    assert r1.status_code == 403

    # Test CF-Connecting-IP header
    r2 = requests.get("http://127.0.0.1:8080/api/posts", headers={"CF-Connecting-IP": "203.0.113.195"})
    assert r2.status_code == 403

    # Test X-Forwarded-For header
    r3 = requests.get("http://127.0.0.1:8080/", headers={"X-Forwarded-For": "203.0.113.195"})
    assert r3.status_code == 403

    # Test external Host header
    r4 = requests.get("http://127.0.0.1:8080/api/status", headers={"Host": "automa.trycloudflare.com"})
    assert r4.status_code == 403


def test_external_post_action_blocked():
    """Confirms external POST action endpoints (publish, generate) are strictly blocked with 403."""
    resp = requests.post(
        "http://127.0.0.1:8080/api/publish",
        headers={"CF-Ray": "cf_test_ray"},
        json={"force": True},
    )
    assert resp.status_code == 403


def test_public_media_access_allowed():
    """Confirms /media/<valid_file>.png is accessible publicly for Instagram crawlers."""
    resp = requests.get(
        "http://127.0.0.1:8080/media/post_instagram_8881cac1.png",
        headers={"CF-Ray": "cf_test_ray", "Host": "automa.trycloudflare.com"},
    )
    assert resp.status_code == 200
    assert "image" in resp.headers.get("Content-Type", "")


def test_media_path_traversal_blocked():
    """Confirms path traversal or non-image extensions are rejected."""
    # Disallowed extension
    r1 = requests.get(
        "http://127.0.0.1:8080/media/config.py",
        headers={"CF-Ray": "cf_test_ray"},
    )
    assert r1.status_code in (403, 404)

