def safe_gt(value, threshold):
    return value is not None and value > threshold

def safe_lt(value, threshold):
    return value is not None and value < threshold


def buffett_criteria(metrics):
    roe = metrics["profitability"].get("ROE")
    debt = metrics["financial_health"].get("Debt_to_Equity")
    growth = metrics["growth"].get("EPS_Growth")

    return {
        "ROE > 15%": safe_gt(roe, 0.15),
        "Debt Low": safe_lt(debt, 0.5),
        "Consistent Earnings": safe_gt(growth, 0),
    }


def quality_score(metrics):
    score = 0

    roe = metrics["profitability"].get("ROE")
    pe = metrics["valuation"].get("PE")
    debt = metrics["financial_health"].get("Debt_to_Equity")

    if safe_gt(roe, 0.15):
        score += 1

    if safe_lt(pe, 25):
        score += 1

    if safe_lt(debt, 0.5):
        score += 1

    return score


def screening_framework(metrics):
    return {
        "buffett": buffett_criteria(metrics),
        "quality_score": quality_score(metrics)
    }