from __future__ import annotations

import logging
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from services.common.http_utils import read_json, send_json
from services.common.logging_utils import configure_logging
from services.common.metrics import (
    MetricsMixin,
    NOTIFICATIONS_DISPATCHED_TOTAL,
    init_service,
    send_metrics,
)
from services.notification_service.app.channels.email import build_email_notification
from services.notification_service.app.channels.sms import build_sms_notification
from services.notification_service.app.events.consumer import handle_sqs_notification_event, normalize_notification_event


logger = logging.getLogger(__name__)

_SERVICE = "notification-service"


class NotificationRequestHandler(MetricsMixin, BaseHTTPRequestHandler):
    server_version = "NotificationService/1.0"
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

            if route == "/v1/notifications/send":
                notification = self._build_notification(payload)
                channel = notification.get("channel", "unknown")
                logger.info(
                    "Notification accepted | channel=%s | recipient=%s | severity=%s",
                    channel,
                    notification.get("recipient"),
                    payload.get("severity", "info"),
                )
                NOTIFICATIONS_DISPATCHED_TOTAL.labels(channel=channel, status="success").inc()
                send_json(self, notification, status=HTTPStatus.ACCEPTED)
                return

            if route == "/v1/events/consume":
                notification_payload = normalize_notification_event(payload)
                notification = self._build_notification(notification_payload)
                channel = notification.get("channel", "unknown")
                NOTIFICATIONS_DISPATCHED_TOTAL.labels(channel=channel, status="success").inc()
                send_json(
                    self,
                    {"event_status": "consumed", "notification": notification},
                    status=HTTPStatus.ACCEPTED,
                )
                return

            send_json(self, {"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            logger.warning("Invalid notification request: %s", exc)
            send_json(self, {"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unhandled notification-service error: %s", exc)
            send_json(self, {"error": "Internal server error"}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def _build_notification(self, payload: dict) -> dict:
        channel = str(payload.get("channel") or "email").lower()
        if channel == "email":
            return build_email_notification(payload)
        if channel == "sms":
            return build_sms_notification(payload)
        raise ValueError("channel must be either email or sms")


def run_server() -> None:
    host = os.environ.get("NOTIFICATION_SERVICE_HOST", os.environ.get("SERVICE_HOST", "127.0.0.1"))
    port = int(os.environ.get("NOTIFICATION_SERVICE_PORT", os.environ.get("SERVICE_PORT", "8006")))
    configure_logging("notification-service", console=True)
    init_service(_SERVICE)

    sqs_queue_url = os.environ.get("SQS_NOTIFICATION_EVENTS_URL", "")
    if sqs_queue_url:
        from services.common.common.messaging.sqs_consumer import SQSConsumer
        SQSConsumer(queue_url=sqs_queue_url, handler=handle_sqs_notification_event).start()

    server = ThreadingHTTPServer((host, port), NotificationRequestHandler)
    logger.info("Notification service listening on %s:%s", host, port)
    server.serve_forever()


if __name__ == "__main__":
    run_server()
