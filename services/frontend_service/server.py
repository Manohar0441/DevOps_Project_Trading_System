from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from services.common.http_utils import send_json
from services.common.logging_utils import configure_logging
from services.common.metrics import MetricsMixin, init_service, send_metrics


logger = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).resolve().parent / "static"

# Internal K8s DNS name for the scoring service — override via env var if needed
SCORING_SERVICE_URL = os.environ.get("SCORING_SERVICE_URL", "http://scoring-service:8000")

_SERVICE = "frontend-service"


class FrontendRequestHandler(MetricsMixin, SimpleHTTPRequestHandler):
    _service_name = _SERVICE
    def do_GET(self) -> None:  # noqa: N802
        request_path = self.path.split("?", 1)[0]
        if request_path == "/health":
            send_json(self, {"status": "ok", "service": "frontend-service"})
            return

        if request_path == "/metrics":
            send_metrics(self, "frontend-service")
            return

        # Proxy all /v1/* API calls to the scoring service
        if request_path.startswith("/v1/"):
            self._proxy(request_path)
            return

        asset_path = STATIC_DIR / request_path.lstrip("/")
        if request_path == "/" or (not asset_path.exists() and "." not in Path(request_path).name):
            self.path = "/index.html"

        return super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        request_path = self.path.split("?", 1)[0]
        if request_path.startswith("/v1/"):
            self._proxy(request_path)
            return
        self.send_error(404, "Not Found")

    def do_OPTIONS(self) -> None:  # noqa: N802
        request_path = self.path.split("?", 1)[0]
        if request_path.startswith("/v1/"):
            self._proxy(request_path)
            return
        send_json(self, {"status": "ok"})

    def _proxy(self, path: str) -> None:
        """Forward the request to the scoring service and relay the response."""
        target = f"{SCORING_SERVICE_URL}{path}"
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else None
        content_type = self.headers.get("Content-Type", "application/json")

        try:
            req = urllib.request.Request(
                target,
                data=body,
                method=self.command,
                headers={"Content-Type": content_type},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_body = resp.read()
                self.send_response(resp.status)
                self.send_header("Content-Type", resp.headers.get("Content-Type", "application/json"))
                self.send_header("Content-Length", str(len(resp_body)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(resp_body)
        except urllib.error.HTTPError as exc:
            resp_body = exc.read()
            self.send_response(exc.code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp_body)))
            self.end_headers()
            self.wfile.write(resp_body)
        except Exception as exc:  # noqa: BLE001
            logger.error("Proxy error → %s: %s", target, exc)
            error_body = json.dumps({"error": "scoring service unavailable"}).encode()
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(error_body)))
            self.end_headers()
            self.wfile.write(error_body)


def run_server() -> None:
    host = os.environ.get("FRONTEND_SERVICE_HOST", "127.0.0.1")
    port = int(os.environ.get("FRONTEND_SERVICE_PORT", "8080"))
    configure_logging("frontend-service", console=True)
    init_service(_SERVICE)

    class StaticFrontendHandler(FrontendRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    server = ThreadingHTTPServer((host, port), StaticFrontendHandler)
    logger.info(
        "Frontend service listening on %s:%s (proxy → %s)",
        host, port, SCORING_SERVICE_URL,
    )
    server.serve_forever()


if __name__ == "__main__":
    run_server()
