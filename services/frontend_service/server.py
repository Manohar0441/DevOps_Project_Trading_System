from __future__ import annotations

import logging
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from services.common.http_utils import send_json
from services.common.logging_utils import configure_logging


logger = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).resolve().parent / "static"


class FrontendRequestHandler(SimpleHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        request_path = self.path.split("?", 1)[0]
        if request_path == "/health":
            send_json(self, {"status": "ok", "service": "frontend-service"})
            return

        asset_path = STATIC_DIR / request_path.lstrip("/")
        if request_path == "/" or (not asset_path.exists() and "." not in Path(request_path).name):
            self.path = "/index.html"

        return super().do_GET()


def run_server() -> None:
    host = os.environ.get("FRONTEND_SERVICE_HOST", "127.0.0.1")
    port = int(os.environ.get("FRONTEND_SERVICE_PORT", "8080"))
    configure_logging("frontend-service", console=True)

    class StaticFrontendHandler(FrontendRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    server = ThreadingHTTPServer((host, port), StaticFrontendHandler)
    logger.info("Frontend service listening on %s:%s", host, port)
    server.serve_forever()


if __name__ == "__main__":
    run_server()
