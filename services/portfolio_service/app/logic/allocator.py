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


def allocate_portfolio(payload: dict[str, Any]) -> dict[str, Any]:
    capital = _as_float(payload.get("capital"), 100000.0)
    max_positions = int(_as_float(payload.get("max_positions"), 5))
    max_position_pct = _as_float(payload.get("max_position_pct"), 20.0)
    stop_loss_pct = _as_float(payload.get("default_stop_loss_pct"), 8.0)
    candidates = payload.get("candidates", [])

    if capital <= 0:
        raise ValueError("capital must be greater than zero")
    if max_positions <= 0:
        raise ValueError("max_positions must be greater than zero")
    if not isinstance(candidates, list):
        raise ValueError("candidates must be a list")

    normalized_candidates: list[dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        ticker = str(candidate.get("ticker") or candidate.get("symbol") or "").upper()
        if not ticker:
            continue
        score = _as_float(candidate.get("total_score", candidate.get("quality_score", candidate.get("score"))), 1.0)
        price = _as_float(candidate.get("price", candidate.get("current_price")), 0.0)
        normalized_candidates.append({**candidate, "ticker": ticker, "allocation_score": max(score, 1.0), "price": price})

    ranked = sorted(normalized_candidates, key=lambda item: item["allocation_score"], reverse=True)[:max_positions]
    score_total = sum(item["allocation_score"] for item in ranked) or 1.0
    max_position_value = capital * (max_position_pct / 100)

    allocations: list[dict[str, Any]] = []
    allocated_capital = 0.0
    for candidate in ranked:
        target_value = min(capital * (candidate["allocation_score"] / score_total), max_position_value)
        price = candidate["price"]
        quantity = int(target_value // price) if price > 0 else None
        actual_value = round(quantity * price, 2) if quantity is not None else round(target_value, 2)
        allocated_capital += actual_value
        allocations.append(
            {
                "ticker": candidate["ticker"],
                "target_value": round(target_value, 2),
                "allocated_value": actual_value,
                "allocation_pct": round((actual_value / capital) * 100, 2),
                "quantity": quantity,
                "reference_price": price or None,
                "stop_loss_pct": stop_loss_pct,
                "stop_loss_price": round(price * (1 - stop_loss_pct / 100), 2) if price > 0 else None,
            }
        )

    return {
        "capital": round(capital, 2),
        "allocated_capital": round(allocated_capital, 2),
        "cash_remaining": round(capital - allocated_capital, 2),
        "allocations": allocations,
        "constraints": {
            "max_positions": max_positions,
            "max_position_pct": max_position_pct,
            "default_stop_loss_pct": stop_loss_pct,
        },
    }
