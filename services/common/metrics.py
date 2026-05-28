"""
Production-grade Prometheus metrics for all trading-devops services.

All HTTP metrics use shared names with a ``service`` label so Grafana can
aggregate across the fleet or drill into a single service.

Business metrics (scoring, batch, risk, etc.) are defined here once and
imported by the relevant service.  Services that do not use a metric simply
never call .inc() / .observe() on it — Prometheus still emits the metric with
value 0, which is correct behaviour.
"""
from __future__ import annotations

import time as _time
from http.server import BaseHTTPRequestHandler
from typing import Any

_PROMETHEUS_AVAILABLE = False

try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
    )
    _PROMETHEUS_AVAILABLE = True

    # ── Service availability ───────────────────────────────────────────────────
    SERVICE_UP = Gauge(
        "service_up",
        "1 if the service is running, 0 if not",
        ["service"],
    )

    # ── HTTP traffic (shared across all services) ─────────────────────────────
    HTTP_REQUESTS_TOTAL = Counter(
        "http_requests_total",
        "Total HTTP requests handled",
        ["service", "method", "endpoint", "status_code"],
    )
    HTTP_REQUEST_DURATION_SECONDS = Histogram(
        "http_request_duration_seconds",
        "HTTP request latency in seconds",
        ["service", "method", "endpoint"],
        buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    )
    HTTP_REQUESTS_IN_FLIGHT = Gauge(
        "http_requests_in_flight",
        "Current number of in-flight HTTP requests",
        ["service"],
    )

    # ── Scoring service metrics ───────────────────────────────────────────────
    SCORING_REQUESTS_TOTAL = Counter(
        "scoring_requests_total",
        "Total individual stock scoring requests",
        ["outcome"],           # pass / fail / error
    )
    SCORING_SCORE_VALUE = Histogram(
        "scoring_score_value",
        "Distribution of computed stock scores (0 – 100)",
        buckets=[0, 10, 20, 30, 40, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100],
    )
    SCORING_PIPELINE_DURATION_SECONDS = Histogram(
        "scoring_pipeline_duration_seconds",
        "Wall-clock time to score one ticker end-to-end",
        buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5],
    )
    STOCKS_REGISTERED_TOTAL = Counter(
        "stocks_registered_total",
        "Total tickers registered across all sessions",
    )

    # ── Batch service metrics ─────────────────────────────────────────────────
    BATCH_JOBS_TOTAL = Counter(
        "batch_jobs_total",
        "Total batch scoring jobs submitted",
        ["status"],            # success / partial / error
    )
    BATCH_STOCKS_PROCESSED_TOTAL = Counter(
        "batch_stocks_processed_total",
        "Individual stock tickers processed inside batch jobs",
        ["status"],            # success / error
    )
    BATCH_JOB_DURATION_SECONDS = Histogram(
        "batch_job_duration_seconds",
        "Wall-clock time to complete a full batch job",
        buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0],
    )

    # ── Screening service metrics ─────────────────────────────────────────────
    SCREENING_REQUESTS_TOTAL = Counter(
        "screening_requests_total",
        "Total screening requests processed",
        ["status"],
    )
    SCREENING_CANDIDATES_EVALUATED_TOTAL = Counter(
        "screening_candidates_evaluated_total",
        "Number of candidate stocks evaluated by the screener",
    )

    # ── Risk service metrics ──────────────────────────────────────────────────
    RISK_EVALUATIONS_TOTAL = Counter(
        "risk_evaluations_total",
        "Portfolio risk evaluations completed",
        ["outcome"],           # PASS / CAUTION / BREACH
    )
    RISK_PROFIT_LOCK_SIGNALS_TOTAL = Counter(
        "risk_profit_lock_signals_total",
        "Number of profit-lock exit signals triggered",
    )
    RISK_MACRO_FLAGS_TOTAL = Counter(
        "risk_macro_flags_total",
        "Number of macro-environment caution flags raised",
    )

    # ── Portfolio service metrics ─────────────────────────────────────────────
    PORTFOLIO_ALLOCATIONS_TOTAL = Counter(
        "portfolio_allocations_total",
        "Total portfolio allocation requests",
        ["status"],
    )
    PORTFOLIO_POSITIONS_ALLOCATED_TOTAL = Counter(
        "portfolio_positions_allocated_total",
        "Total individual stock positions allocated across all portfolios",
    )

    # ── Notification & SQS metrics ────────────────────────────────────────────
    NOTIFICATIONS_DISPATCHED_TOTAL = Counter(
        "notifications_dispatched_total",
        "Notifications dispatched by channel",
        ["channel", "status"],   # channel: email/sms, status: success/error
    )
    SQS_MESSAGES_CONSUMED_TOTAL = Counter(
        "sqs_messages_consumed_total",
        "SQS messages successfully consumed and processed",
        ["queue"],
    )
    SQS_MESSAGES_FAILED_TOTAL = Counter(
        "sqs_messages_failed_total",
        "SQS messages that failed to process (will be re-queued / sent to DLQ)",
        ["queue"],
    )

