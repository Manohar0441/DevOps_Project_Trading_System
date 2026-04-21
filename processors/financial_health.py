from utils.financials import (
    CASH_ONLY_KEYS,
    CURRENT_ASSETS_KEYS,
    CURRENT_LIABILITIES_KEYS,
    EQUITY_KEYS,
    INVENTORY_KEYS,
    OPERATING_CASH_FLOW_KEYS,
    OPERATING_INCOME_KEYS,
    RECEIVABLES_KEYS,
    SHORT_TERM_INVESTMENTS_KEYS,
    TOTAL_ASSETS_KEYS,
    balance_value,
    cashflow_value,
    current_debt_value,
    income_value,
    interest_expense_value,
    interest_paid_value,
    is_missing,
    normalize_output,
    safe_div,
    total_debt_value,
)


def _quick_assets(data, current_assets, inventory):
    if not is_missing(current_assets):
        return current_assets - (0 if is_missing(inventory) else inventory)

    cash_only = balance_value(data, CASH_ONLY_KEYS)
    short_term_investments = balance_value(data, SHORT_TERM_INVESTMENTS_KEYS)
    receivables = balance_value(data, RECEIVABLES_KEYS)

    if all(is_missing(value) for value in [cash_only, short_term_investments, receivables]):
        return None

    return (
        (0 if is_missing(cash_only) else cash_only)
        + (0 if is_missing(short_term_investments) else short_term_investments)
        + (0 if is_missing(receivables) else receivables)
    )


def compute_financial_health(data):
    current_assets = balance_value(data, CURRENT_ASSETS_KEYS)
    current_liabilities = balance_value(data, CURRENT_LIABILITIES_KEYS)
    inventory = balance_value(data, INVENTORY_KEYS)
    total_assets = balance_value(data, TOTAL_ASSETS_KEYS)
    equity = balance_value(data, EQUITY_KEYS)
    total_debt = total_debt_value(data)
    current_debt = current_debt_value(data)

    quick_assets = _quick_assets(data, current_assets, inventory)
    operating_cash_flow = cashflow_value(data, OPERATING_CASH_FLOW_KEYS)
    operating_income = income_value(data, OPERATING_INCOME_KEYS)
    interest_expense = interest_expense_value(data)
    interest_paid = interest_paid_value(data)

    debt_capital_base = None
    if not is_missing(total_debt) or not is_missing(equity):
        debt_capital_base = (0 if is_missing(total_debt) else total_debt) + (
            0 if is_missing(equity) else equity
        )

    debt_service_interest = interest_paid if not is_missing(interest_paid) else interest_expense
    debt_service = None
    if not is_missing(current_debt) or not is_missing(debt_service_interest):
        debt_service = (0 if is_missing(current_debt) else current_debt) + (
            0 if is_missing(debt_service_interest) else debt_service_interest
        )

    metrics = {
        "Current_Ratio": safe_div(current_assets, current_liabilities),
        "Quick_Ratio": safe_div(quick_assets, current_liabilities),
        "Operating_Cash_Flow_Ratio": safe_div(operating_cash_flow, current_liabilities),
        "Debt_to_Equity": safe_div(total_debt, equity),
        "Debt_to_Capital": safe_div(total_debt, debt_capital_base),
        "Debt_to_Assets": safe_div(total_debt, total_assets),
        "Interest_Coverage": safe_div(operating_income, interest_expense),
        "Debt_Service_Coverage": safe_div(operating_cash_flow, debt_service),
    }

    return {key: normalize_output(value) for key, value in metrics.items()}
