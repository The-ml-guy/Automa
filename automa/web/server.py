"""
Localhost Monitoring Dashboard Server for Automa (Phase 10 & 11).
Binds strictly to 127.0.0.1 and provides REST endpoints and static UI.
"""

from __future__ import annotations
import json
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from typing import Dict, Any

from automa.config import get_settings, BASE_DIR
from automa.db.repository import PostRepository
from automa.engine.generator import ContentEngine
from automa.scheduler.runner import SchedulerRunner

logger = logging.getLogger("automa.web.server")
STATIC_DIR = Path(__file__).resolve().parent / "static"


class DashboardHandler(BaseHTTPRequestHandler):
    repo = PostRepository()
    engine = ContentEngine(repo=repo)
    runner = SchedulerRunner(repo=repo, engine=engine)

    def _send_json(self, data: Any, status: int = 200) -> None:
        payload = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1:8080")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(payload)

    def _serve_file(self, file_path: Path, content_type: str) -> None:
        if not file_path.exists():
            self.send_error(404, "File Not Found")
            return
        with open(file_path, "rb") as f:
            content = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1:8080")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        if path in ("", "/", "/index.html"):
            self._serve_file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
        elif path == "/styles.css":
            self._serve_file(STATIC_DIR / "styles.css", "text/css; charset=utf-8")
        elif path == "/app.js":
            self._serve_file(STATIC_DIR / "app.js", "application/javascript; charset=utf-8")
        elif path == "/api/status":
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
        else:
            self.send_error(404, "Endpoint Not Found")

    def do_POST(self) -> None:
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        content_length = int(self.headers.get("Content-Length", 0))
        post_body = self.rfile.read(content_length) if content_length > 0 else b"{}"
        try:
            body = json.loads(post_body.decode("utf-8")) if post_body else {}
        except Exception:
            body = {}

        if path == "/api/generate":
            res = self.engine.run_scheduled_generation()
            self._send_json(res)
        elif path == "/api/publish":
            res = self.runner.process_due_posts()
            self._send_json(res)
        elif path == "/api/review/decision":
            post_id = body.get("post_id")
            action = body.get("action") # "approve" or "reject"
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
        else:
            self.send_error(404, "Endpoint Not Found")


def run_dashboard_server(host: str = "127.0.0.1", port: int = 8080) -> None:
    server_address = (host, port)
    httpd = HTTPServer(server_address, DashboardHandler)
    logger.info("Automa Local Dashboard live at http://%s:%d (localhost only)", host, port)
    try:
        httpd.serve_forever()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Stopping dashboard server.")
        httpd.server_close()
