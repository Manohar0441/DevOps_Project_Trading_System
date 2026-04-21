import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _get(metrics: Dict[str, Any], *path: str) -> Any:
    """
    Safe nested getter.
    Returns None if any level is missing.
    """
    cur: Any = metrics
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def _is_valid_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _positive(value: Any) -> bool:
    return _is_valid_number(value) and value > 0


def _negative_or_zero(value: Any) -> bool:
    return _is_valid_number(value) and value <= 0


def _lt(value: Any, threshold: float) -> bool:
    return _is_valid_number(value) and value < threshold


def _gt(value: Any, threshold: float) -> bool:
    return _is_valid_number(value) and value > threshold


def _score_check(condition: bool, points: int = 1) -> int:
    return points if condition else 0


def holistic_valuation_framework(metrics: Dict[str, Any]) -> Dict[str, Any]:
    valuation = metrics.get("valuation", {}) or {}
    profitability = metrics.get("profitability", {}) or {}
    financial_health = metrics.get("financial_health", {}) or {}
    cashflow = metrics.get("cashflow", {}) or {}
    growth = metrics.get("growth", {}) or {}
    risk = metrics.get("risk", {}) or {}
    competitive = metrics.get("competitive", {}) or {}
    valuation_models = metrics.get("valuation_models", {}) or {}

    pe = valuation.get("PE")
    pb = valuation.get("PB")
    ps = valuation.get("PS")
    earnings_yield = valuation.get("Earnings_Yield")
    fcf_yield = valuation.get("FCF_Yield")

    roe = profitability.get("ROE")
    roic = profitability.get("ROIC")
    roa = profitability.get("ROA")
    gross_margin = profitability.get("Gross_Margin")
    operating_margin = profitability.get("Operating_Margin")
    net_margin = profitability.get("Net_Margin")

    current_ratio = financial_health.get("Current_Ratio")
    quick_ratio = financial_health.get("Quick_Ratio")
    debt_to_equity = financial_health.get("Debt_to_Equity")
    interest_coverage = financial_health.get("Interest_Coverage")

    fcf = cashflow.get("FCF")
    ocf = cashflow.get("OCF")
    fcf_margin = cashflow.get("FCF_Margin")
    cash_conversion = cashflow.get("Cash_Conversion_Ratio")

    revenue_growth = growth.get("Revenue_Growth")
    eps_growth = growth.get("EPS_Growth")
    earnings_stability = growth.get("Earnings_Stability")
    dividend_growth = growth.get("Dividend_Growth_Rate")

    volatility = risk.get("Standard Deviation")
    sharpe = risk.get("Sharpe Ratio")
    beta = risk.get("Beta")

    moat_score = _get(metrics, "competitive", "moat", "moat_score")

    # Component scores
    valuation_score = 0
    valuation_score += _score_check(_lt(pe, 25))
    valuation_score += _score_check(_lt(pb, 5))
    valuation_score += _score_check(_lt(ps, 8))
    valuation_score += _score_check(_gt(earnings_yield, 0.04))
    valuation_score += _score_check(_gt(fcf_yield, 0.03))
    valuation_score = min(5, valuation_score)

    profitability_score = 0
    profitability_score += _score_check(_gt(roe, 0.15))
    profitability_score += _score_check(_gt(roic, 0.10))
    profitability_score += _score_check(_gt(roa, 0.05))
    profitability_score += _score_check(_gt(gross_margin, 0.30))
    profitability_score += _score_check(_gt(operating_margin, 0.15))
    profitability_score += _score_check(_gt(net_margin, 0.10))
    profitability_score = min(5, profitability_score)

    balance_sheet_score = 0
    balance_sheet_score += _score_check(_gt(current_ratio, 1.2))
    balance_sheet_score += _score_check(_gt(quick_ratio, 1.0))
    balance_sheet_score += _score_check(_lt(debt_to_equity, 1.0))
    balance_sheet_score += _score_check(_gt(interest_coverage, 5.0))
    balance_sheet_score = min(4, balance_sheet_score)

    cashflow_score = 0
    cashflow_score += _score_check(_positive(fcf))
    cashflow_score += _score_check(_positive(ocf))
    cashflow_score += _score_check(_gt(fcf_margin, 0.10))
    cashflow_score += _score_check(_gt(cash_conversion, 0.8))
    cashflow_score = min(4, cashflow_score)

    growth_score = 0
    growth_score += _score_check(_gt(revenue_growth, 0))
    growth_score += _score_check(_gt(eps_growth, 0))
    growth_score += _score_check(_gt(earnings_stability, 0.80))
    growth_score += _score_check(_gt(dividend_growth, 0))
    growth_score = min(4, growth_score)

    risk_score = 0
    risk_score += _score_check(_lt(volatility, 0.03))
    risk_score += _score_check(_gt(sharpe, 0.5))
    risk_score += _score_check(beta is None or _lt(beta, 1.5))
    risk_score = min(3, risk_score)

    competitive_score = 0
    competitive_score += _score_check(_is_valid_number(moat_score) and moat_score >= 3)
    competitive_score += _score_check(_is_valid_number(moat_score) and moat_score >= 4)
    competitive_score = min(2, competitive_score)

    dcf_value = _get(valuation_models, "DCF", "Per_Share_Value")
    total_score = (
        valuation_score
        + profitability_score
        + balance_sheet_score
        + cashflow_score
        + growth_score
        + risk_score
        + competitive_score
    )

    framework = {
        "Valuation": {
            "PE": pe,
            "PB": pb,
            "PS": ps,
            "Earnings_Yield": earnings_yield,
            "FCF_Yield": fcf_yield,
            "DCF_Per_Share_Value": dcf_value,
            "Score": valuation_score,
        },
        "Profitability": {
            "ROE": roe,
            "ROIC": roic,
            "ROA": roa,
            "Gross_Margin": gross_margin,
            "Operating_Margin": operating_margin,
            "Net_Margin": net_margin,
            "Score": profitability_score,
        },
        "Financial_Health": {
            "Current_Ratio": current_ratio,
            "Quick_Ratio": quick_ratio,
            "Debt_to_Equity": debt_to_equity,
            "Interest_Coverage": interest_coverage,
            "Score": balance_sheet_score,
        },
        "Cash_Flow": {
            "FCF": fcf,
            "OCF": ocf,
            "FCF_Margin": fcf_margin,
            "Cash_Conversion_Ratio": cash_conversion,
            "Score": cashflow_score,
        },
        "Growth": {
            "Revenue_Growth": revenue_growth,
            "EPS_Growth": eps_growth,
            "Earnings_Stability": earnings_stability,
            "Dividend_Growth_Rate": dividend_growth,
            "Score": growth_score,
        },
        "Risk": {
            "Standard_Deviation": volatility,
            "Sharpe_Ratio": sharpe,
            "Beta": beta,
            "Score": risk_score,
        },
        "Competitive": {
            "Moat_Score": moat_score,
            "Score": competitive_score,
        },
        "Overall_Score": total_score,
    }

    return framework


