from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def build_email_notification(payload: dict[str, Any]) -> dict[str, Any]:
    recipient = str(payload.get("recipient") or payload.get("to") or "").strip()
    subject = str(payload.get("subject") or "Trading alert").strip()
    message = str(payload.get("message") or "").strip()
    if not recipient:
        raise ValueError("recipient is required for email notification")
    if not message:
        raise ValueError("message is required for email notification")

    return {
        "channel": "email",
        "recipient": recipient,
        "subject": subject,
        "message": message,
        "status": "accepted",
        "accepted_at": datetime.now(timezone.utc).isoformat(),
    }
