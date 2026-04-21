from datetime import datetime


def _safe_get(metrics, section, key, default=None):
    try:
        return metrics.get(section, {}).get(key, default)
    except Exception:
        return default


# ---------------------------------------
# PART M: Long-Term Tracking
# ---------------------------------------
def performance_monitoring(metrics):
    return {
        "Return Metrics": {
            "Cumulative Return": _safe_get(metrics, "risk", "Cumulative Return"),
            "CAGR": _safe_get(metrics, "risk", "CAGR"),
            "Total Shareholder Return": _safe_get(metrics, "risk", "Total Shareholder Return"),
        },
        "Risk Metrics": {
            "Volatility": _safe_get(metrics, "risk", "Standard Deviation"),
            "Sharpe Ratio": _safe_get(metrics, "risk", "Sharpe Ratio"),
            "Sortino Ratio": _safe_get(metrics, "risk", "Sortino Ratio"),
        },
        "Fundamental Tracking": {
            "PE": _safe_get(metrics, "valuation", "PE"),
            "ROE": _safe_get(metrics, "profitability", "ROE"),
            "Revenue Growth": _safe_get(metrics, "growth", "Revenue_Growth"),
            "FCF": _safe_get(metrics, "cashflow", "FCF"),
        },
        "Health Indicators": {
            "Debt_to_Equity": _safe_get(metrics, "financial_health", "Debt_to_Equity"),
            "Current Ratio": _safe_get(metrics, "financial_health", "Current_Ratio"),
        },
    }


def metric_tracking_schedule():
    return {
        "Frequency": "Monthly",
        "Review Window": "Rolling 12 months",
        "Snapshot Points": [
            "End of every month",
            "Quarterly results",
            "Post earnings release",
        ],
        "Tracked Areas": [
            "Performance monitoring",
            "KPI monitoring",
            "Valuation stability",
            "Risk stability",
            "Rebalancing triggers",
        ],
    }


def kpi_monitoring(metrics):
    return {
        "Valuation KPIs": {
            "PE": _safe_get(metrics, "valuation", "PE"),
            "PB": _safe_get(metrics, "valuation", "PB"),
            "PS": _safe_get(metrics, "valuation", "PS"),
            "EV/EBITDA": _safe_get(metrics, "valuation", "EV_EBITDA"),
        },
        "Profitability KPIs": {
            "ROE": _safe_get(metrics, "profitability", "ROE"),
            "ROA": _safe_get(metrics, "profitability", "ROA"),
            "Net Margin": _safe_get(metrics, "profitability", "Net_Margin"),
            "Operating Margin": _safe_get(metrics, "profitability", "Operating_Margin"),
        },
        "Growth KPIs": {
            "Revenue Growth": _safe_get(metrics, "growth", "Revenue_Growth"),
            "EPS Growth": _safe_get(metrics, "growth", "EPS_Growth"),
            "FCF Growth": _safe_get(metrics, "growth", "FCF_Growth"),
        },
        "Financial Health KPIs": {
            "Debt_to_Equity": _safe_get(metrics, "financial_health", "Debt_to_Equity"),
            "Current Ratio": _safe_get(metrics, "financial_health", "Current_Ratio"),
            "Interest Coverage": _safe_get(metrics, "financial_health", "Interest_Coverage"),
        },
        "Risk KPIs": {
            "Volatility": _safe_get(metrics, "risk", "Standard Deviation"),
            "Sharpe Ratio": _safe_get(metrics, "risk", "Sharpe Ratio"),
            "Sortino Ratio": _safe_get(metrics, "risk", "Sortino Ratio"),
            "Beta": _safe_get(metrics, "risk", "Beta"),
        },
    }


def rebalancing_triggers(metrics):
    pe = _safe_get(metrics, "valuation", "PE")
    roe = _safe_get(metrics, "profitability", "ROE")
    fcf = _safe_get(metrics, "cashflow", "FCF")
    volatility = _safe_get(metrics, "risk", "Standard Deviation")
    debt_to_equity = _safe_get(metrics, "financial_health", "Debt_to_Equity")
    revenue_growth = _safe_get(metrics, "growth", "Revenue_Growth")
    sharpe = _safe_get(metrics, "risk", "Sharpe Ratio")

    score = 0
    triggers = []

    if pe is not None:
        if pe < 20:
            score += 1
            triggers.append("Undervalued (PE)")
        elif pe > 40:
            score -= 1
            triggers.append("Overvalued (PE)")

    if roe is not None:
        if roe > 0.15:
            score += 1
            triggers.append("Strong ROE")
        elif roe < 0.10:
            score -= 1
            triggers.append("Weak ROE")

    if fcf is not None:
        if fcf > 0:
            score += 1
            triggers.append("Positive FCF")
        else:
            score -= 1
            triggers.append("Negative FCF")

    if volatility is not None:
        if volatility < 0.03:
            score += 1
            triggers.append("Low volatility")
        elif volatility > 0.05:
            score -= 1
            triggers.append("High volatility")

    if debt_to_equity is not None:
        if debt_to_equity < 0.5:
            score += 1
            triggers.append("Low leverage")
        elif debt_to_equity > 1.5:
            score -= 1
            triggers.append("High leverage")

    if revenue_growth is not None:
        if revenue_growth > 0.10:
            score += 1
            triggers.append("Strong growth")
        elif revenue_growth < 0:
            score -= 1
            triggers.append("Declining growth")

    if sharpe is not None:
        if sharpe > 1:
            score += 1
            triggers.append("Good Sharpe")
        elif sharpe < 0:
            score -= 1
            triggers.append("Poor Sharpe")

    if score >= 4:
        decision = "ADD / ACCUMULATE"
    elif score >= 2:
        decision = "HOLD"
    elif score >= 0:
        decision = "REDUCE"
    else:
        decision = "EXIT"

    return {
        "Decision": decision,
        "Score": score,
        "Triggers": triggers,
    }


def long_term_tracking(metrics):
    return {
        "timestamp": datetime.now().isoformat(),
        "Performance Monitoring": performance_monitoring(metrics),
        "Metric Tracking Schedule": metric_tracking_schedule(),
        "KPI Monitoring": kpi_monitoring(metrics),
        "Rebalancing Triggers": rebalancing_triggers(metrics),
    }


def track_metrics(metrics):
    return long_term_tracking(metrics)

# ---------------------------------------
# Backward Compatibility
# ---------------------------------------
def track_metrics(metrics):
    return long_term_tracking(metrics)


def rebalance_signal(metrics):
    return rebalancing_triggers(metrics)