def red_flags_assessment(metrics: Dict[str, Any]) -> Dict[str, Any]:
    valuation = metrics.get("valuation", {}) or {}
    profitability = metrics.get("profitability", {}) or {}
    financial_health = metrics.get("financial_health", {}) or {}
    cashflow = metrics.get("cashflow", {}) or {}
    growth = metrics.get("growth", {}) or {}
    risk = metrics.get("risk", {}) or {}
    competitive = metrics.get("competitive", {}) or {}

    flags = []

    pe = valuation.get("PE")
    pb = valuation.get("PB")
    ps = valuation.get("PS")

    current_ratio = financial_health.get("Current_Ratio")
    quick_ratio = financial_health.get("Quick_Ratio")
    debt_to_equity = financial_health.get("Debt_to_Equity")
    interest_coverage = financial_health.get("Interest_Coverage")

    fcf = cashflow.get("FCF")
    ocf = cashflow.get("OCF")

    roe = profitability.get("ROE")
    roic = profitability.get("ROIC")
    net_margin = profitability.get("Net_Margin")

    revenue_growth = growth.get("Revenue_Growth")
    eps_growth = growth.get("EPS_Growth")

    volatility = risk.get("Standard Deviation")
    sharpe = risk.get("Sharpe Ratio")
    beta = risk.get("Beta")

    moat_score = _get(metrics, "competitive", "moat", "moat_score")

    if _is_valid_number(debt_to_equity) and debt_to_equity > 1:
        flags.append({
            "flag": "High Debt",
            "severity": "Medium",
            "value": debt_to_equity,
            "reason": "Debt-to-equity is above 1."
        })

    if _is_valid_number(current_ratio) and current_ratio < 1:
        flags.append({
            "flag": "Liquidity Risk",
            "severity": "High",
            "value": current_ratio,
            "reason": "Current ratio is below 1."
        })

    if _is_valid_number(quick_ratio) and quick_ratio < 1:
        flags.append({
            "flag": "Tight Short-Term Liquidity",
            "severity": "Medium",
            "value": quick_ratio,
            "reason": "Quick ratio is below 1."
        })

    if fcf is not None and fcf <= 0:
        flags.append({
            "flag": "Negative Free Cash Flow",
            "severity": "High",
            "value": fcf,
            "reason": "Free cash flow is not positive."
        })

    if ocf is not None and ocf <= 0:
        flags.append({
            "flag": "Negative Operating Cash Flow",
            "severity": "High",
            "value": ocf,
            "reason": "Operating cash flow is not positive."
        })

    if _is_valid_number(roe) and roe < 0.10:
        flags.append({
            "flag": "Weak Return on Equity",
            "severity": "Medium",
            "value": roe,
            "reason": "ROE is below 10%."
        })

    if _is_valid_number(roic) and roic < 0.08:
        flags.append({
            "flag": "Weak Return on Invested Capital",
            "severity": "Medium",
            "value": roic,
            "reason": "ROIC is below 8%."
        })

    if _is_valid_number(net_margin) and net_margin < 0.05:
        flags.append({
            "flag": "Low Net Margin",
            "severity": "Medium",
            "value": net_margin,
            "reason": "Net margin is below 5%."
        })

    if _is_valid_number(pe) and pe > 35:
        flags.append({
            "flag": "Rich Valuation",
            "severity": "Medium",
            "value": pe,
            "reason": "PE is elevated."
        })

    if _is_valid_number(pb) and pb > 10:
        flags.append({
            "flag": "Rich Price-to-Book",
            "severity": "Medium",
            "value": pb,
            "reason": "PB is elevated."
        })

    if _is_valid_number(ps) and ps > 8:
        flags.append({
            "flag": "Rich Price-to-Sales",
            "severity": "Medium",
            "value": ps,
            "reason": "PS is elevated."
        })

    if _is_valid_number(interest_coverage) and interest_coverage < 3:
        flags.append({
            "flag": "Low Interest Coverage",
            "severity": "High",
            "value": interest_coverage,
            "reason": "Interest coverage is below 3."
        })

    if _is_valid_number(revenue_growth) and _is_valid_number(eps_growth) and revenue_growth <= 0 and eps_growth <= 0:
        flags.append({
            "flag": "Weak Growth",
            "severity": "Medium",
            "value": {"revenue_growth": revenue_growth, "eps_growth": eps_growth},
            "reason": "Both revenue and EPS growth are non-positive."
        })

    if _is_valid_number(volatility) and volatility > 0.03:
        flags.append({
            "flag": "High Volatility",
            "severity": "Medium",
            "value": volatility,
            "reason": "Volatility is elevated."
        })

    if _is_valid_number(sharpe) and sharpe < 0:
        flags.append({
            "flag": "Negative Risk-Adjusted Return",
            "severity": "High",
            "value": sharpe,
            "reason": "Sharpe ratio is negative."
        })

    if _is_valid_number(beta) and beta > 1.5:
        flags.append({
            "flag": "High Market Sensitivity",
            "severity": "Medium",
            "value": beta,
            "reason": "Beta is above 1.5."
        })

    if _is_valid_number(moat_score) and moat_score < 2:
        flags.append({
            "flag": "Weak Competitive Moat",
            "severity": "Medium",
            "value": moat_score,
            "reason": "Moat score is weak."
        })

    critical_count = sum(1 for f in flags if f["severity"] == "High")
    medium_count = sum(1 for f in flags if f["severity"] == "Medium")

    if critical_count >= 2:
        risk_level = "High"
    elif critical_count == 1 or medium_count >= 4:
        risk_level = "Moderate"
    else:
        risk_level = "Low"

    return {
        "flags": flags,
        "critical_count": critical_count,
        "medium_count": medium_count,
        "risk_level": risk_level,
    }


