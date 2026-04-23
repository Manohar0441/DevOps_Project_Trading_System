from __future__ import annotations

from typing import Any, Dict, List

from services.screening.helpers import safe_float
from services.screening.validation import ScreeningValidator


class ScreeningEngine:
    def __init__(self) -> None:
        self.validator = ScreeningValidator()

    def evaluate(
        self,
        ticker: str,
        final_metrics: Dict[str, Any],
        user_input_validation: Dict[str, Any],
        peer_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        checks: Dict[str, Any] = {}
        reasons: List[str] = []

        quarterly_revenue = final_metrics.get("quarterly_revenue", {}).get("final_value", [])
        quarterly_net_income = final_metrics.get("quarterly_net_income", {}).get("final_value", [])
        quarterly_margin = final_metrics.get("quarterly_net_profit_margin", {}).get("final_value", [])

        revenue_growth = self._metric(final_metrics, "revenue_growth")
        net_profit_margin = self._metric(final_metrics, "net_profit_margin")
        operating_cash_flow = self._metric(final_metrics, "operating_cash_flow")
        net_income = self._metric(final_metrics, "net_income")
        debt_to_equity = self._metric(final_metrics, "debt_to_equity")
        pe_ratio = self._metric(final_metrics, "pe_ratio")
        industry_average_pe = self._metric(final_metrics, "industry_average_pe")
        rsi = self._metric(final_metrics, "rsi")
        pullback = self._metric(final_metrics, "pullback_percentage")

        checks["quarterly_momentum"] = self._check_quarterly_momentum(quarterly_revenue, quarterly_net_income)
        checks["revenue_growth"] = self._result(
            revenue_growth is not None and revenue_growth > 0.08,
            revenue_growth,
            "Revenue growth must be greater than 8%.",
        )
        checks["profitability"] = self._result(
            self.validator.positive_stable_margin(net_profit_margin, quarterly_margin),
            net_profit_margin,
            "Net profit margin must be positive and stable or expanding.",
        )
        checks["cash_flow_quality"] = self._result(
            operating_cash_flow is not None and net_income is not None and operating_cash_flow > net_income,
            {"operating_cash_flow": operating_cash_flow, "net_income": net_income},
            "Operating cash flow must exceed net income.",
        )

        red_flags = self.validator.accounting_red_flags(final_metrics)
        checks["accounting_quality"] = self._result(
            not red_flags,
            red_flags,
            "Accounting red flags require deeper review.",
        )

        sector = peer_context.get("sector")
        debt_limit = self.validator.sector_debt_limit(sector)
        checks["debt_health"] = self._result(
            debt_to_equity is not None and debt_to_equity < debt_limit,
            {"debt_to_equity": debt_to_equity, "limit": debt_limit},
            "Debt to equity exceeds the allowable threshold.",
        )
        checks["valuation"] = self._result(
            pe_ratio is not None
            and industry_average_pe is not None
            and pe_ratio <= industry_average_pe * 1.3,
            {"pe_ratio": pe_ratio, "industry_average_pe": industry_average_pe},
            "P/E ratio is more than 30% above the industry average.",
        )
        checks["technical_condition"] = self._result(
            rsi is not None and rsi < 70,
            rsi,
            "RSI must be below 70.",
        )
        checks["entry_price_discipline"] = self._result(
            pullback is not None and 0.05 <= pullback <= 0.08,
            pullback,
            "Entry should be 5% to 8% below the recent high.",
        )
        checks["stop_loss_discipline"] = self._user_input_result(user_input_validation, "stop_loss")
        checks["exit_plan"] = self._result(
            user_input_validation.get("inputs", {}).get("target_price", {}).get("valid", False)
            and user_input_validation.get("inputs", {}).get("exit_logic", {}).get("valid", False),
            {
                "target_price": user_input_validation.get("inputs", {}).get("target_price"),
                "exit_logic": user_input_validation.get("inputs", {}).get("exit_logic"),
            },
            "Target price and exit logic must be explicitly defined.",
        )

        critical_conflicts = [
            key for key, metric in final_metrics.items()
            if isinstance(metric, dict) and metric.get("data_conflict") and metric.get("requires_review")
        ]
        review_required_metrics = [
            key for key, metric in final_metrics.items()
            if isinstance(metric, dict) and metric.get("requires_review")
        ]
        incomplete_critical = [
            key for key, metric in final_metrics.items()
            if isinstance(metric, dict) and metric.get("final_value") in (None, []) and metric.get("requires_review")
        ]
        failed_rules = [name for name, result in checks.items() if not result["pass"]]

        if critical_conflicts:
            reasons.append(f"Critical data conflicts: {', '.join(sorted(critical_conflicts))}")
        if review_required_metrics:
            reasons.append(f"Metrics requiring review: {', '.join(sorted(review_required_metrics))}")
        if red_flags:
            reasons.extend(red_flags)
        if incomplete_critical:
            reasons.append(f"Incomplete critical metrics: {', '.join(sorted(incomplete_critical))}")
        for rule_name in failed_rules:
            reasons.append(f"{rule_name}: {checks[rule_name]['message']}")

        decision = "ACCEPT"
        if review_required_metrics or critical_conflicts or red_flags or incomplete_critical:
            decision = "REVIEW_REQUIRED"
        if failed_rules:
            decision = "REJECT"
            if review_required_metrics or critical_conflicts or red_flags:
                decision = "REVIEW_REQUIRED"

        return {
            "ticker": ticker,
            "screening_checks": checks,
            "failed_rules": failed_rules,
            "accounting_red_flags": red_flags,
            "critical_data_conflicts": critical_conflicts,
            "review_required_metrics": review_required_metrics,
            "incomplete_critical_metrics": incomplete_critical,
            "final_decision": decision,
            "reasons_for_decision": reasons,
        }

    def _metric(self, final_metrics: Dict[str, Any], key: str) -> float | None:
        metric = final_metrics.get(key, {})
        return safe_float(metric.get("final_value")) if isinstance(metric, dict) else None

    def _result(self, passed: bool, value: Any, message: str) -> Dict[str, Any]:
        return {"pass": bool(passed), "value": value, "message": "ok" if passed else message}

    def _user_input_result(self, validation: Dict[str, Any], key: str) -> Dict[str, Any]:
        payload = validation.get("inputs", {}).get(key, {})
        return {
            "pass": bool(payload.get("valid")),
            "value": payload.get("value"),
            "message": payload.get("message", "invalid"),
        }

    def _check_quarterly_momentum(
        self,
        quarterly_revenue: List[Dict[str, Any]],
        quarterly_net_income: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        basis = "quarterly_revenue"
        series = quarterly_revenue
        if len(series) < 3:
            series = quarterly_net_income
            basis = "quarterly_net_income"

        values = [safe_float(item.get("value")) for item in series[:3]]
        values = [value for value in values if value is not None]
        passed = len(values) >= 3 and values[0] > values[1] > values[2]
        return {
            "pass": passed,
            "value": {"basis": basis, "series": series[:3]},
            "message": "ok" if passed else "Latest two quarter-over-quarter moves do not show consecutive improvement.",
        }
