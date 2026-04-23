from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from services.screening.constants import METRIC_DEFINITIONS, USER_INPUT_KEYS
from services.screening.helpers import first_present, normalize_period_label, normalize_ratio, safe_float


class InputParser:
    def parse(
        self,
        ticker: Optional[str] = None,
        input_path: Optional[str] = None,
        user_inputs_path: Optional[str] = None,
        inline_user_inputs: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        input_payload = self._read_json(input_path) if input_path else {}
        user_inputs_payload = self._read_json(user_inputs_path) if user_inputs_path else {}

        merged_user_inputs = {}
        merged_user_inputs.update(input_payload.get("user_inputs", {}) or {})
        merged_user_inputs.update(user_inputs_payload or {})
        merged_user_inputs.update(inline_user_inputs or {})

        resolved_ticker = (
            ticker
            or input_payload.get("ticker")
            or input_payload.get("symbol")
            or input_payload.get("meta", {}).get("ticker")
        )
        if resolved_ticker:
            resolved_ticker = str(resolved_ticker).upper()

        parsed_metrics = self._extract_metrics(input_payload)
        return {
            "ticker": resolved_ticker,
            "raw_input": input_payload,
            "input_metrics": parsed_metrics,
            "user_inputs": {key: merged_user_inputs.get(key) for key in USER_INPUT_KEYS if key in merged_user_inputs},
            "additional_user_inputs": {
                key: value for key, value in merged_user_inputs.items() if key not in USER_INPUT_KEYS
            },
        }

    def _read_json(self, path: str) -> Dict[str, Any]:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
        raise ValueError(f"Expected a JSON object in {path}")

    def _extract_metrics(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        metrics: Dict[str, Any] = {}
        candidate_maps = [
            payload,
            payload.get("metrics", {}) or {},
            payload.get("financials", {}) or {},
            payload.get("valuation", {}) or {},
            payload.get("profitability", {}) or {},
            payload.get("cashflow", {}) or {},
            payload.get("growth", {}) or {},
            payload.get("technical", {}) or {},
        ]

        merged: Dict[str, Any] = {}
        for mapping in candidate_maps:
            if isinstance(mapping, dict):
                merged.update(mapping)

        for key, definition in METRIC_DEFINITIONS.items():
            raw_value = first_present(merged, definition.input_aliases)
            if key.startswith("quarterly_"):
                metrics[key] = self._extract_series(payload, definition.input_aliases)
            elif key in {"revenue_growth", "net_profit_margin", "debt_to_equity", "rsi", "pullback_percentage"}:
                metrics[key] = normalize_ratio(raw_value)
            else:
                metrics[key] = safe_float(raw_value)

        if not metrics.get("quarterly_net_profit_margin"):
            metrics["quarterly_net_profit_margin"] = self._derive_margin_series(
                metrics.get("quarterly_net_income"),
                metrics.get("quarterly_revenue"),
            )
        return metrics

    def _extract_series(self, payload: Dict[str, Any], aliases: tuple[str, ...]) -> list[Dict[str, Any]]:
        quarterly = payload.get("quarterly", {}) if isinstance(payload.get("quarterly"), dict) else {}
        raw_series = first_present(payload, aliases) or first_present(quarterly, aliases)
        if raw_series is None:
            return []

        items = []
        if isinstance(raw_series, dict):
            iterator = raw_series.items()
        elif isinstance(raw_series, list):
            iterator = []
            for item in raw_series:
                if isinstance(item, dict):
                    iterator.append((item.get("period") or item.get("quarter") or item.get("date"), item.get("value")))
        else:
            return []

        for period, raw_value in iterator:
            numeric = safe_float(raw_value)
            period_label = normalize_period_label(period)
            if numeric is None or period_label is None:
                continue
            items.append({"period": period_label, "value": numeric})

        return sorted(items, key=lambda item: item["period"], reverse=True)

    def _derive_margin_series(
        self,
        income_series: list[Dict[str, Any]],
        revenue_series: list[Dict[str, Any]],
    ) -> list[Dict[str, Any]]:
        if not income_series or not revenue_series:
            return []
        revenue_map = {item["period"]: item["value"] for item in revenue_series}
        derived = []
        for item in income_series:
            revenue = revenue_map.get(item["period"])
            if revenue in (None, 0):
                continue
            derived.append({"period": item["period"], "value": item["value"] / revenue})
        return sorted(derived, key=lambda item: item["period"], reverse=True)
