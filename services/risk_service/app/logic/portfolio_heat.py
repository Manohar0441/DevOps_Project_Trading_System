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


def evaluate_portfolio_heat(payload: dict[str, Any]) -> dict[str, Any]:
    positions = payload.get("positions", [])
    capital = _as_float(payload.get("capital"), 0.0)
    max_heat_pct = _as_float(payload.get("max_portfolio_heat_pct"), 30.0)

    if not isinstance(positions, list):
        raise ValueError("positions must be a list")

    evaluated: list[dict[str, Any]] = []
    total_market_value = 0.0
    total_risk_value = 0.0

    for position in positions:
        if not isinstance(position, dict):
            continue
        ticker = str(position.get("ticker") or position.get("symbol") or "").upper()
        quantity = _as_float(position.get("quantity"), 0.0)
        current_price = _as_float(position.get("current_price", position.get("price")), 0.0)
        entry_price = _as_float(position.get("entry_price"), current_price)
        stop_loss_price = _as_float(position.get("stop_loss_price"), current_price * 0.92)
        market_value = quantity * current_price
        risk_value = max((current_price - stop_loss_price) * quantity, 0.0)

        total_market_value += market_value
        total_risk_value += risk_value
        evaluated.append(
            {
                "ticker": ticker,
                "market_value": round(market_value, 2),
                "unrealized_return_pct": round(((current_price - entry_price) / entry_price) * 100, 2)
                if entry_price > 0
                else 0.0,
                "risk_value": round(risk_value, 2),
            }
        )

    base_capital = capital or total_market_value or 1.0
    heat_pct = round((total_risk_value / base_capital) * 100, 2)
    return {
        "portfolio_heat_pct": heat_pct,
        "max_portfolio_heat_pct": max_heat_pct,
        "status": "PASS" if heat_pct <= max_heat_pct else "BREACH",
        "total_market_value": round(total_market_value, 2),
        "total_risk_value": round(total_risk_value, 2),
        "positions": evaluated,
    }
