from datetime import datetime


def _safe_get(metrics, section, key):
    try:
        return metrics.get(section, {}).get(key)
    except:
        return None


# ---------------------------------------
# 1. Performance Monitoring
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
        }
    }


# ---------------------------------------
# 2. Snapshot Tracking
# ---------------------------------------
def track_metrics(metrics):
    return {
        "timestamp": datetime.now().isoformat(),
        "snapshot": {
            "PE": _safe_get(metrics, "valuation", "PE"),
            "ROE": _safe_get(metrics, "profitability", "ROE"),
            "FCF": _safe_get(metrics, "cashflow", "FCF"),
            "Revenue Growth": _safe_get(metrics, "growth", "Revenue_Growth"),
        },
        "performance": performance_monitoring(metrics)
    }


# ---------------------------------------
# 3. Rebalance Signal (Improved)
# ---------------------------------------
def rebalance_signal(metrics):
    pe = _safe_get(metrics, "valuation", "PE")
    roe = _safe_get(metrics, "profitability", "ROE")
    fcf = _safe_get(metrics, "cashflow", "FCF")
    volatility = _safe_get(metrics, "risk", "Standard Deviation")

    score = 0

    # Valuation
    if pe is not None:
        if pe < 20:
            score += 1
        elif pe > 40:
            score -= 1

    # Profitability
    if roe is not None and roe > 0.15:
        score += 1

    # Cash Flow
    if fcf is not None and fcf > 0:
        score += 1

    # Risk
    if volatility is not None and volatility < 0.03:
        score += 1
    elif volatility is not None and volatility > 0.05:
        score -= 1

    # Final Decision
    if score >= 3:
        return "ADD / ACCUMULATE"
    elif score == 2:
        return "HOLD"
    elif score == 1:
        return "REDUCE"
    else:
        return "EXIT"