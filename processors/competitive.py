def competitive_moat_score(metrics, raw):
    score = 0
    reasons = []

    # --- Sustained ROIC proxy (using ROE for now) ---
    roe = metrics["profitability"].get("ROE", 0)
    if roe and roe > 0.15:
        score += 1
        reasons.append("High returns on capital")

    # --- Stable margins ---
    margin = metrics["profitability"].get("Net_Margin", 0)
    if margin and margin > 0.15:
        score += 1
        reasons.append("Strong profit margins")

    # --- Pricing power proxy ---
    if metrics["valuation"].get("PE", 0) > 25:
        score += 1
        reasons.append("Market assigns premium valuation")

    return {
        "moat_score": score,
        "reasons": reasons
    }


def management_quality(raw):
    info = raw["info"]

    return {
        "insider_ownership": info.get("heldPercentInsiders"),
        "institutional_confidence": info.get("heldPercentInstitutions"),
        "comment": "Higher insider holding = aligned incentives"
    }


def competitive_analysis(metrics, raw):
    return {
        "moat": competitive_moat_score(metrics, raw),
        "management": management_quality(raw)
    }