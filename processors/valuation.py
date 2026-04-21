from utils.financials import (
    CASH_KEYS,
    EQUITY_KEYS,
    NET_INCOME_KEYS,
    OPERATING_CASH_FLOW_KEYS,
    REVENUE_KEYS,
    balance_value,
    cashflow_value,
    current_free_cash_flow,
    income_value,
    is_missing,
    market_cap_value,
    normalize_output,
    normalized_free_cash_flow,
    safe_div,
    total_debt_value,
)


def compute_valuation(data):
    info = data.get("info", {}) if isinstance(data.get("info"), dict) else {}

    market_cap = market_cap_value(info)

    # TTM flows and latest balance-sheet values keep valuation internally consistent.
    net_income = income_value(data, NET_INCOME_KEYS)
    revenue = income_value(data, REVENUE_KEYS)
    equity = balance_value(data, EQUITY_KEYS)
    cash = balance_value(data, CASH_KEYS)
    total_debt = total_debt_value(data)
    operating_cash_flow = cashflow_value(data, OPERATING_CASH_FLOW_KEYS)

    if is_missing(cash):
        cash = 0
    if is_missing(total_debt):
        total_debt = 0

    current_fcf = current_free_cash_flow(data)
    normalized_fcf = normalized_free_cash_flow(data)

    enterprise_value = None
    if not is_missing(market_cap):
        enterprise_value = market_cap + total_debt - cash

    # For valuation multiples, use normalized FCF and suppress ratios when the base
    # is missing or economically non-meaningful.
    valuation_fcf = normalized_fcf
    if is_missing(valuation_fcf) or valuation_fcf <= 0:
        valuation_fcf = None

    metrics = {
        "PE": safe_div(market_cap, net_income),
        "PB": safe_div(market_cap, equity),
        "PS": safe_div(market_cap, revenue),
        "EV": enterprise_value,
        "EV_Sales": safe_div(enterprise_value, revenue),
        "P_CF": safe_div(market_cap, operating_cash_flow),
        "P_FCF": safe_div(market_cap, valuation_fcf),
        "Earnings_Yield": safe_div(net_income, market_cap),
        "FCF_Yield": safe_div(valuation_fcf, market_cap),
        "Current_FCF": current_fcf,
        "Normalized_FCF": normalized_fcf,
    }

    return {key: normalize_output(value) for key, value in metrics.items()}
