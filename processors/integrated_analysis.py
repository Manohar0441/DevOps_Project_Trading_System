def investment_signal(metrics):
    score = 0
    reasons = []

    # --- Valuation ---
    pe = metrics["valuation"].get("PE")
    if pe and pe < 25:
        score += 1
        reasons.append("Reasonable valuation")

    # --- Profitability ---
    roe = metrics["profitability"].get("ROE")
    if roe and roe > 0.15:
        score += 1
        reasons.append("Strong profitability")

    # --- Growth ---
    growth = metrics["growth"].get("Revenue_Growth", 0)
    if growth and growth > 0:
        score += 1
        reasons.append("Positive growth")

    # --- Cash Flow ---
    if metrics["cashflow"].get("FCF"):
        score += 1
        reasons.append("Positive free cash flow")

    # --- Risk ---
    if metrics["risk"].get("Volatility", 1) < 0.02:
        score += 1
        reasons.append("Low volatility")

    # --- Competitive Advantage ---
    moat = metrics["competitive"]["moat"]["moat_score"]
    if moat >= 2:
        score += 1
        reasons.append("Strong competitive moat")

    # --- Final Decision ---
    if score >= 5:
        signal = "STRONG BUY"
    elif score >= 3:
        signal = "BUY"
    elif score == 2:
        signal = "HOLD"
    else:
        signal = "SELL"

    return {
        "score": score,
        "signal": signal,
        "reasons": reasons
    }


def integrated_analysis(metrics):
    return investment_signal(metrics)