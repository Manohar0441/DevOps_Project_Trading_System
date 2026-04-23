from __future__ import annotations

from typing import Any, Dict, List

from services.screening.constants import SECTOR_DEBT_LIMITS
from services.screening.helpers import normalize_ratio, safe_float


class UserInputValidator:
    def validate(self, user_inputs: Dict[str, Any], current_price: float | None = None) -> Dict[str, Any]:
        validations: Dict[str, Any] = {}

        entry_price = safe_float(user_inputs.get("entry_price"))
        stop_loss = safe_float(user_inputs.get("stop_loss"))
        target_price = safe_float(user_inputs.get("target_price"))
        exit_logic = user_inputs.get("exit_logic")
        risk_level = user_inputs.get("risk_level")

        validations["entry_price"] = self._status(
            entry_price is not None and entry_price > 0,
            entry_price,
            "Entry price must be a positive number.",
        )
        validations["stop_loss"] = self._validate_stop_loss(entry_price, stop_loss)
        validations["target_price"] = self._status(
            target_price is not None and target_price > 0 and (entry_price is None or target_price > entry_price),
            target_price,
            "Target price must be positive and above entry price.",
        )
        validations["exit_logic"] = self._status(
            isinstance(exit_logic, str) and bool(exit_logic.strip()),
            exit_logic,
            "Exit logic must be explicitly provided.",
        )
        validations["risk_level"] = self._status(
            risk_level in {"low", "medium", "high", "LOW", "MEDIUM", "HIGH"},
            risk_level,
            "Risk level should be one of low, medium, or high.",
        )

        if current_price is not None and entry_price is not None:
            validations["entry_vs_market"] = self._status(
                abs(entry_price - current_price) / current_price <= 0.1,
                entry_price,
                "Entry price is far from the latest reconciled market price.",
            )

        return {
            "inputs": validations,
            "overall_valid": all(item["valid"] for item in validations.values()),
        }

    def _validate_stop_loss(self, entry_price: float | None, stop_loss: float | None) -> Dict[str, Any]:
        if entry_price is None or stop_loss is None:
            return self._status(False, stop_loss, "Stop loss and entry price must both be supplied.")
        if stop_loss >= entry_price:
            return self._status(False, stop_loss, "Stop loss must be below entry price.")
        distance = (entry_price - stop_loss) / entry_price
        return self._status(0.05 <= distance <= 0.07, stop_loss, "Stop loss must sit 5% to 7% below entry price.")

    def _status(self, valid: bool, value: Any, message: str) -> Dict[str, Any]:
        return {"value": value, "valid": bool(valid), "message": "ok" if valid else message}


class ScreeningValidator:
    def sector_debt_limit(self, sector: str | None) -> float:
        if not sector:
            return 2.0
        lowered = sector.lower()
        for key, value in SECTOR_DEBT_LIMITS.items():
            if key in lowered:
                return value
        return 2.0

    def positive_stable_margin(self, margin: float | None, quarterly_margins: List[Dict[str, Any]]) -> bool:
        if margin is None or margin <= 0:
            return False
        recent = [normalize_ratio(item.get("value")) for item in quarterly_margins[:4]]
        recent = [value for value in recent if value is not None]
        if len(recent) < 2:
            return True
        latest = recent[0]
        previous = recent[1]
        return latest is not None and previous is not None and latest >= previous - 0.01

    def accounting_red_flags(self, final_metrics: Dict[str, Any]) -> List[str]:
        flags: List[str] = []
        ebitda = self._final_value(final_metrics, "ebitda")
        ocf = self._final_value(final_metrics, "operating_cash_flow")
        net_income = self._final_value(final_metrics, "net_income")
        intangibles = self._final_value(final_metrics, "intangibles")
        amortization = self._final_value(final_metrics, "amortization")
        quarterly_ocf = final_metrics.get("quarterly_operating_cash_flow", {}).get("final_value", [])
        quarterly_net_income = final_metrics.get("quarterly_net_income", {}).get("final_value", [])

        if ebitda is not None and ocf is not None and ebitda > 0 and ocf < (0.5 * ebitda):
            flags.append("EBITDA is strong but operating cash flow is weak.")
        if intangibles is not None and net_income is not None and net_income != 0 and intangibles > abs(net_income) * 2:
            flags.append("Intangibles are large relative to earnings and may reflect acquisition-heavy growth.")
        if amortization is not None and ebitda is not None and ebitda > 0 and abs(amortization) / ebitda > 0.25:
            flags.append("Amortization is materially large relative to EBITDA.")

        cash_conversion_failures = 0
        net_income_map = {item["period"]: item["value"] for item in quarterly_net_income}
        for item in quarterly_ocf[:4]:
            income = net_income_map.get(item["period"])
            if income is None or income <= 0:
                continue
            if item["value"] < income:
                cash_conversion_failures += 1
        if cash_conversion_failures >= 2:
            flags.append("Cash conversion is poor over multiple consecutive quarters.")
        return flags

    def _final_value(self, final_metrics: Dict[str, Any], key: str) -> float | None:
        metric = final_metrics.get(key, {})
        return safe_float(metric.get("final_value")) if isinstance(metric, dict) else None