except ImportError:
    _PROMETHEUS_AVAILABLE = False
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"

    class _Null:
        """No-op stub so service code doesn't crash when prometheus_client is absent."""
        def labels(self, **_kw: Any) -> "_Null":
            return self
        def inc(self, _n: float = 1) -> None: ...
        def dec(self, _n: float = 1) -> None: ...
        def set(self, _v: float) -> None: ...
        def observe(self, _v: float) -> None: ...

    _n = _Null()
    (SERVICE_UP, HTTP_REQUESTS_TOTAL, HTTP_REQUEST_DURATION_SECONDS,
     HTTP_REQUESTS_IN_FLIGHT, SCORING_REQUESTS_TOTAL, SCORING_SCORE_VALUE,
     SCORING_PIPELINE_DURATION_SECONDS, STOCKS_REGISTERED_TOTAL,
     BATCH_JOBS_TOTAL, BATCH_STOCKS_PROCESSED_TOTAL, BATCH_JOB_DURATION_SECONDS,
     SCREENING_REQUESTS_TOTAL, SCREENING_CANDIDATES_EVALUATED_TOTAL,
     RISK_EVALUATIONS_TOTAL, RISK_PROFIT_LOCK_SIGNALS_TOTAL,
     RISK_MACRO_FLAGS_TOTAL, PORTFOLIO_ALLOCATIONS_TOTAL,
     PORTFOLIO_POSITIONS_ALLOCATED_TOTAL, NOTIFICATIONS_DISPATCHED_TOTAL,
     SQS_MESSAGES_CONSUMED_TOTAL, SQS_MESSAGES_FAILED_TOTAL) = (_n,) * 21

# ── Helpers ────────────────────────────────────────────────────────────────────

_start_time = _time.time()
_initialized_services: set[str] = set()

_KNOWN_ENDPOINTS: frozenset[str] = frozenset({
    "/health", "/metrics",
    "/v1/scoring-model", "/v1/score",
    "/v1/stocks/register", "/v1/manual-inputs/save-and-score",
    "/v1/batch-score",
    "/v1/screen", "/v1/sectors/rank",
    "/v1/portfolio/allocate",
    "/v1/risk/evaluate", "/v1/risk/week-rule", "/v1/risk/stream",
    "/v1/notifications/send", "/v1/events/consume",
})


def _normalise(path: str) -> str:
    """Collapse unknown/dynamic segments to '/other' to prevent cardinality explosion."""
    p = path.split("?")[0].rstrip("/") or "/"
    return p if p in _KNOWN_ENDPOINTS else "/other"


def init_service(service_name: str) -> None:
    """Mark this service as up. Call once from ``run_server()``."""
    if service_name in _initialized_services:
        return
    _initialized_services.add(service_name)
    if _PROMETHEUS_AVAILABLE:
        SERVICE_UP.labels(service=service_name).set(1)


def record_request(
    service: str,
    method: str,
    path: str,
    status: int,
    duration_secs: float = 0.0,
) -> None:
    """Record one HTTP request. Call at the end of each handler method."""
    if not _PROMETHEUS_AVAILABLE:
        return
    endpoint = _normalise(path)
    HTTP_REQUESTS_TOTAL.labels(
        service=service,
        method=method,
        endpoint=endpoint,
        status_code=str(status),
    ).inc()
    if duration_secs > 0.0:
        HTTP_REQUEST_DURATION_SECONDS.labels(
            service=service, method=method, endpoint=endpoint
        ).observe(duration_secs)


def generate_metrics_text(service_name: str) -> tuple[str, str]:
    """Return ``(body, content_type)`` in Prometheus text exposition format."""
    init_service(service_name)
    if _PROMETHEUS_AVAILABLE:
        return generate_latest().decode("utf-8"), CONTENT_TYPE_LATEST
    # Minimal text-format fallback (valid Prometheus syntax)
    n = service_name.replace("-", "_")
    body = (
        f"# HELP {n}_up Service availability\n"
        f"# TYPE {n}_up gauge\n"
        f"{n}_up 1\n"
        f"# HELP process_start_time_seconds Unix timestamp of process start\n"
        f"# TYPE process_start_time_seconds gauge\n"
        f"process_start_time_seconds {_start_time:.3f}\n"
    )
    return body, "text/plain; version=0.0.4; charset=utf-8"


def send_metrics(handler: BaseHTTPRequestHandler, service_name: str) -> None:
    """Write a complete Prometheus ``/metrics`` response."""
    body, content_type = generate_metrics_text(service_name)
    payload = body.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


# ── MetricsMixin ───────────────────────────────────────────────────────────────

class MetricsMixin:
    """
    Drop-in mixin for any ``BaseHTTPRequestHandler`` subclass.

    Automatically records:
    - ``http_requests_total`` (method / endpoint / status_code)
    - ``http_request_duration_seconds`` (latency histogram)
    - ``http_requests_in_flight`` (live gauge)

    Usage::

        class MyHandler(MetricsMixin, BaseHTTPRequestHandler):
            _service_name = "my-service"
            ...
    """
    _service_name: str = "unknown"

    # ── intercept send_response to capture status code ─────────────────────
    def send_response(self, code: int, message: str | None = None) -> None:  # type: ignore[override]
        self.__dict__["_metric_status"] = code
        super().send_response(code, message)  # type: ignore[misc]

    # ── wrap handle_one_request for timing + in-flight gauge ───────────────
    def handle_one_request(self) -> None:  # type: ignore[override]
        svc = getattr(self, "_service_name", "unknown")
        t0 = _time.perf_counter()
        self.__dict__["_metric_status"] = 200
        if _PROMETHEUS_AVAILABLE:
            HTTP_REQUESTS_IN_FLIGHT.labels(service=svc).inc()
        try:
            super().handle_one_request()  # type: ignore[misc]
        finally:
            if _PROMETHEUS_AVAILABLE:
                HTTP_REQUESTS_IN_FLIGHT.labels(service=svc).dec()
            command = getattr(self, "command", None)
            if command:
                path = getattr(self, "path", "/")
                duration = _time.perf_counter() - t0
                status = self.__dict__.get("_metric_status", 200)
                record_request(svc, command, path, status, duration)
