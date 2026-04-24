from __future__ import annotations

import logging
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from services.batch_service.runner import BatchScoringService
from services.common.http_utils import read_json, send_json
from services.common.logging_utils import configure_logging


logger = logging.getLogger(__name__)


class BatchRequestHandler(BaseHTTPRequestHandler):
    server_version = "BatchScoringService/1.0"
    max_workers = 10
    output_dir = "outputs"
    write_outputs = True

    def do_OPTIONS(self) -> None:  # noqa: N802
        send_json(self, {"status": "ok"})

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            send_json(
                self,
                {
                    "status": "ok",
                    "service": "batch-service",
                    "max_workers": self.max_workers,
                },
            )
            return

        send_json(self, {"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/batch-score":
            send_json(self, {"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
            return

        try:
            payload = read_json(self)
            jobs = payload.get("stocks", [])
            if not isinstance(jobs, list):
                raise ValueError("stocks must be a JSON array")
            service = BatchScoringService(max_workers=self.max_workers)
            result = service.run_jobs(
                jobs=jobs,
                output_dir=self.output_dir,
                write_outputs=self.write_outputs,
            )
            send_json(self, result)
        except ValueError as exc:
            logger.warning("Invalid batch request: %s", exc)
            send_json(
                self,
                {"error": str(exc)},
                status=HTTPStatus.BAD_REQUEST,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unhandled batch-service error: %s", exc)
            send_json(
                self,
                {"error": "Internal server error"},
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )


def run_server() -> None:
    host = os.environ.get("BATCH_SERVICE_HOST", "127.0.0.1")
    port = int(os.environ.get("BATCH_SERVICE_PORT", "8001"))
    max_workers = int(os.environ.get("BATCH_MAX_WORKERS", "10"))
    output_dir = os.environ.get("BATCH_OUTPUT_DIR", "outputs")
    write_outputs = os.environ.get("BATCH_WRITE_OUTPUTS", "true").lower() == "true"
    configure_logging("batch-service", level=logging.DEBUG, console=True)

    BatchRequestHandler.max_workers = max_workers
    BatchRequestHandler.output_dir = output_dir
    BatchRequestHandler.write_outputs = write_outputs

    server = ThreadingHTTPServer((host, port), BatchRequestHandler)
    logger.info("Batch service listening on %s:%s", host, port)
    server.serve_forever()


if __name__ == "__main__":
    run_server()
