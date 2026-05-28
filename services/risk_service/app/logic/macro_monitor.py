from __future__ import annotations

from typing import Any


def evaluate_macro_flags(payload: dict[str, Any]) -> dict[str, Any]:
    flags = payload.get("macro_flags", {})
    if not isinstance(flags, dict):
        flags = {}

    elevated = [
        key
        for key, value in flags.items()
        if str(value).lower() in {"high", "true", "risk", "elevated", "negative"}
    ]
    return {
        "status": "CAUTION" if elevated else "CLEAR",
        "elevated_flags": elevated,
        "message": "Macro risk flags detected." if elevated else "No macro overrides detected.",
    }
