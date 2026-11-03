"""
Automa Cloudflare Tunnel Manager.
Provides zero-cost, secure HTTPS tunneling for Meta/Instagram Graph API
to ingest generated media cards from localhost without opening firewall ports.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional, Dict, Any

from automa.config import BASE_DIR

logger = logging.getLogger("automa.tunnel")
TUNNEL_INFO_FILE = BASE_DIR / ".tunnel_info.json"


def _is_process_alive(pid: int) -> bool:
    """Checks if a given process ID is active on Windows or POSIX."""
    try:
        import psutil
        return psutil.pid_exists(pid)
    except ImportError:
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False


def get_tunnel_url() -> Optional[str]:
    """
    Returns the currently active public base URL.
    Checks environment variable PUBLIC_MEDIA_BASE_URL first,
    then active tunnel metadata file.
    """
    env_url = os.getenv("PUBLIC_MEDIA_BASE_URL")
    if env_url:
        return env_url.strip().rstrip("/")

    if TUNNEL_INFO_FILE.exists():
        try:
            data = json.loads(TUNNEL_INFO_FILE.read_text(encoding="utf-8"))
            url = data.get("url")
            if url:
                return url.strip().rstrip("/")
        except Exception as e:
            logger.debug("Failed to read tunnel metadata: %s", e)

    return None


def start_tunnel(port: int = 8080, timeout_seconds: int = 25) -> Optional[str]:
    """
    Starts a free Cloudflare Quick Tunnel forwarding to http://127.0.0.1:{port}.
    Returns the assigned HTTPS URL (e.g. https://xxx.trycloudflare.com).
    """
    existing_url = get_tunnel_url()
    if existing_url:
        logger.info("Using existing active tunnel URL: %s", existing_url)
        return existing_url

    npx_path = shutil.which("npx")
    if not npx_path:
        logger.error("Node.js / npx is not found on PATH. Cannot launch Cloudflare Tunnel.")
        return None

    logger.info("Initiating Cloudflare Quick Tunnel to port %d...", port)
    cmd = ["cmd.exe", "/c", "npx", "--yes", "cloudflared", "tunnel", "--url", f"http://127.0.0.1:{port}"]

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        tunnel_url = None
        start_time = time.time()

        while time.time() - start_time < timeout_seconds:
            line = proc.stdout.readline()
            if not line:
                if proc.poll() is not None:
                    logger.error("cloudflared process exited prematurely with code %s", proc.returncode)
                    break
                time.sleep(0.1)
                continue

            clean_line = line.strip()
            match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", clean_line)
            if match:
                tunnel_url = match.group(0).rstrip("/")
                logger.info("Cloudflare Quick Tunnel established at: %s", tunnel_url)
                break

        if tunnel_url:
            # Save metadata
            info: Dict[str, Any] = {
                "url": tunnel_url,
                "pid": proc.pid,
                "created_at": time.time(),
                "port": port,
            }
            TUNNEL_INFO_FILE.write_text(json.dumps(info, indent=2), encoding="utf-8")
            os.environ["PUBLIC_MEDIA_BASE_URL"] = tunnel_url
            return tunnel_url
        else:
            logger.error("Timed out waiting for Cloudflare Tunnel URL.")
            proc.terminate()
            return None

    except Exception as e:
        logger.error("Failed to start Cloudflare Tunnel: %s", e)
        return None


def stop_tunnel() -> bool:
    """Stops the active Cloudflare Quick Tunnel process if running."""
    if not TUNNEL_INFO_FILE.exists():
        return False

    try:
        data = json.loads(TUNNEL_INFO_FILE.read_text(encoding="utf-8"))
        pid = data.get("pid")
        if pid and _is_process_alive(pid):
            try:
                import psutil
                parent = psutil.Process(pid)
                for child in parent.children(recursive=True):
                    child.terminate()
                parent.terminate()
            except ImportError:
                import signal
                os.kill(pid, signal.SIGTERM)
            logger.info("Cloudflare Tunnel (PID %d) terminated.", pid)

        TUNNEL_INFO_FILE.unlink(missing_ok=True)
        if "PUBLIC_MEDIA_BASE_URL" in os.environ:
            del os.environ["PUBLIC_MEDIA_BASE_URL"]
        return True
    except Exception as e:
        logger.error("Failed to terminate tunnel: %s", e)
        TUNNEL_INFO_FILE.unlink(missing_ok=True)
        return False
