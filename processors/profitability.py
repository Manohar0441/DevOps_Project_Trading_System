from utils.financials import (
    CASH_KEYS,
    COGS_KEYS,
    CURRENT_LIABILITIES_KEYS,
    EQUITY_KEYS,
    GROSS_PROFIT_KEYS,
    INVENTORY_KEYS,
    NET_INCOME_KEYS,
    OPERATING_INCOME_KEYS,
    PAYABLES_KEYS,
    PRETAX_INCOME_KEYS,
    RECEIVABLES_KEYS,
    REVENUE_KEYS,
    TAX_EXPENSE_KEYS,
    TOTAL_ASSETS_KEYS,
    average_balance_value,
    average_total_debt_value,
    _safe_gt,
    _safe_lt,
    income_value,
    is_missing,
    normalize_output,
    safe_div,
)
from processors.metric_engine import ebitda_snapshot, safe_ratio, to_float


def _effective_tax_rate(data):
    tax_expense = income_value(data, TAX_EXPENSE_KEYS)
    pretax_income = income_value(data, PRETAX_INCOME_KEYS)
    tax_rate = safe_div(tax_expense, pretax_income)

    # Extreme effective tax rates are usually one-time accounting noise and can
    # badly distort NOPAT-based ratios such as ROIC.
    if is_missing(tax_rate) or _safe_lt(tax_rate, 0) or _safe_gt(tax_rate, 0.5):
        return None

    return tax_rate


def _nopat(operating_income, tax_rate):
    if is_missing(operating_income) or is_missing(tax_rate):
        return None

    return operating_income * (1 - tax_rate)


def compute_profitability(data):
    net_income = income_value(data, NET_INCOME_KEYS)
    revenue = income_value(data, REVENUE_KEYS)
    gross_profit = income_value(data, GROSS_PROFIT_KEYS)
    operating_income = income_value(data, OPERATING_INCOME_KEYS)
    ebitda_meta = ebitda_snapshot(data)
    ebitda = to_float(ebitda_meta["value"])
    cogs = income_value(data, COGS_KEYS)

    average_equity = average_balance_value(data, EQUITY_KEYS)
    average_assets = average_balance_value(data, TOTAL_ASSETS_KEYS)
    average_inventory = average_balance_value(data, INVENTORY_KEYS)
    average_receivables = average_balance_value(data, RECEIVABLES_KEYS)
    average_payables = average_balance_value(data, PAYABLES_KEYS)
    average_cash = average_balance_value(data, CASH_KEYS)
    average_current_liabilities = average_balance_value(data, CURRENT_LIABILITIES_KEYS)
    average_debt = average_total_debt_value(data)

    invested_capital = None
    if not is_missing(average_equity):
        invested_capital = average_equity + (0 if is_missing(average_debt) else average_debt) - (
            0 if is_missing(average_cash) else average_cash
        )

    capital_employed = None
    if not is_missing(average_assets) and not is_missing(average_current_liabilities):
        capital_employed = average_assets - average_current_liabilities

    tax_rate = _effective_tax_rate(data)
    nopat = _nopat(operating_income, tax_rate)

  
    receivables_turnover = safe_div(revenue, average_receivables)
    payables_turnover = safe_div(cogs, average_payables)

    
    days_receivable = safe_div(365, receivables_turnover)
    days_payable = safe_div(365, payables_turnover)

    metrics = {
        "ROE": safe_div(net_income, average_equity),
        "ROIC": safe_div(nopat, invested_capital),
        "ROA": safe_div(net_income, average_assets),
        "ROCE": safe_div(operating_income, capital_employed),
        "Gross_Margin": safe_div(gross_profit, revenue),
        "Operating_Margin": safe_div(operating_income, revenue),
        "Net_Margin": safe_div(net_income, revenue),
        "EBITDA_Margin": safe_ratio(ebitda, revenue),
        "Asset_Turnover": safe_div(revenue, average_assets),
        "Net_Income": net_income,
        "Receivables_Turnover": receivables_turnover,
        "_meta": {
            "ebitda_source": ebitda_meta["source"],
            "ebitda_basis": ebitda_meta["basis"],
            "ebitda_as_of": ebitda_meta["as_of"],
            "ebitda_value": ebitda,
            "operating_income_for_ebitda": ebitda_meta["operating_income"],
            "margin_period_basis": "TTM",
        },
    }

   

    return {key: normalize_output(value) for key, value in metrics.items()}
