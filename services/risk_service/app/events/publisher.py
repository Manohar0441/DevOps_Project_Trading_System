from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def build_risk_event(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "source": "risk-service",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