def investment_signal(metrics: Dict[str, Any]) -> Dict[str, Any]:
    score = 0
    reasons: List[str] = []

    pe = _get(metrics, "valuation", "PE")
    roe = _get(metrics, "profitability", "ROE")
    growth = _get(metrics, "growth", "Revenue_Growth")
    fcf = _get(metrics, "cashflow", "FCF")
    volatility = _get(metrics, "risk", "Standard Deviation")
    moat = _get(metrics, "competitive", "moat", "moat_score")
    debt_to_equity = _get(metrics, "financial_health", "Debt_to_Equity")
    current_ratio = _get(metrics, "financial_health", "Current_Ratio")

    if _lt(pe, 25):
        score += 1
        reasons.append("Reasonable valuation")

    if _gt(roe, 0.15):
        score += 1
        reasons.append("Strong profitability")

    if _gt(growth, 0):
        score += 1
        reasons.append("Positive growth")

    if _positive(fcf):
        score += 1
        reasons.append("Positive free cash flow")

    if _lt(volatility, 0.02):
        score += 1
        reasons.append("Low volatility")

    if _is_valid_number(moat) and moat >= 2:
        score += 1
        reasons.append("Strong competitive moat")

    if _is_valid_number(debt_to_equity) and debt_to_equity < 1:
        score += 1
        reasons.append("Manageable leverage")

    if _is_valid_number(current_ratio) and current_ratio >= 1:
        score += 1
        reasons.append("Acceptable liquidity")

    red_flags = red_flags_assessment(metrics)
    penalty = red_flags["critical_count"] * 2 + red_flags["medium_count"]

    final_score = max(0, score - penalty)

    if final_score >= 6:
        signal = "STRONG BUY"
    elif final_score >= 4:
        signal = "BUY"
    elif final_score >= 2:
        signal = "HOLD"
    else:
        signal = "SELL"

    return {
        "score": final_score,
        "raw_score": score,
        "signal": signal,
        "reasons": reasons,
    }


def integrated_analysis(metrics: Dict[str, Any]) -> Dict[str, Any]:
    holistic = holistic_valuation_framework(metrics)
    red_flags = red_flags_assessment(metrics)
    signal_block = investment_signal(metrics)

    return {
        "Holistic Valuation Framework": holistic,
        "Red Flags Assessment": red_flags,
        "score": signal_block["score"],
        "raw_score": signal_block["raw_score"],
        "signal": signal_block["signal"],
        "reasons": signal_block["reasons"],
    }