from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Tuple

from processors import valuation
from processors.metric_engine import normalize_decimal_ratio, saas_exception, to_float


DECIMAL_METRICS = {
    ("valuation", "Dividend_Yield"),
    ("valuation", "Earnings_Yield"),
    ("valuation", "FCF_Yield"),
    ("profitability", "ROE"),
    ("profitability", "ROIC"),
    ("profitability", "ROA"),
    ("profitability", "ROCE"),
    ("profitability", "Gross_Margin"),
    ("profitability", "Operating_Margin"),
    ("profitability", "Net_Margin"),
    ("profitability", "EBITDA_Margin"),
    ("cashflow", "OCF_Margin"),
    ("cashflow", "FCF_Margin"),
    ("cashflow", "FCF_Yield"),
    ("growth", "Revenue_Growth"),
    ("growth", "Revenue_Growth_Rate"),
    ("growth", "EPS_Growth"),
    ("growth", "EPS_Growth_Rate"),
    ("growth", "Dividend_Payout_Ratio"),
    ("growth", "Retention_Ratio"),
    ("growth", "Dividend_Growth_Rate"),
    ("ownership", "Institutional_Ownership"),
    ("ownership", "Insider_Ownership"),
}


def _append_issue(
    issues: List[Dict[str, Any]],
    section: str,
    metric: str,
    failure: str,
    root_cause: str,
    severity: str,
    action: str,
    original_value: Any,
    corrected_value: Any = None,
) -> None:
    issues.append(
        {
            "section": section,
            "metric": metric,
            "failure": failure,
            "root_cause": root_cause,
            "severity": severity,
            "action": action,
            "original_value": original_value,
            "corrected_value": corrected_value,
        }
    )


def _normalize_decimal_metrics(metrics: Dict[str, Any], issues: List[Dict[str, Any]]) -> None:
    for section, metric in DECIMAL_METRICS:
        section_data = metrics.get(section)
        if not isinstance(section_data, dict) or metric not in section_data:
            continue

        original_value = section_data.get(metric)
        normalized_value = normalize_decimal_ratio(original_value)
        if normalized_value != original_value:
            section_data[metric] = normalized_value
            _append_issue(
                issues,
                section,
                metric,
                "percentage metric was not stored as a decimal",
                "unit normalization failure in calculation layer",
                "MAJOR",
                "normalized_to_decimal",
                original_value,
                normalized_value,
            )


def _invalidate_metric(
    metrics: Dict[str, Any],
    section: str,
    metric: str,
    issues: List[Dict[str, Any]],
    failure: str,
    root_cause: str,
    severity: str,
    original_value: Any,
) -> None:
    if isinstance(metrics.get(section), dict) and metric in metrics[section]:
        metrics[section][metric] = None
    _append_issue(
        issues,
        section,
        metric,
        failure,
        root_cause,
        severity,
        "invalidated",
        original_value,
        None,
    )


def _validation_summary(metrics: Dict[str, Any], issues: List[Dict[str, Any]]) -> Dict[str, Any]:
    valuation_issues = [issue for issue in issues if issue["section"] == "valuation"]
    hard_failures = [issue for issue in issues if issue["severity"] == "CRITICAL"]
    valuation = metrics.get("valuation", {})
    valuation_meta = valuation.get("_meta", {}) if isinstance(valuation, dict) else {}
    growth_meta = metrics.get("growth", {}).get("_meta", {}) if isinstance(metrics.get("growth"), dict) else {}
    cashflow_meta = metrics.get("cashflow", {}).get("_meta", {}) if isinstance(metrics.get("cashflow"), dict) else {}

    return {
        "status": "FAIL" if hard_failures else ("WARN" if issues else "PASS"),
        "issue_count": len(issues),
        "hard_failure_count": len(hard_failures),
        "valuation_passed": not valuation_issues and all(
            valuation.get(metric) is not None for metric in ("PE", "PEG", "EV_Sales", "Dividend_Yield")
        ),
        "time_consistency": {
            "valuation_period_basis": valuation_meta.get("valuation_period_basis"),
            "growth_revenue_basis": growth_meta.get("revenue_growth_basis"),
            "growth_eps_basis": growth_meta.get("eps_growth_basis"),
            "cashflow_basis": cashflow_meta.get("fcf_basis"),
            "uses_forward_estimates": False,
        },
        "issues": issues,
    }


