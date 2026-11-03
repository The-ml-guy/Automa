"""
WSGI Application entry point for Gunicorn / Render production deployment.
Adapts Automa's DashboardHandler to standard WSGI callable.
"""

from __future__ import annotations
import io
import logging
import os
import threading
from urllib.parse import urlparse
from automa.db.schema import init_db
from automa.web.server import DashboardHandler

# Ensure database tables exist on WSGI boot
try:
    init_db()
except Exception as e:
    pass

logger = logging.getLogger("automa.web.wsgi")

_scheduler_instance = None
_scheduler_lock = threading.Lock()


def _ensure_background_scheduler() -> None:
    """Initializes in-process background scheduler for production cloud hosting."""
    global _scheduler_instance
    if os.getenv("ENABLE_SCHEDULER", "true").lower() in ("true", "1", "yes"):
        if _scheduler_instance is None:
            with _scheduler_lock:
                if _scheduler_instance is None:
                    try:
                        from automa.scheduler.runner import SchedulerRunner
                        runner = SchedulerRunner()
                        _scheduler_instance = runner.start_daemon(blocking=False)
                        logger.info("Automa production background scheduler daemon started.")
                    except Exception as err:
                        logger.warning("Could not launch in-process scheduler: %s", err)


# Start background scheduler when WSGI module loads
_ensure_background_scheduler()


class WSGIResponseCollector:
    def __init__(self):
        self.status = 200
        self.headers = []
        self.body = io.BytesIO()

    def send_response(self, status: int, message: str = ""):
        self.status = status

    def send_header(self, keyword: str, value: str):
        self.headers.append((keyword, str(value)))

    def end_headers(self):
        pass


def application(environ, start_response):
    """
    Standard WSGI callable.
    Dispatches HTTP requests into DashboardHandler logic.
    """
    method = environ.get("REQUEST_METHOD", "GET").upper()
    path = environ.get("PATH_INFO", "/")
    query_string = environ.get("QUERY_STRING", "")
    full_path = f"{path}?{query_string}" if query_string else path

    # Read input body with size limit (1MB max)
    content_length = int(environ.get("CONTENT_LENGTH") or 0)
    if content_length > 1024 * 1024:
        start_response("413 Payload Too Large", [("Content-Type", "application/json")])
        return [b'{"error": "Payload exceeds 1MB limit"}']

    rfile = environ.get("wsgi.input")
    body_bytes = rfile.read(content_length) if (rfile and content_length > 0) else b""

    # Prepare mock handler to capture response
    collector = WSGIResponseCollector()
    
    # Extract headers
    req_headers = {}
    for key, value in environ.items():
        if key.startswith("HTTP_"):
            header_name = key[5:].replace("_", "-").title()
            req_headers[header_name] = value
        elif key in ("CONTENT_TYPE", "CONTENT_LENGTH"):
            header_name = key.replace("_", "-").title()
            req_headers[header_name] = value

    client_ip = environ.get("REMOTE_ADDR", "127.0.0.1")
    client_port = int(environ.get("REMOTE_PORT", 0) or 0)

    # Minimal socket/request dummy object
    class DummyRequest:
        def makefile(self, *args, **kwargs):
            return io.BytesIO()

    class HandlerInstance(DashboardHandler):
        def __init__(self):
            self.rfile = io.BytesIO(body_bytes)
            self.wfile = collector.body
            self.headers = req_headers
            self.client_address = (client_ip, client_port)
            self.command = method
            self.path = full_path
            self.request_version = "HTTP/1.1"

        def send_response(self, code, message=None):
            collector.send_response(code, message or "")

        def send_header(self, keyword, value):
            collector.send_header(keyword, value)

        def end_headers(self):
            collector.end_headers()

        def send_error(self, code, message=None, explain=None):
            collector.send_response(code, message or "Error")
            collector.send_header("Content-Type", "application/json")
            err_body = f'{{"error": "{message or "Error"}", "code": {code}}}'.encode("utf-8")
            collector.send_header("Content-Length", str(len(err_body)))
            collector.end_headers()
            collector.body.write(err_body)

    handler = HandlerInstance()

    try:
        if method == "GET":
            handler.do_GET()
        elif method == "POST":
            handler.do_POST()
        elif method == "OPTIONS":
            handler.do_OPTIONS()
        elif method == "HEAD":
            handler.do_GET()
            # Body discarded for HEAD
            collector.body = io.BytesIO()
        else:
            handler.send_error(405, "Method Not Allowed")
    except Exception as exc:
        logger.exception("WSGI exception: %s", exc)
        start_response("500 Internal Server Error", [("Content-Type", "application/json")])
        return [b'{"error": "Internal Server Error"}']

    # Map status code to status string
    status_str = f"{collector.status} OK" if collector.status == 200 else f"{collector.status} Status"
    
    start_response(status_str, collector.headers)
    return [collector.body.getvalue()]

