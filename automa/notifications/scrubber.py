"""
Secret & Sensitive Data Scrubber for Automa.
Prevents credentials, API keys, and sensitive tokens from appearing in logs or notifications.
"""

from __future__ import annotations
import re
from typing import Any

# Regex patterns matching common secrets and credentials
SECRET_PATTERNS = [
    # Gemini / Google API keys
    (re.compile(r"AIza[0-9A-Za-z-_]{35}"), "[REDACTED_GEMINI_KEY]"),
    # Generic Bearer tokens
    (re.compile(r"Bearer\s+([a-zA-Z0-9_\-\.]{15,})", re.IGNORECASE), "Bearer [REDACTED_TOKEN]"),
    # Authorization headers
    (re.compile(r"Authorization:\s*([^\s,]+)", re.IGNORECASE), "Authorization: [REDACTED_AUTH]"),
    # Postiz API keys (UUID or hex-like tokens)
    (re.compile(r"(postiz[_\-]?api[_\-]?key\s*[:=]\s*)['\"]?([a-zA-Z0-9_\-]{16,})['\"]?", re.IGNORECASE), r"\1[REDACTED_KEY]"),
    # General secret / token / password assignments
    (re.compile(r"((?:secret|password|token|api_key|access_key|private_key)\s*[:=]\s*)['\"]?([^\s'\"]{8,})['\"]?", re.IGNORECASE), r"\1[REDACTED]"),
    # SSH / Private key blocks
    (re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----[^-]+-----END [A-Z ]+PRIVATE KEY-----", re.DOTALL), "[REDACTED_PRIVATE_KEY]"),
]


def scrub_secrets(text: str) -> str:
    """Replaces any detected API keys, passwords, or tokens with sanitized placeholders."""
    if not isinstance(text, str):
        return text

    scrubbed = text
    for pattern, replacement in SECRET_PATTERNS:
        scrubbed = pattern.sub(replacement, scrubbed)

    return scrubbed


def sanitize_payload(payload: Any) -> Any:
    """Recursively sanitizes dictionary or list payloads."""
    if isinstance(payload, str):
        return scrub_secrets(payload)
    elif isinstance(payload, dict):
        sanitized = {}
        for k, v in payload.items():
            if any(term in k.lower() for term in ["key", "token", "secret", "password", "auth"]):
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = sanitize_payload(v)
        return sanitized
    elif isinstance(payload, list):
        return [sanitize_payload(item) for item in payload]
    return payload
