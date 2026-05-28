from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def build_sms_notification(payload: dict[str, Any]) -> dict[str, Any]:
    recipient = str(payload.get("recipient") or payload.get("phone") or payload.get("to") or "").strip()
    message = str(payload.get("message") or "").strip()
    if not recipient:
        raise ValueError("recipient is required for SMS notification")
    if not message:
        raise ValueError("message is required for SMS notification")

    return {
        "channel": "sms",
        "recipient": recipient,
        "message": message[:320],
        "status": "accepted",
        "accepted_at": datetime.now(timezone.utc).isoformat(),
    }