def validate_metrics(raw_data: Dict[str, Any], metrics: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    sanitized = deepcopy(metrics)
    issues: List[Dict[str, Any]] = []

    _normalize_decimal_metrics(sanitized, issues)

    growth_section = sanitized.get("growth", {})
    if isinstance(growth_section, dict) and "Dividend_Yield" in growth_section:
        original_value = growth_section.pop("Dividend_Yield")
        _append_issue(
            issues,
            "growth",
            "Dividend_Yield",
            "Dividend Yield existed outside the valuation section",
            "duplicate source-of-truth design",
            "CRITICAL",
            "removed_duplicate_metric",
            original_value,
            None,
        )

    valuation = sanitized.get("valuation", {}) if isinstance(sanitized.get("valuation"), dict) else {}
    profitability = sanitized.get("profitability", {}) if isinstance(sanitized.get("profitability"), dict) else {}
    cashflow = sanitized.get("cashflow", {}) if isinstance(sanitized.get("cashflow"), dict) else {}
    valuation_meta = valuation.get("_meta", {}) if isinstance(valuation.get("_meta"), dict) else {}
    profitability_meta = profitability.get("_meta", {}) if isinstance(profitability.get("_meta"), dict) else {}

    ebitda_margin = to_float(profitability.get("EBITDA_Margin"))
    if valuation_meta.get("revenue_basis") not in {"TTM", "ANNUAL"}:
        _append_issue(
            issues,
            "valuation",
            "EV_Sales",
            "valuation section used an unsupported fiscal basis",
            "period-selection layer returned inconsistent revenue basis",
            "CRITICAL",
            "flagged_period_inconsistency",
            valuation_meta.get("revenue_basis"),
            valuation_meta.get("revenue_basis"),
        )

    # SaaS-friendly handling:
    # High EBITDA margins should be flagged, not nulled, because SaaS businesses
    # often have EBITDA that differs materially from operating income due to D&A
    # and other non-cash items.
    if ebitda_margin is not None and ebitda_margin > 0.60 and not saas_exception(raw_data):
        _append_issue(
            issues,
            "profitability",
            "EBITDA_Margin",
            "EBITDA Margin is unusually high",
            "possible EBITDA reconstruction mismatch",
            "MAJOR",
            "flagged_only",
            ebitda_margin,
            ebitda_margin,
        )

    operating_income_for_ebitda = to_float(valuation_meta.get("operating_income_for_ebitda"))
    ebitda_numeric = to_float(valuation_meta.get("ebitda_value"))
    if ebitda_numeric is None:
        ebitda_numeric = to_float(profitability_meta.get("ebitda_value"))

    # Only invalidate if EBITDA is actually unusable.
    if ebitda_numeric is None or ebitda_numeric <= 0:
        _invalidate_metric(
            sanitized,
            "profitability",
            "EBITDA_Margin",
            issues,
            "EBITDA was missing or non-positive",
            "EBITDA reconstruction failed or produced an unusable value",
            "CRITICAL",
            profitability.get("EBITDA_Margin"),
        )
        if "EV_EBITDA" in valuation:
            _invalidate_metric(
                sanitized,
                "valuation",
                "EV_EBITDA",
                issues,
                "EV/EBITDA relied on unusable EBITDA",
                "EBITDA was missing or non-positive",
                "CRITICAL",
                valuation.get("EV_EBITDA"),
            )
    elif operating_income_for_ebitda is not None and ebitda_numeric > operating_income_for_ebitda * 1.3:
        # Warning only; do not null valid SaaS metrics.
        _append_issue(
            issues,
            "profitability",
            "EBITDA_Margin",
            "EBITDA exceeded operating income by more than 30%",
            "possible SaaS-style accounting mismatch or reconstruction asymmetry",
            "MAJOR",
            "flagged_only",
            profitability.get("EBITDA_Margin"),
            profitability.get("EBITDA_Margin"),
        )

    peg = to_float(valuation.get("PEG"))

    if peg is not None:

    # Negative PEG (invalid)
        if peg < 0:
            _append_issue(
            issues,
            "valuation",
            "PEG",
            "PEG was negative",
            "growth/earnings mismatch",
            "MAJOR",
            "flagged_only",
            peg,
            peg,
        )

    # Suspiciously low PEG (likely unit/data issue)
        elif peg < 0.5:
         _append_issue(
            issues,
            "valuation",
            "PEG",
            "PEG unusually low",
            "possible growth unit mismatch or calculation error",
            "MAJOR",
            "flagged_only",
            peg,
            peg,
        )

    # High PEG (overvaluation signal)
    elif peg > 5:
        _append_issue(
            issues,
            "valuation",
            "PEG",
            "PEG is high",
            "growth stock priced richly relative to growth",
            "MAJOR",
            "flagged_only",
            peg,
            peg,
        )
    ev_sales = to_float(valuation.get("EV_Sales"))
    if ev_sales is not None and ev_sales > 15:
        _invalidate_metric(
            sanitized,
            "valuation",
            "EV_Sales",
            issues,
            "EV/Sales exceeded the 15x sanity ceiling",
            "enterprise value or revenue input is likely stale or mismatched",
            "MAJOR",
            ev_sales,
        )

    raw_capex_to_ocf = to_float(cashflow.get("_meta", {}).get("capex_to_ocf_raw")) if isinstance(cashflow.get("_meta"), dict) else None
    if raw_capex_to_ocf is not None and raw_capex_to_ocf > 0.7:
        _invalidate_metric(
            sanitized,
            "cashflow",
            "Capex_to_OCF_Ratio",
            issues,
            "Capex/OCF exceeded the 0.7 hard ceiling",
            "capex or operating cash flow is inconsistent for the reported period",
            "MAJOR",
            raw_capex_to_ocf,
        )

    fcf_yield = to_float(cashflow.get("FCF_Yield"))
    net_income = to_float(profitability.get("Net_Income"))
    if fcf_yield is not None and fcf_yield < 0 and net_income is not None and net_income > 0:
        _invalidate_metric(
            sanitized,
            "cashflow",
            "FCF_Yield",
            issues,
            "FCF Yield was negative while Net Income was positive",
            "cash flow and market-cap inputs are inconsistent",
            "MAJOR",
            fcf_yield,
        )
        if isinstance(valuation, dict) and "FCF_Yield" in valuation:
            _invalidate_metric(
                sanitized,
                "valuation",
                "FCF_Yield",
                issues,
                "FCF Yield was negative while Net Income was positive",
                "cash flow and market-cap inputs are inconsistent",
                "MAJOR",
                valuation.get("FCF_Yield"),
            )

    if isinstance(valuation.get("_meta"), dict) and not valuation["_meta"].get("price_consistent_market_cap", False):
        _invalidate_metric(
            sanitized,
            "cashflow",
            "FCF_Yield",
            issues,
            "FCF Yield did not have price-date consistent market cap",
            "market cap fallback was not tied to the latest price snapshot",
            "CRITICAL",
            cashflow.get("FCF_Yield"),
        )
        if isinstance(valuation, dict) and "FCF_Yield" in valuation:
            _invalidate_metric(
                sanitized,
                "valuation",
                "FCF_Yield",
                issues,
                "FCF Yield did not have price-date consistent market cap",
                "market cap fallback was not tied to the latest price snapshot",
                "CRITICAL",
                valuation.get("FCF_Yield"),
            )

    if isinstance(valuation.get("_meta"), dict) and not valuation["_meta"].get("price_consistent_dividend_yield", False):
        _invalidate_metric(
            sanitized,
            "valuation",
            "Dividend_Yield",
            issues,
            "Dividend Yield did not have price-date consistency",
            "dividend yield was not anchored to the same price snapshot",
            "CRITICAL",
            valuation.get("Dividend_Yield"),
        )

    report = _validation_summary(sanitized, issues)
    return sanitized, report