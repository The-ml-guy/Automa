"""
Production & Localhost Dashboard Server for Automa.
Supports standard HTTP, Gunicorn WSGI, production security headers,
Render deployment, and local development.
"""

from __future__ import annotations
import json
import logging
import mimetypes
import os
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from typing import Dict, Any

from automa.config import get_settings, BASE_DIR, CONTENT_DIR
from automa.db.schema import init_db
from automa.db.repository import PostRepository
from automa.engine.generator import ContentEngine
from automa.scheduler.runner import SchedulerRunner

# Ensure database tables exist
try:
    init_db()
except Exception:
    pass

logger = logging.getLogger("automa.web.server")
STATIC_DIR = Path(__file__).resolve().parent / "static"


class DashboardHandler(BaseHTTPRequestHandler):
    repo = PostRepository()
    engine = ContentEngine(repo=repo)
    runner = SchedulerRunner(repo=repo, engine=engine)

    def _apply_security_headers(self) -> None:
        """Inject production security headers on all responses."""
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https: blob:; "
            "script-src 'self' 'unsafe-inline'; "
            "connect-src 'self' https:;"
        )

    def _apply_cors_headers(self) -> None:
        settings = get_settings()
        origin = self.headers.get("Origin") or ""
        allowed = settings.allowed_origins.split(",") if settings.allowed_origins else []
        
        # In production with allowed_origins configured, check whitelist; else allow same-origin/localhost
        if settings.environment == "production" and allowed:
            if origin in [a.strip() for a in allowed]:
                self.send_header("Access-Control-Allow-Origin", origin)
        elif settings.environment == "production":
            # Default to requesting origin in production if no explicit whitelist
            self.send_header("Access-Control-Allow-Origin", origin if origin else "*")
        else:
            self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1:8080")

        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def _send_json(self, data: Any, status: int = 200) -> None:
        payload = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self._apply_security_headers()
        self._apply_cors_headers()
        self.end_headers()
        self.wfile.write(payload)

    def _serve_file(self, file_path: Path, content_type: str, is_static_asset: bool = False) -> None:
        if not file_path.exists():
            self.send_error(404, "File Not Found")
            return
        try:
            with open(file_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self._apply_security_headers()
            self._apply_cors_headers()

            if is_static_asset:
                # Cache static assets (CSS, JS, Fonts, Images) for 1 hour
                self.send_header("Cache-Control", "public, max-age=3600")
            else:
                # HTML pages should revalidate
                self.send_header("Cache-Control", "no-cache, must-revalidate")

            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            logger.warning("Error serving file %s: %s", file_path, e)
            self.send_error(500, "Error reading file")

    def do_OPTIONS(self) -> None:
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        if not path.startswith("/media/") and path != "/api/health" and self._is_unauthorized_external():
            self.send_error(403, "Forbidden: Administrative access restricted.")
            return
        self.send_response(204)
        self._apply_cors_headers()
        self._apply_security_headers()
        self.end_headers()

    def do_HEAD(self) -> None:
        """Standard HEAD implementation matching GET headers without body."""
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        if path == "/api/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._apply_security_headers()
            self.end_headers()
            return
        # Delegate to do_GET but suppress writing body
        self.do_GET()

    def _is_unauthorized_external(self) -> bool:
        """
        In development with a Cloudflare tunnel running, protect admin endpoints.
        In production (Render/Railway), external requests to the app are normal.
        """
        settings = get_settings()
        if settings.environment == "production":
            return False

        # In development: check if request arrived via reverse tunnel / proxy
        proxy_headers = ("cf-ray", "cf-connecting-ip", "x-forwarded-for", "x-real-ip", "x-forwarded-proto")
        for h in proxy_headers:
            if self.headers.get(h):
                return True

        client_ip = self.client_address[0]
        if client_ip not in ("127.0.0.1", "::1", "localhost"):
            return True

        host = self.headers.get("Host", "").split(":")[0].lower()
        if host not in ("127.0.0.1", "localhost", "testserver"):
            return True

        return False

    def do_GET(self) -> None:
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        # 1. Public Health Check for Render & uptime monitors
        if path in ("/api/health", "/health", "/healthz"):
            self._send_json({"status": "healthy", "service": "automa", "environment": get_settings().environment})
            return

        # 2. Public Media Endpoint (for Instagram/Meta crawlers and UI previews)
        if path.startswith("/media/"):
            filename = Path(path.replace("/media/", "")).name
            suffix = Path(filename).suffix.lower()
            if suffix not in (".png", ".jpg", ".jpeg", ".webp", ".svg"):
                self.send_error(403, "Forbidden file format")
                return

            media_path = CONTENT_DIR / "media" / filename
            if not media_path.exists():
                media_path = BASE_DIR / "content" / "media" / filename
            if media_path.exists() and media_path.is_file():
                mime = mimetypes.guess_type(str(media_path))[0] or "application/octet-stream"
                self._serve_file(media_path, mime, is_static_asset=True)
            else:
                self.send_error(404, "Media not found")
            return

        # 3. Security Boundary in Development mode
        if self._is_unauthorized_external():
            self.send_error(403, "Forbidden: Administrative access restricted to localhost.")
            return

        # 4. Static UI Routing
        if path in ("", "/", "/index.html"):
            self._serve_file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
            return
        elif path in ("/share", "/share.html"):
            self._serve_file(STATIC_DIR / "share.html", "text/html; charset=utf-8")
            return

        # Generic static asset handler under static/
        clean_path = path.lstrip("/")
        potential_static = (STATIC_DIR / clean_path).resolve()
        if str(potential_static).startswith(str(STATIC_DIR)) and potential_static.exists() and potential_static.is_file():
            mime, _ = mimetypes.guess_type(str(potential_static))
            self._serve_file(potential_static, mime or "text/plain; charset=utf-8", is_static_asset=True)
            return

        # 5. REST APIs
        try:
            if path == "/api/status":
                settings = get_settings()
                counts = self.repo.get_queue_counts()
                audit = self.repo.get_recent_audit_logs(limit=10)
                self._send_json({
                    "healthy": True,
                    "environment": settings.environment,
                    "dry_run": settings.dry_run,
                    "publisher_type": settings.publisher_type,
                    "gemini_model": settings.gemini_model,
                    "timezone": settings.timezone,
                    "queue_counts": counts,
                    "recent_audit": audit,
                })
            elif path == "/api/posts":
                query_params = parse_qs(parsed_url.query)
                platform = query_params.get("platform", [None])[0]
                posts = self.repo.get_recent_posts(platform=platform, limit=100)
                self._send_json([p.model_dump() for p in posts])
            elif path == "/api/reviews":
                posts = self.repo.get_posts_requiring_review()
                self._send_json([p.model_dump() for p in posts])
            elif path == "/api/audit":
                audit = self.repo.get_recent_audit_logs(limit=50)
                self._send_json(audit)
            elif path == "/api/intelligence/stats":
                stats = self.repo.get_intelligence_stats()
                self._send_json(stats)
            elif path == "/api/intelligence/discovered":
                query_params = parse_qs(parsed_url.query)
                source_type = query_params.get("source", [None])[0]
                items = self.repo.get_discovered_items(source_type=source_type, limit=100)
                self._send_json([item.model_dump() for item in items])
            elif path == "/api/intelligence/rankings":
                rankings = self.repo.get_top_ranked_topics(limit=50)
                self._send_json(rankings)
            else:
                self.send_error(404, "Endpoint Not Found")
        except Exception as e:
            logger.exception("Error handling GET %s: %s", path, e)
            self._send_json({"error": f"API error on {path}: {str(e)}"}, status=500)

    def do_POST(self) -> None:
        if self._is_unauthorized_external():
            self.send_error(403, "Forbidden: Administrative access restricted.")
            return

        parsed_url = urlparse(self.path)
        path = parsed_url.path

        # Protect against oversized POST payloads (1MB maximum)
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > 1024 * 1024:
            self._send_json({"error": "Payload exceeds 1MB limit"}, status=413)
            return

        post_body = self.rfile.read(content_length) if content_length > 0 else b"{}"
        try:
            body = json.loads(post_body.decode("utf-8")) if post_body else {}
        except Exception:
            body = {}

        try:
            if path == "/api/generate":
                force = body.get("force", True) if isinstance(body, dict) else True
                res = self.engine.run_scheduled_generation(force=force)
                self._send_json(res)
            elif path == "/api/publish":
                force = body.get("force", True) if isinstance(body, dict) else True
                res = self.runner.process_due_posts(force=force)
                self._send_json(res)
            elif path == "/api/posts/publish":
                post_id = body.get("post_id") if isinstance(body, dict) else None
                if not post_id:
                    self._send_json({"error": "Missing post_id"}, status=400)
                    return
                res = self.runner.publish_post_by_id(post_id)
                self._send_json(res)
            elif path == "/api/intelligence/discover":
                from automa.agents.discovery import ResearchDiscoveryAgent
                agent = ResearchDiscoveryAgent(repo=self.repo)
                limit = body.get("limit", 5)
                res = agent.execute({"limit_per_source": limit})
                self._send_json(res)
            elif path == "/api/intelligence/pipeline":
                from automa.agents.orchestrator import ContentIntelligencePipeline
                orchestrator = ContentIntelligencePipeline(repo=self.repo)
                res = orchestrator.run_full_pipeline(
                    discovery_limit_per_source=body.get("discovery_limit", 5),
                    target_platforms=body.get("platforms", ["linkedin", "x"]),
                )
                self._send_json(res)
            elif path == "/api/review/decision":
                post_id = body.get("post_id")
                action = body.get("action")  # "approve" or "reject"
                post = self.repo.get_post_by_id(post_id)
                if not post:
                    self._send_json({"error": "Post not found"}, status=404)
                    return

                if action == "approve":
                    post.status = "SCHEDULED"
                    post.requires_manual_review = False
                    post.scheduled_at = (post.scheduled_at or post.created_at)
                    self.repo.save_post(post)
                    self.repo.log_audit_event("MANUAL_APPROVAL", post.id, "Post approved by human reviewer.")
                    self._send_json({"success": True, "status": "SCHEDULED"})
                else:
                    post.status = "REJECTED"
                    post.requires_manual_review = False
                    self.repo.save_post(post)
                    self.repo.log_audit_event("MANUAL_REJECTION", post.id, "Post rejected by human reviewer.")
                    self._send_json({"success": True, "status": "REJECTED"})
            elif path == "/api/posts/generate-image":
                post_id = body.get("post_id") if isinstance(body, dict) else None
                if not post_id:
                    self._send_json({"error": "Missing post_id"}, status=400)
                    return
                post = self.repo.get_post_by_id(post_id)
                if not post:
                    self._send_json({"error": "Post not found"}, status=404)
                    return
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
                        platform=post.platform,
                        post_id=post.id,
                    )
                    card_path = renderer.render(card_brief)
                    post.media_urls = [str(card_path)]
                    post.media_prompt = f"Editorial Card [{card_brief.template}]: {post.topic}"
                    self.repo.save_post(post)
                    filename = Path(str(card_path)).name
                    self._send_json({"success": True, "image_url": f"/media/{filename}", "path": str(card_path)})
                except Exception as e:
                    self._send_json({"error": f"Image generation failed: {str(e)}"}, status=500)
            else:
                self.send_error(404, "Endpoint Not Found")
        except Exception as e:
            logger.exception("Error handling POST %s: %s", path, e)
            self._send_json({"error": f"Internal error handling {path}: {str(e)}"}, status=500)


def run_dashboard_server(host: str | None = None, port: int | None = None) -> None:
    settings = get_settings()
    actual_host = host or settings.web_host
    actual_port = port or settings.web_port
    server_address = (actual_host, actual_port)
    httpd = ThreadingHTTPServer(server_address, DashboardHandler)
    logger.info("Automa Dashboard live at http://%s:%d (env: %s)", actual_host, actual_port, settings.environment)
    try:
        httpd.serve_forever()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Stopping dashboard server.")
        httpd.server_close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    run_dashboard_server()
