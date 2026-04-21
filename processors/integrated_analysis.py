import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Utility helpers
# ─────────────────────────────────────────────

def _get(metrics: Dict[str, Any], *path: str) -> Any:
    """Safe nested getter.  Returns None if any level is missing."""
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


# ─────────────────────────────────────────────
# Quality tier
# ─────────────────────────────────────────────

def _quality_tier(metrics: Dict[str, Any]) -> str:
    """Classify the company as 'high', 'medium', or 'low' quality.

    Quality tier drives context-aware thresholds throughout the framework.
    High-quality compounders (Apple, MSFT, etc.) legitimately trade at premium
    multiples — flagging that as a red flag produces SELL signals for
    structurally strong businesses.

    Criteria
    --------
    HIGH  : ROE > 20 %, FCF positive, net margin > 15 %, moat >= 3
    MEDIUM: ROE > 10 %, FCF positive, net margin > 5 %
    LOW   : everything else
    """
    roe = _get(metrics, "profitability", "ROE")
    net_margin = _get(metrics, "profitability", "Net_Margin")
    fcf = _get(metrics, "cashflow", "FCF")
    moat = _get(metrics, "competitive", "moat", "moat_score")
    ocf = _get(metrics, "cashflow", "OCF")

    fcf_ok = _positive(fcf) or _positive(ocf)  # either cash flow measure suffices

    if (
        _gt(roe, 0.20)
        and fcf_ok
        and _gt(net_margin, 0.15)
        and (_is_valid_number(moat) and moat >= 3 or moat is None)
    ):
        return "high"

    if _gt(roe, 0.10) and fcf_ok and _gt(net_margin, 0.05):
        return "medium"

    return "low"


# ─────────────────────────────────────────────
# Holistic valuation framework
# ─────────────────────────────────────────────

