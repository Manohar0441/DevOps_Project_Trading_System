from __future__ import annotations

import logging
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from services.common.http_utils import read_json, send_json, send_text
from services.common.logging_utils import configure_logging
from services.common.metrics import (
    MetricsMixin,
    RISK_EVALUATIONS_TOTAL,
    RISK_MACRO_FLAGS_TOTAL,
    RISK_PROFIT_LOCK_SIGNALS_TOTAL,
    init_service,
    send_metrics,
)
from services.risk_service.app.events.publisher import build_risk_event
from services.risk_service.app.logic.macro_monitor import evaluate_macro_flags
from services.risk_service.app.logic.portfolio_heat import evaluate_portfolio_heat
from services.risk_service.app.logic.profit_lock import evaluate_profit_locks
from services.risk_service.app.logic.week_rules import rule_for_holding_days
from services.risk_service.app.sse.stream import format_sse


logger = logging.getLogger(__name__)

_SERVICE = "risk-service"


class RiskRequestHandler(MetricsMixin, BaseHTTPRequestHandler):
    server_version = "RiskService/1.0"
    _service_name = _SERVICE

    def do_OPTIONS(self) -> None:  # noqa: N802
        send_json(self, {"status": "ok"})

    def do_GET(self) -> None:  # noqa: N802
        route = self.path.split("?", 1)[0]
        if route == "/health":
            send_json(self, {"status": "ok", "service": _SERVICE})
            return
        if route == "/metrics":
            send_metrics(self, _SERVICE)
            return
        if route == "/v1/risk/stream":
            send_text(
                self,
                format_sse("risk.heartbeat", {"status": "ok", "service": _SERVICE}),
                content_type="text/event-stream; charset=utf-8",
            )
            return
        send_json(self, {"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        route = self.path.split("?", 1)[0]
        try:
            payload = read_json(self)
            if not isinstance(payload, dict):
                raise ValueError("Request body must be a JSON object")

            if route == "/v1/risk/evaluate":
                heat = evaluate_portfolio_heat(payload)
                positions = payload.get("positions", [])
                lock_threshold = float(payload.get("profit_lock_threshold_pct", 15.0))
                profit_locks = evaluate_profit_locks(
                    positions if isinstance(positions, list) else [], lock_threshold
                )
                macro = evaluate_macro_flags(payload)
                outcome = (
                    "BREACH" if heat["status"] == "BREACH"
                    else "CAUTION" if profit_locks or macro["status"] == "CAUTION"
                    else "PASS"
                )
                result = {
                    "status": outcome,
                    "portfolio_heat": heat,
                    "profit_lock_signals": profit_locks,
                    "macro": macro,
                    "event": build_risk_event("risk.evaluated", {"status": outcome}),
                }
                # Record metrics
                RISK_EVALUATIONS_TOTAL.labels(outcome=outcome).inc()
                if profit_locks:
                    RISK_PROFIT_LOCK_SIGNALS_TOTAL.inc(len(profit_locks))
                if macro.get("status") == "CAUTION":
                    RISK_MACRO_FLAGS_TOTAL.inc()

                send_json(self, result)
                return

            if route == "/v1/risk/week-rule":
                holding_days = int(payload.get("holding_days", 0))
                send_json(self, rule_for_holding_days(holding_days))
                return

            send_json(self, {"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            logger.warning("Invalid risk request: %s", exc)
            send_json(self, {"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unhandled risk-service error: %s", exc)
            send_json(self, {"error": "Internal server error"}, status=HTTPStatus.INTERNAL_SERVER_ERROR)


def run_server() -> None:
    host = os.environ.get("RISK_SERVICE_HOST", os.environ.get("SERVICE_HOST", "127.0.0.1"))
    port = int(os.environ.get("RISK_SERVICE_PORT", os.environ.get("SERVICE_PORT", "8004")))
    configure_logging("risk-service", console=True)
    init_service(_SERVICE)
    server = ThreadingHTTPServer((host, port), RiskRequestHandler)
    logger.info("Risk service listening on %s:%s", host, port)
    server.serve_forever()


if __name__ == "__main__":
    run_server()
