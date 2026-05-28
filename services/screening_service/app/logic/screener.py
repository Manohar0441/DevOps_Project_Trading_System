from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from services.common.configuration import MANUAL_METRICS_DIR


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


def _flatten_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    metrics = payload.get("metrics", payload)
    if not isinstance(metrics, dict):
        return {}

    flattened: dict[str, Any] = {}
    for key, value in metrics.items():
        if isinstance(value, dict):
            flattened.update(value)
        else:
            flattened[key] = value
    return flattened


def _load_manual_payload(ticker: str) -> dict[str, Any]:
    path = MANUAL_METRICS_DIR / f"{ticker.upper()}.json"
    if not path.exists():
        return {"ticker": ticker.upper(), "metrics": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def _candidate_payload(candidate: Any) -> dict[str, Any]:
    if isinstance(candidate, str):
        return _load_manual_payload(candidate)
    if isinstance(candidate, dict):
        ticker = str(candidate.get("ticker") or candidate.get("symbol") or "").upper()
        if "metrics" not in candidate and ticker:
            loaded = _load_manual_payload(ticker)
            loaded.update(candidate)
            return loaded
        return candidate
    return {}


def screen_candidates(payload: dict[str, Any]) -> dict[str, Any]:
    raw_candidates = payload.get("candidates") or payload.get("tickers") or []
    if isinstance(raw_candidates, str):
        raw_candidates = [item.strip() for item in raw_candidates.split(",") if item.strip()]
    if not isinstance(raw_candidates, list):
        raise ValueError("candidates or tickers must be a list or comma-separated string")

    min_eps_growth = _as_float(payload.get("min_eps_growth_yoy"), 5.0)
    min_revenue_growth = _as_float(payload.get("min_revenue_growth_yoy"), 0.0)
    min_score = _as_float(payload.get("min_score"), 0.0)

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for raw_candidate in raw_candidates:
        candidate = _candidate_payload(raw_candidate)
        ticker = str(candidate.get("ticker") or candidate.get("symbol") or "").upper()
        if not ticker:
            rejected.append({"ticker": "", "reason": "Missing ticker"})
            continue

        metrics = _flatten_metrics(candidate)
        eps_growth = _as_float(metrics.get("eps_growth_yoy"))
        revenue_growth = _as_float(metrics.get("revenue_growth_yoy"))
        operating_margin = _as_float(metrics.get("operating_margin"))
        roic = _as_float(metrics.get("roic"))
        debt_to_equity = _as_float(metrics.get("debt_to_equity"))

        quality_score = round(
            max(eps_growth, 0) * 0.35
            + max(revenue_growth, 0) * 0.25
            + max(operating_margin, 0) * 0.20
            + max(roic, 0) * 0.20
            - max(debt_to_equity - 1, 0) * 5,
            2,
        )

        reasons: list[str] = []
        if eps_growth < min_eps_growth:
            reasons.append(f"EPS growth {eps_growth:.2f} is below {min_eps_growth:.2f}")
        if revenue_growth < min_revenue_growth:
            reasons.append(f"Revenue growth {revenue_growth:.2f} is below {min_revenue_growth:.2f}")
        if quality_score < min_score:
            reasons.append(f"Quality score {quality_score:.2f} is below {min_score:.2f}")

        result = {
            "ticker": ticker,
            "quality_score": quality_score,
            "eps_growth_yoy": eps_growth,
            "revenue_growth_yoy": revenue_growth,
            "operating_margin": operating_margin,
            "roic": roic,
            "sector": candidate.get("sector") or candidate.get("metadata", {}).get("sector"),
        }
        if reasons:
            rejected.append({**result, "reasons": reasons})
        else:
            accepted.append(result)

    accepted.sort(key=lambda item: item["quality_score"], reverse=True)
    return {
        "accepted": accepted,
        "rejected": rejected,
        "summary": {
            "requested": len(raw_candidates),
            "accepted": len(accepted),
            "rejected": len(rejected),
        },
    }
