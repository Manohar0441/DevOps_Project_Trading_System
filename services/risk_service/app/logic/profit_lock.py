from __future__ import annotations

from typing import Any


def _as_float(value: Any, default: float = 0.0) -> float:
    if value is None or isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip().replace("%", ""))
        except ValueError:
            return default
    return default


def evaluate_profit_locks(positions: list[dict[str, Any]], lock_threshold_pct: float = 15.0) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    for position in positions:
        ticker = str(position.get("ticker") or position.get("symbol") or "").upper()
        entry_price = _as_float(position.get("entry_price"))
        current_price = _as_float(position.get("current_price", position.get("price")))
        if not ticker or entry_price <= 0 or current_price <= 0:
            continue
        gain_pct = ((current_price - entry_price) / entry_price) * 100
        if gain_pct >= lock_threshold_pct:
            signals.append(
                {
                    "ticker": ticker,
                    "signal": "PROFIT_LOCK",
                    "gain_pct": round(gain_pct, 2),
                    "message": f"Gain is above {lock_threshold_pct:.2f}%; consider trailing stop or partial exit.",
                }
            )
    return signals
