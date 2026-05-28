from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def normalize_notification_event(payload: dict[str, Any]) -> dict[str, Any]:
    event_payload = payload.get("payload") if isinstance(payload.get("payload"), dict) else payload
    return {
        "channel": event_payload.get("channel", "email"),
        "recipient": event_payload.get("recipient") or event_payload.get("to") or event_payload.get("phone"),
        "subject": event_payload.get("subject", "Trading alert"),
        "message": event_payload.get("message", ""),
        "severity": event_payload.get("severity", "info"),
    }


def handle_sqs_notification_event(message: dict[str, Any]) -> None:
    """Process a notification event received from the SQS notification-events queue."""
    event_type = message.get("event_type", "unknown")
    normalized = normalize_notification_event(message.get("payload", message))
    logger.info(
        "SQS event consumed | type=%s | channel=%s | recipient=%s | severity=%s",
        event_type,
        normalized.get("channel"),
        normalized.get("recipient"),
        normalized.get("severity"),
    )
