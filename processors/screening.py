def safe_gt(value, threshold):
    return value is not None and value > threshold


def safe_lt(value, threshold):
    return value is not None and value < threshold


def safe_between(value, low, high):
    return value is not None and low <= value <= high


# -------------------------------
# Buffett Criteria
# -------------------------------
def buffett_criteria(metrics):
    roe = metrics["profitability"].get("ROE")
    debt = metrics["financial_health"].get("Debt_to_Equity")
    growth = metrics["growth"].get("EPS_Growth")

    return {
        "ROE > 15%": safe_gt(roe, 0.15),
        "Low Debt (<0.5)": safe_lt(debt, 0.5),
        "Positive EPS Growth": safe_gt(growth, 0)
    }


# -------------------------------
# Quality Screening
# -------------------------------
def quality_screening(metrics):
    score = 0
    checks = {}

    roe = metrics["profitability"].get("ROE")
    pe = metrics["valuation"].get("PE")
    debt = metrics["financial_health"].get("Debt_to_Equity")
    fcf = metrics["cashflow"].get("Free_Cash_Flow")

    checks["High ROE"] = safe_gt(roe, 0.15)
    checks["Reasonable PE"] = safe_lt(pe, 25)
    checks["Low Debt"] = safe_lt(debt, 0.5)
    checks["Positive FCF"] = safe_gt(fcf, 0)

    score = sum(v for v in checks.values() if v)

    return {"Score": score, "Checks": checks}


# -------------------------------
# 8-Point Checklist
# -------------------------------
def eight_point_checklist(metrics):
    return {
        "ROE > 15%": safe_gt(metrics["profitability"].get("ROE"), 0.15),
        "ROA > 7%": safe_gt(metrics["profitability"].get("ROA"), 0.07),
        "Debt/Equity < 0.5": safe_lt(metrics["financial_health"].get("Debt_to_Equity"), 0.5),
        "Current Ratio > 1.5": safe_gt(metrics["financial_health"].get("Current_Ratio"), 1.5),
        "Positive EPS Growth": safe_gt(metrics["growth"].get("EPS_Growth"), 0),
        "Revenue Growth > 5%": safe_gt(metrics["growth"].get("Revenue_Growth"), 0.05),
        "Positive FCF": safe_gt(metrics["cashflow"].get("Free_Cash_Flow"), 0),
        "PE < 25": safe_lt(metrics["valuation"].get("PE"), 25)
    }


# -------------------------------
# Growth Stock Evaluation
# -------------------------------
def growth_stock_evaluation(metrics):
    return {
        "High Revenue Growth": safe_gt(metrics["growth"].get("Revenue_Growth"), 0.15),
        "High EPS Growth": safe_gt(metrics["growth"].get("EPS_Growth"), 0.20),
        "High PE (Growth Premium)": safe_gt(metrics["valuation"].get("PE"), 25)
    }


# -------------------------------
# Value Stock Evaluation
# -------------------------------
def value_stock_evaluation(metrics):
    return {
        "Low PE": safe_lt(metrics["valuation"].get("PE"), 20),
        "Low PB": safe_lt(metrics["valuation"].get("PB"), 3),
        "High Dividend Yield": safe_gt(metrics["valuation"].get("Dividend_Yield"), 0.03)
    }


# -------------------------------
# Cyclical Stock Analysis
# -------------------------------
def cyclical_stock_analysis(metrics):
    return {
        "High Revenue Variability": metrics["growth"].get("Revenue_Growth") is not None,
        "Moderate Debt": safe_between(metrics["financial_health"].get("Debt_to_Equity"), 0.3, 1.5),
        "Economic Sensitivity (Proxy PE < 20)": safe_lt(metrics["valuation"].get("PE"), 20)
    }


# -------------------------------
# Dividend Stock Analysis
# -------------------------------
def dividend_stock_analysis(metrics):
    return {
        "Stable Dividend Yield": safe_gt(metrics["valuation"].get("Dividend_Yield"), 0.02),
        "Positive Free Cash Flow": safe_gt(metrics["cashflow"].get("Free_Cash_Flow"), 0),
        "Low Payout Risk (Debt Low)": safe_lt(metrics["financial_health"].get("Debt_to_Equity"), 0.6)
    }


# -------------------------------
# Fundamental Analysis Framework
# -------------------------------
def fundamental_analysis_framework(metrics):
    return {
        "Profitability": metrics.get("profitability"),
        "Growth": metrics.get("growth"),
        "Valuation": metrics.get("valuation"),
        "Financial Health": metrics.get("financial_health"),
        "Cash Flow": metrics.get("cashflow")
    }


# -------------------------------
# MASTER FUNCTION
# -------------------------------
def screening_framework(metrics):
    return {
        "Fundamental Analysis Framework": fundamental_analysis_framework(metrics),
        "Quality Screening": quality_screening(metrics),
        "Buffett Criteria": buffett_criteria(metrics),
        "8-Point Checklist": eight_point_checklist(metrics),
        "Growth Stock Evaluation": growth_stock_evaluation(metrics),
        "Value Stock Evaluation": value_stock_evaluation(metrics),
        "Cyclical Stock Analysis": cyclical_stock_analysis(metrics),
        "Dividend Stock Analysis": dividend_stock_analysis(metrics)
    }