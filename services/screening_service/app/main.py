from __future__ import annotations

import logging
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from services.common.http_utils import read_json, send_json
from services.common.logging_utils import configure_logging
from services.common.metrics import (
    MetricsMixin,
    SCREENING_CANDIDATES_EVALUATED_TOTAL,
    SCREENING_REQUESTS_TOTAL,
    init_service,
    send_metrics,
)
from services.screening_service.app.events.publisher import build_screening_event
from services.screening_service.app.logic.screener import screen_candidates
from services.screening_service.app.logic.sector_ranker import rank_by_sector


logger = logging.getLogger(__name__)

_SERVICE = "screening-service"


class ScreeningRequestHandler(MetricsMixin, BaseHTTPRequestHandler):
    server_version = "ScreeningService/1.0"
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
        route = self.path.split("?", 1)[0]
        try:
            payload = read_json(self)
            if not isinstance(payload, dict):
                raise ValueError("Request body must be a JSON object")

            if route == "/v1/screen":
                candidates = payload.get("candidates", [])
                result = screen_candidates(payload)
                result["event"] = build_screening_event("screening.completed", result["summary"])
                SCREENING_REQUESTS_TOTAL.labels(status="success").inc()
                if isinstance(candidates, list):
                    SCREENING_CANDIDATES_EVALUATED_TOTAL.inc(len(candidates))
                send_json(self, result)
                return

            if route == "/v1/sectors/rank":
                candidates = payload.get("candidates", [])
                if not isinstance(candidates, list):
                    raise ValueError("candidates must be a list")
                send_json(self, {"sectors": rank_by_sector(candidates)})
                return

            send_json(self, {"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            logger.warning("Invalid screening request: %s", exc)
            SCREENING_REQUESTS_TOTAL.labels(status="error").inc()
            send_json(self, {"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unhandled screening-service error: %s", exc)
            SCREENING_REQUESTS_TOTAL.labels(status="error").inc()
            send_json(self, {"error": "Internal server error"}, status=HTTPStatus.INTERNAL_SERVER_ERROR)


def run_server() -> None:
    host = os.environ.get("SCREENING_SERVICE_HOST", os.environ.get("SERVICE_HOST", "127.0.0.1"))
    port = int(os.environ.get("SCREENING_SERVICE_PORT", os.environ.get("SERVICE_PORT", "8005")))
    configure_logging("screening-service", console=True)
    init_service(_SERVICE)
    server = ThreadingHTTPServer((host, port), ScreeningRequestHandler)
    logger.info("Screening service listening on %s:%s", host, port)
    server.serve_forever()


if __name__ == "__main__":
    run_server()
