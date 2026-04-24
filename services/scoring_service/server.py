from __future__ import annotations

import logging
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from services.common.configuration import DEFAULT_OUTPUT_DIR, load_scoring_model
from services.common.http_utils import read_json, send_json
from services.common.logging_utils import configure_logging
from services.scoring_service.errors import InputValidationError
from services.scoring_service.pipeline import ManualScoringPipeline
from services.scoring_service.workflow_store import register_tickers, save_manual_metrics_payload


logger = logging.getLogger(__name__)


class ScoringRequestHandler(BaseHTTPRequestHandler):
    server_version = "ManualScoringService/1.0"
    output_dir = DEFAULT_OUTPUT_DIR
    write_outputs = True

    def do_OPTIONS(self) -> None:  # noqa: N802
        send_json(self, {"status": "ok"})

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            send_json(
                self,
                {
                    "status": "ok",
                    "service": "scoring-service",
                    "write_outputs": self.write_outputs,
                },
            )
            return

        if self.path == "/v1/scoring-model":
            send_json(self, load_scoring_model())
            return

        send_json(self, {"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        try:
            route = self.path.split("?", 1)[0]
            payload = read_json(self)
            if not isinstance(payload, dict):
                raise InputValidationError("Request body must be a JSON object.", ["Invalid request payload"])

            if route == "/v1/score":
                ticker = str(payload.get("ticker") or payload.get("symbol") or "").upper()
                pipeline = ManualScoringPipeline(ticker or "UNKNOWN")
                bundle = pipeline.run(
                    inline_payload=payload,
                    output_dir=str(self.output_dir),
                    write_outputs=self.write_outputs,
                )
                send_json(self, bundle["standardized_output"], status=HTTPStatus.OK)
                return

            if route == "/v1/stocks/register":
                expected_count = payload.get("count")
                if expected_count not in (None, ""):
                    expected_count = int(expected_count)
                result = register_tickers(
                    raw_tickers=payload.get("tickers") or payload.get("tickers_csv") or [],
                    expected_count=expected_count,
                )
                logger.info(
                    "Registered stock session | requested_tickers=%s | added_tickers=%s | stocks_file=%s",
                    result["requested_tickers"],
                    result["added_tickers"],
                    result["stocks_file"],
                )
                send_json(self, result, status=HTTPStatus.OK)
                return

            if route == "/v1/manual-inputs/save-and-score":
                ticker = str(payload.get("ticker") or payload.get("symbol") or "").upper()
                if not ticker:
                    raise InputValidationError("Ticker is required.", ["Missing required field: ticker"])
                saved_path = save_manual_metrics_payload(payload=payload, ticker=ticker)
                logger.info("Saved manual metrics payload | ticker=%s | path=%s", ticker, saved_path)
                pipeline = ManualScoringPipeline(ticker)
                bundle = pipeline.run(
                    input_path=str(saved_path),
                    output_dir=str(self.output_dir),
                    write_outputs=self.write_outputs,
                )
                send_json(
                    self,
                    {
                        **bundle["standardized_output"],
                        "saved_input_path": str(saved_path),
                        "output_files": bundle.get("output_files", {}),
                    },
                    status=HTTPStatus.OK,
                )
                return

            send_json(self, {"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
        except InputValidationError as exc:
            logger.warning("Validation failed: %s", exc)
            send_json(
                self,
                {
                    "error": str(exc),
                    "details": exc.errors,
                },
                status=HTTPStatus.BAD_REQUEST,
            )
        except ValueError as exc:
            logger.warning("Invalid request: %s", exc)
            send_json(
                self,
                {"error": str(exc)},
                status=HTTPStatus.BAD_REQUEST,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unhandled scoring-service error: %s", exc)
            send_json(
                self,
                {"error": "Internal server error"},
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )


def run_server() -> None:
    host = os.environ.get("SCORING_SERVICE_HOST", "127.0.0.1")
    port = int(os.environ.get("SCORING_SERVICE_PORT", "8000"))
    output_dir = Path(os.environ.get("SCORING_OUTPUT_DIR", str(DEFAULT_OUTPUT_DIR)))
    write_outputs = os.environ.get("SCORING_WRITE_OUTPUTS", "true").lower() == "true"
    configure_logging("scoring-service", level=logging.DEBUG, console=True)

    ScoringRequestHandler.output_dir = output_dir
    ScoringRequestHandler.write_outputs = write_outputs

    server = ThreadingHTTPServer((host, port), ScoringRequestHandler)
    logger.info("Scoring service listening on %s:%s", host, port)
    server.serve_forever()


if __name__ == "__main__":
    run_server()