def holistic_valuation_framework(metrics: Dict[str, Any]) -> Dict[str, Any]:
    tier = _quality_tier(metrics)

    valuation = metrics.get("valuation", {}) or {}
    profitability = metrics.get("profitability", {}) or {}
    financial_health = metrics.get("financial_health", {}) or {}
    cashflow = metrics.get("cashflow", {}) or {}
    growth = metrics.get("growth", {}) or {}
    risk = metrics.get("risk", {}) or {}
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

    volatility = risk.get("Standard_Deviation") or risk.get("Standard Deviation")
    sharpe = risk.get("Sharpe_Ratio") or risk.get("Sharpe Ratio")
    beta = risk.get("Beta")

    moat_score = _get(metrics, "competitive", "moat", "moat_score")

    # ── Valuation score ───────────────────────────────────────────────────────
    # For high-quality companies, premium multiples are expected.  Use looser
    # thresholds (PE < 40, PB < 20, PS < 15) so Apple-type companies don't
    # automatically score 0 on valuation.  Earnings / FCF yield checks remain
    # the same — they are yield-based and already normalise for quality.
    if tier == "high":
        pe_threshold, pb_threshold, ps_threshold = 40, 20, 15
    elif tier == "medium":
        pe_threshold, pb_threshold, ps_threshold = 30, 8, 10
    else:
        pe_threshold, pb_threshold, ps_threshold = 25, 5, 8

    valuation_score = 0
    valuation_score += _score_check(_lt(pe, pe_threshold) or pe is None)
    valuation_score += _score_check(_lt(pb, pb_threshold) or pb is None)
    valuation_score += _score_check(_lt(ps, ps_threshold) or ps is None)
    valuation_score += _score_check(_gt(earnings_yield, 0.03))   # 3 % yield floor
    valuation_score += _score_check(_gt(fcf_yield, 0.02))        # 2 % FCF yield floor
    valuation_score = min(5, valuation_score)

    # ── Profitability score ───────────────────────────────────────────────────
    profitability_score = 0
    profitability_score += _score_check(_gt(roe, 0.15))
    profitability_score += _score_check(_gt(roic, 0.10))
    profitability_score += _score_check(_gt(roa, 0.05))
    profitability_score += _score_check(_gt(gross_margin, 0.30))
    profitability_score += _score_check(_gt(operating_margin, 0.15))
    profitability_score += _score_check(_gt(net_margin, 0.10))
    profitability_score = min(5, profitability_score)

    # ── Balance sheet score ───────────────────────────────────────────────────
    # current_ratio < 1 is structurally normal for capital-return companies
    # (Apple, MSFT) — check FCF as the real liquidity signal instead.
    balance_sheet_score = 0
    if tier == "high":
        # Strong FCF is the liquidity signal; current ratio is less relevant
        balance_sheet_score += _score_check(_positive(fcf) or _gt(current_ratio, 1.0))
    else:
        balance_sheet_score += _score_check(_gt(current_ratio, 1.2))

    balance_sheet_score += _score_check(_gt(quick_ratio, 1.0) or (tier == "high" and _positive(fcf)))
    balance_sheet_score += _score_check(_lt(debt_to_equity, 1.0) or tier == "high")
    balance_sheet_score += _score_check(_gt(interest_coverage, 5.0))
    balance_sheet_score = min(4, balance_sheet_score)

    # ── Cash flow score ───────────────────────────────────────────────────────
    cashflow_score = 0
    cashflow_score += _score_check(_positive(fcf))
    cashflow_score += _score_check(_positive(ocf))
    cashflow_score += _score_check(_gt(fcf_margin, 0.10))
    cashflow_score += _score_check(_gt(cash_conversion, 0.8))
    cashflow_score = min(4, cashflow_score)

    # ── Growth score ──────────────────────────────────────────────────────────
    growth_score = 0
    growth_score += _score_check(_gt(revenue_growth, 0))
    growth_score += _score_check(_gt(eps_growth, 0))
    growth_score += _score_check(_gt(earnings_stability, 0.75))
    growth_score += _score_check(_gt(dividend_growth, 0))
    growth_score = min(4, growth_score)

    # ── Risk score ────────────────────────────────────────────────────────────
    risk_score = 0
    risk_score += _score_check(_lt(volatility, 0.025))
    risk_score += _score_check(_gt(sharpe, 0.5))
    risk_score += _score_check(beta is None or _lt(beta, 1.5))
    risk_score = min(3, risk_score)

    # ── Competitive score ─────────────────────────────────────────────────────
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

    return {
        "Quality_Tier": tier,
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


# ─────────────────────────────────────────────
# Red flags assessment
# ─────────────────────────────────────────────

def red_flags_assessment(metrics: Dict[str, Any]) -> Dict[str, Any]:
    tier = _quality_tier(metrics)

    valuation = metrics.get("valuation", {}) or {}
    profitability = metrics.get("profitability", {}) or {}
    financial_health = metrics.get("financial_health", {}) or {}
    cashflow = metrics.get("cashflow", {}) or {}
    growth = metrics.get("growth", {}) or {}
    risk = metrics.get("risk", {}) or {}

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

    volatility = risk.get("Standard_Deviation") or risk.get("Standard Deviation")
    sharpe = risk.get("Sharpe_Ratio") or risk.get("Sharpe Ratio")
    beta = risk.get("Beta")

    moat_score = _get(metrics, "competitive", "moat", "moat_score")

    # ── Debt ──────────────────────────────────────────────────────────────────
    if _is_valid_number(debt_to_equity) and debt_to_equity > 1:
        # High-quality companies intentionally lever up for buybacks — only flag
        # if interest coverage is also weak (means debt is a genuine risk).
        if tier != "high" or (
            _is_valid_number(interest_coverage) and interest_coverage < 5
        ):
            flags.append({
                "flag": "High Debt",
                "severity": "Medium",
                "value": debt_to_equity,
                "reason": "Debt-to-equity above 1.",
            })

    # ── Liquidity ─────────────────────────────────────────────────────────────
    # current_ratio < 1 is structurally normal for capital-return giants that
    # generate abundant OCF.  Only flag it when OCF is also weak.
    if _is_valid_number(current_ratio) and current_ratio < 1:
        if not _positive(ocf):
            flags.append({
                "flag": "Liquidity Risk",
                "severity": "High",
                "value": current_ratio,
                "reason": "Current ratio below 1 and operating cash flow is not positive.",
            })

    if _is_valid_number(quick_ratio) and quick_ratio < 1:
        if tier == "low":
            flags.append({
                "flag": "Tight Short-Term Liquidity",
                "severity": "Medium",
                "value": quick_ratio,
                "reason": "Quick ratio below 1.",
            })

    # ── Cash flow ─────────────────────────────────────────────────────────────
    if fcf is not None and fcf <= 0:
        flags.append({
            "flag": "Negative Free Cash Flow",
            "severity": "High",
            "value": fcf,
            "reason": "Free cash flow is not positive.",
        })

    if ocf is not None and ocf <= 0:
        flags.append({
            "flag": "Negative Operating Cash Flow",
            "severity": "High",
            "value": ocf,
            "reason": "Operating cash flow is not positive.",
        })

    # ── Profitability ─────────────────────────────────────────────────────────
    if _is_valid_number(roe) and roe < 0.10:
        flags.append({
            "flag": "Weak Return on Equity",
            "severity": "Medium",
            "value": roe,
            "reason": "ROE below 10 %.",
        })

    if _is_valid_number(roic) and roic < 0.08:
        flags.append({
            "flag": "Weak Return on Invested Capital",
            "severity": "Medium",
            "value": roic,
            "reason": "ROIC below 8 %.",
        })

    if _is_valid_number(net_margin) and net_margin < 0.05:
        flags.append({
            "flag": "Low Net Margin",
            "severity": "Medium",
            "value": net_margin,
            "reason": "Net margin below 5 %.",
        })

    # ── Valuation — context-aware thresholds ─────────────────────────────────
    # High-quality companies command premium multiples by design.  Flagging
    # Apple for a PE of 30 or PB of 45 would always produce a SELL signal for
    # every strong brand / tech company, which is financially incorrect.
    if tier == "high":
        pe_warn, pb_warn, ps_warn = 60, 60, 25
    elif tier == "medium":
        pe_warn, pb_warn, ps_warn = 40, 15, 12
    else:
        pe_warn, pb_warn, ps_warn = 30, 8, 8

    if _is_valid_number(pe) and pe > 0 and pe > pe_warn:
        flags.append({
            "flag": "Rich Valuation",
            "severity": "Medium",
            "value": pe,
            "reason": f"PE ({pe:.1f}) is above the {tier}-quality threshold of {pe_warn}.",
        })

    if _is_valid_number(pb) and pb > 0 and pb > pb_warn:
        flags.append({
            "flag": "Rich Price-to-Book",
            "severity": "Low" if tier == "high" else "Medium",
            "value": pb,
            "reason": f"PB ({pb:.1f}) is elevated.",
        })

    if _is_valid_number(ps) and ps > 0 and ps > ps_warn:
        flags.append({
            "flag": "Rich Price-to-Sales",
            "severity": "Low" if tier == "high" else "Medium",
            "value": ps,
            "reason": f"PS ({ps:.1f}) is elevated.",
        })

    # ── Interest coverage ─────────────────────────────────────────────────────
    if _is_valid_number(interest_coverage) and interest_coverage < 3:
        flags.append({
            "flag": "Low Interest Coverage",
            "severity": "High",
            "value": interest_coverage,
            "reason": "Interest coverage below 3.",
        })

    # ── Growth ────────────────────────────────────────────────────────────────
    if (
        _is_valid_number(revenue_growth)
        and _is_valid_number(eps_growth)
        and revenue_growth <= 0
        and eps_growth <= 0
    ):
        flags.append({
            "flag": "Weak Growth",
            "severity": "Medium",
            "value": {"revenue_growth": revenue_growth, "eps_growth": eps_growth},
            "reason": "Both revenue and EPS growth are non-positive.",
        })

    # ── Risk ──────────────────────────────────────────────────────────────────
    if _is_valid_number(volatility) and volatility > 0.03:
        flags.append({
            "flag": "High Volatility",
            "severity": "Medium",
            "value": volatility,
            "reason": "Daily volatility is elevated.",
        })

    if _is_valid_number(sharpe) and sharpe < 0:
        flags.append({
            "flag": "Negative Risk-Adjusted Return",
            "severity": "High",
            "value": sharpe,
            "reason": "Sharpe ratio is negative.",
        })

    if _is_valid_number(beta) and beta > 1.5:
        flags.append({
            "flag": "High Market Sensitivity",
            "severity": "Medium",
            "value": beta,
            "reason": "Beta above 1.5.",
        })

    # ── Moat ──────────────────────────────────────────────────────────────────
    if _is_valid_number(moat_score) and moat_score < 2:
        flags.append({
            "flag": "Weak Competitive Moat",
            "severity": "Medium",
            "value": moat_score,
            "reason": "Moat score is weak.",
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
        "quality_tier": tier,
        "flags": flags,
        "critical_count": critical_count,
        "medium_count": medium_count,
        "risk_level": risk_level,
    }


# ─────────────────────────────────────────────
# Investment signal
# ─────────────────────────────────────────────

def investment_signal(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a BUY / HOLD / SELL signal with context-aware scoring.

    Key changes vs old version
    --------------------------
    * Valuation thresholds scale with quality tier so quality-premium companies
      (Apple, MSFT) are not penalised for high PE / PB.
    * Penalty is applied only for HIGH-severity flags; medium flags add a softer
      fractional penalty (0.5 per flag) so a cluster of minor issues still
      moves the needle without immediately generating a SELL.
    * Signal thresholds adjusted for the expanded penalty scale.
    """
    tier = _quality_tier(metrics)

    score = 0
    reasons: List[str] = []

    pe = _get(metrics, "valuation", "PE")
    roe = _get(metrics, "profitability", "ROE")
    growth = _get(metrics, "growth", "Revenue_Growth")
    fcf = _get(metrics, "cashflow", "FCF")
    ocf = _get(metrics, "cashflow", "OCF")
    volatility = _get(metrics, "risk", "Standard_Deviation") or _get(metrics, "risk", "Standard Deviation")
    moat = _get(metrics, "competitive", "moat", "moat_score")
    debt_to_equity = _get(metrics, "financial_health", "Debt_to_Equity")
    current_ratio = _get(metrics, "financial_health", "Current_Ratio")

    # Tier-adjusted PE threshold for "reasonable valuation" check
    pe_ok_threshold = 40 if tier == "high" else 30 if tier == "medium" else 25

    if _lt(pe, pe_ok_threshold):
        score += 1
        reasons.append("Reasonable valuation")

    if _gt(roe, 0.15):
        score += 1
        reasons.append("Strong profitability")

    if _gt(growth, 0):
        score += 1
        reasons.append("Positive revenue growth")

    if _positive(fcf) or _positive(ocf):
        score += 1
        reasons.append("Positive free / operating cash flow")

    if _lt(volatility, 0.025):
        score += 1
        reasons.append("Low volatility")

    if _is_valid_number(moat) and moat >= 2:
        score += 1
        reasons.append("Competitive moat present")

    # Debt check: for quality companies, high D/E is acceptable if coverage is fine
    interest_coverage = _get(metrics, "financial_health", "Interest_Coverage")
    debt_ok = (
        (_is_valid_number(debt_to_equity) and debt_to_equity < 1)
        or (tier == "high" and _gt(interest_coverage, 5))
    )
    if debt_ok:
        score += 1
        reasons.append("Manageable leverage")

    # Liquidity check: for quality companies, strong OCF overrides low current ratio
    liquidity_ok = (
        (_is_valid_number(current_ratio) and current_ratio >= 1)
        or (tier in ("high", "medium") and _positive(ocf))
    )
    if liquidity_ok:
        score += 1
        reasons.append("Acceptable liquidity")

    # ── Penalty ───────────────────────────────────────────────────────────────
    red_flags = red_flags_assessment(metrics)
    # High-severity flags: -2 each (genuine business risk)
    # Medium-severity flags: -0.5 each (concern, not crisis)
    # Low-severity flags: no penalty
    penalty = (
        red_flags["critical_count"] * 2
        + sum(0.5 for f in red_flags["flags"] if f["severity"] == "Medium")
    )

    final_score = max(0.0, score - penalty)

    # Signal thresholds (max raw score = 8)
    if final_score >= 6:
        signal = "STRONG BUY"
    elif final_score >= 4:
        signal = "BUY"
    elif final_score >= 2:
        signal = "HOLD"
    else:
        signal = "SELL"

    return {
        "quality_tier": tier,
        "score": round(final_score, 2),
        "raw_score": score,
        "signal": signal,
        "reasons": reasons,
        "red_flag_summary": {
            "critical": red_flags["critical_count"],
            "medium": red_flags["medium_count"],
            "risk_level": red_flags["risk_level"],
        },
    }


# ─────────────────────────────────────────────
# Composite entry point
# ─────────────────────────────────────────────

def integrated_analysis(metrics: Dict[str, Any]) -> Dict[str, Any]:
    holistic = holistic_valuation_framework(metrics)
    red_flags = red_flags_assessment(metrics)
    signal_block = investment_signal(metrics)

    return {
        "Holistic_Valuation_Framework": holistic,
        "Red_Flags_Assessment": red_flags,
        "score": signal_block["score"],
        "raw_score": signal_block["raw_score"],
        "signal": signal_block["signal"],
        "quality_tier": signal_block["quality_tier"],
        "reasons": signal_block["reasons"],
        "red_flag_summary": signal_block["red_flag_summary"],
    }