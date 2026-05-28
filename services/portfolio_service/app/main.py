from __future__ import annotations

import logging
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from services.common.http_utils import read_json, send_json
from services.common.logging_utils import configure_logging
from services.common.metrics import (
    MetricsMixin,
    PORTFOLIO_ALLOCATIONS_TOTAL,
    PORTFOLIO_POSITIONS_ALLOCATED_TOTAL,
    init_service,
    send_metrics,
)
from services.portfolio_service.app.logic.allocator import allocate_portfolio


logger = logging.getLogger(__name__)

_SERVICE = "portfolio-service"


class PortfolioRequestHandler(MetricsMixin, BaseHTTPRequestHandler):
    server_version = "PortfolioService/1.0"
    _service_name = _SERVICE

    def do_OPTIONS(self) -> None:  # noqa: N802
        send_json(self, {"status": "ok"})

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            send_json(self, {"status": "ok", "service": _SERVICE})
            return
        if self.path == "/metrics":
            send_metrics(self, _SERVICE)
            return
        send_json(self, {"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        if self.path.split("?", 1)[0] != "/v1/portfolio/allocate":
            send_json(self, {"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
            return
        try:
            payload = read_json(self)
            if not isinstance(payload, dict):
                raise ValueError("Request body must be a JSON object")
            result = allocate_portfolio(payload)
            positions = result.get("positions", [])
            PORTFOLIO_ALLOCATIONS_TOTAL.labels(status="success").inc()
            if isinstance(positions, list) and positions:
                PORTFOLIO_POSITIONS_ALLOCATED_TOTAL.inc(len(positions))
            send_json(self, result)
        except ValueError as exc:
            logger.warning("Invalid portfolio request: %s", exc)
            PORTFOLIO_ALLOCATIONS_TOTAL.labels(status="error").inc()
            send_json(self, {"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unhandled portfolio-service error: %s", exc)
            PORTFOLIO_ALLOCATIONS_TOTAL.labels(status="error").inc()
            send_json(self, {"error": "Internal server error"}, status=HTTPStatus.INTERNAL_SERVER_ERROR)


def run_server() -> None:
    host = os.environ.get("PORTFOLIO_SERVICE_HOST", os.environ.get("SERVICE_HOST", "127.0.0.1"))
    port = int(os.environ.get("PORTFOLIO_SERVICE_PORT", os.environ.get("SERVICE_PORT", "8003")))
    configure_logging("portfolio-service", console=True)
    init_service(_SERVICE)
    server = ThreadingHTTPServer((host, port), PortfolioRequestHandler)
    logger.info("Portfolio service listening on %s:%s", host, port)
    server.serve_forever()


if __name__ == "__main__":
    run_server()
