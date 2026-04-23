import pandas as pd


NET_INCOME_KEYS = ["Net Income"]
REVENUE_KEYS = ["Total Revenue", "Operating Revenue"]
GROSS_PROFIT_KEYS = ["Gross Profit"]
OPERATING_INCOME_KEYS = ["Operating Income", "EBIT"]
EBITDA_KEYS = ["EBITDA"]
TAX_EXPENSE_KEYS = ["Income Tax Expense", "Tax Provision"]
PRETAX_INCOME_KEYS = ["Pretax Income", "Pre Tax Income"]
COGS_KEYS = ["Cost Of Revenue", "Cost of Revenue", "Cost Of Goods Sold"]
TOTAL_ASSETS_KEYS = ["Total Assets"]
CURRENT_ASSETS_KEYS = ["Total Current Assets", "Current Assets"]
CURRENT_LIABILITIES_KEYS = ["Total Current Liabilities", "Current Liabilities"]
EQUITY_KEYS = [
    "Total Stockholder Equity",
    "Stockholders Equity",
    "Total Equity Gross Minority Interest",
    "Common Stock Equity",
]
INVENTORY_KEYS = ["Inventory"]
RECEIVABLES_KEYS = ["Net Receivables", "Accounts Receivable", "Receivables"]
PAYABLES_KEYS = ["Accounts Payable", "Payables", "Total Payables", "Current Payables"]
CASH_KEYS = [
    "Cash Cash Equivalents And Short Term Investments",
    "Cash And Cash Equivalents",
    "Cash",
]
CASH_ONLY_KEYS = ["Cash And Cash Equivalents", "Cash"]
SHORT_TERM_INVESTMENTS_KEYS = [
    "Available For Sale Securities",
    "Other Short Term Investments",
    "Short Term Investments",
]
TOTAL_DEBT_KEYS = ["Total Debt"]
CURRENT_DEBT_KEYS = [
    "Current Debt",
    "Current Debt And Capital Lease Obligation",
    "Current Portion Of Long Term Debt",
    "Current Portion Of Long Term Debt And Capital Lease Obligation",
    "Short Long Term Debt",
    "Short Term Debt",
]
LONG_TERM_DEBT_KEYS = [
    "Long Term Debt",
    "Long Term Debt And Capital Lease Obligation",
]
OPERATING_CASH_FLOW_KEYS = [
    "Operating Cash Flow",
    "Total Cash From Operating Activities",
]
CAPEX_KEYS = ["Capital Expenditure", "Capital Expenditures"]
STOCK_BASED_COMPENSATION_KEYS = ["Stock Based Compensation"]
INTEREST_EXPENSE_KEYS = [
    "Interest Expense",
    "Interest Expense Non Operating",
    "Interest And Debt Expense",
]
INTEREST_PAID_KEYS = ["Interest Paid Supplemental Data", "Interest Paid"]
NET_BORROWING_KEYS = [
    "Net Issuance Payments Of Debt",
    "Net Long Term Debt Issuance",
    "Net Short Term Debt Issuance",
]
DEBT_ISSUED_KEYS = [
    "Issuance Of Debt",
    "Debt Issuance",
    "Long Term Debt Issuance",
    "Short Term Debt Issuance",
]
DEBT_REPAID_KEYS = [
    "Repayment Of Debt",
    "Debt Repayment",
    "Long Term Debt Payments",
    "Short Term Debt Payments",
    "Long Term Debt Reduction",
]


def is_missing(value):
    if value is None:
        return True

    try:
        return bool(pd.isna(value))
    except TypeError:
        return False


def normalize_output(value):
    if is_missing(value):
        return None

    if hasattr(value, "item"):
        try:
            return value.item()
        except (TypeError, ValueError):
            return value

    return value


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and not is_missing(value)


def _safe_gt(a, b):
    return _is_number(a) and _is_number(b) and a > b


def _safe_lt(a, b):
    return _is_number(a) and _is_number(b) and a < b


def safe_div(numerator, denominator):
    if is_missing(numerator) or is_missing(denominator) or denominator == 0:
        return None

    try:
        return numerator / denominator
    except (TypeError, ZeroDivisionError):
        return None


def ordered_frame(frame):
    if frame is None or not hasattr(frame, "empty") or frame.empty:
        return pd.DataFrame()

    try:
        return frame.sort_index(axis=1, ascending=False)
    except TypeError:
        return frame


def row_series(frame, keys):
    ordered = ordered_frame(frame)
    if ordered.empty:
        return pd.Series(dtype="float64")

    for key in keys:
        if key not in ordered.index:
            continue

        row = ordered.loc[key]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]

        return row.dropna()

    return pd.Series(dtype="float64")


def latest_value(series):
    for value in series.tolist():
        if not is_missing(value):
            return value

    return None


def trailing_sum(series, periods):
    values = [value for value in series.tolist() if not is_missing(value)]
    if len(values) < periods:
        return None

    return sum(values[:periods])


def rolling_trailing_sums(series, periods, windows):
    values = [value for value in series.tolist() if not is_missing(value)]
    if len(values) < periods:
        return []

    limit = min(windows, len(values) - periods + 1)
    return [sum(values[start:start + periods]) for start in range(limit)]


def median_recent(values, minimum_periods=2):
    cleaned = [value for value in values if not is_missing(value)]
    if len(cleaned) < minimum_periods:
        return None

    return pd.Series(cleaned, dtype="float64").median()


def mean_recent(values, minimum_periods=2):
    cleaned = [value for value in values if not is_missing(value)]
    if len(cleaned) < minimum_periods:
        return None

    return pd.Series(cleaned, dtype="float64").mean()


def point_in_time_value(quarterly_frame, annual_frame, keys):
    quarterly_value = latest_value(row_series(quarterly_frame, keys))
    if not is_missing(quarterly_value):
        return quarterly_value

    return latest_value(row_series(annual_frame, keys))


def average_point_in_time_value(
    quarterly_frame,
    annual_frame,
    keys,
    quarterly_points=5,
    annual_points=2,
):
    quarterly_values = [value for value in row_series(quarterly_frame, keys).tolist() if not is_missing(value)]
    if len(quarterly_values) >= 2:
        return mean_recent(quarterly_values[: min(quarterly_points, len(quarterly_values))])

    annual_values = [value for value in row_series(annual_frame, keys).tolist() if not is_missing(value)]
    if len(annual_values) >= 2:
        return mean_recent(annual_values[: min(annual_points, len(annual_values))])

    latest_quarterly = latest_value(row_series(quarterly_frame, keys))
    if not is_missing(latest_quarterly):
        return latest_quarterly

    return latest_value(row_series(annual_frame, keys))


def flow_value(quarterly_frame, annual_frame, keys):
    quarterly_value = trailing_sum(row_series(quarterly_frame, keys), 4)
    if not is_missing(quarterly_value):
        return quarterly_value

    return latest_value(row_series(annual_frame, keys))


def balance_value(data, keys):
    return point_in_time_value(data.get("quarterly_balance"), data.get("balance"), keys)


def average_balance_value(data, keys, quarterly_points=5, annual_points=2):
    return average_point_in_time_value(
        data.get("quarterly_balance"),
        data.get("balance"),
        keys,
        quarterly_points=quarterly_points,
        annual_points=annual_points,
    )


def income_value(data, keys):
    return flow_value(data.get("quarterly_income"), data.get("income"), keys)


def cashflow_value(data, keys):
    return flow_value(data.get("quarterly_cashflow"), data.get("cashflow"), keys)


def _aligned_series(series_map):
    non_empty = [item for item in series_map if not item[1].empty]
    if len(non_empty) != len(series_map):
        return pd.DataFrame()

    common_index = list(non_empty[0][1].index)
    for _, series in non_empty[1:]:
        common_index = [index for index in common_index if index in series.index]

    if not common_index:
        return pd.DataFrame()

    aligned = pd.DataFrame({
        name: series.loc[common_index]
        for name, series in non_empty
    }).dropna()

    return aligned


def aligned_flow_values(
    left_quarterly_frame,
    left_annual_frame,
    left_keys,
    right_quarterly_frame,
    right_annual_frame,
    right_keys,
):
    quarterly_aligned = _aligned_series([
        ("left", row_series(left_quarterly_frame, left_keys)),
        ("right", row_series(right_quarterly_frame, right_keys)),
    ])
    if len(quarterly_aligned.index) >= 4:
        recent_quarters = quarterly_aligned.iloc[:4]
        return recent_quarters["left"].sum(), recent_quarters["right"].sum()

    annual_aligned = _aligned_series([
        ("left", row_series(left_annual_frame, left_keys)),
        ("right", row_series(right_annual_frame, right_keys)),
    ])
    if not annual_aligned.empty:
        latest_annual = annual_aligned.iloc[0]
        return latest_annual["left"], latest_annual["right"]

    return None, None


def total_debt_series(frame):
    total_debt = row_series(frame, TOTAL_DEBT_KEYS)
    if not total_debt.empty:
        return total_debt

    current_debt = row_series(frame, CURRENT_DEBT_KEYS)
    long_term_debt = row_series(frame, LONG_TERM_DEBT_KEYS)

    if current_debt.empty and long_term_debt.empty:
        return pd.Series(dtype="float64")

    aligned = pd.concat(
        [current_debt.rename("current_debt"), long_term_debt.rename("long_term_debt")],
        axis=1,
    ).fillna(0)

    return aligned.sum(axis=1)


def total_debt_value(data):
    quarterly_debt = latest_value(total_debt_series(data.get("quarterly_balance")))
    if not is_missing(quarterly_debt):
        return quarterly_debt

    return latest_value(total_debt_series(data.get("balance")))


def average_total_debt_value(data, quarterly_points=5, annual_points=2):
    quarterly_values = [
        value
        for value in total_debt_series(data.get("quarterly_balance")).tolist()
        if not is_missing(value)
    ]
    if len(quarterly_values) >= 2:
        return mean_recent(quarterly_values[: min(quarterly_points, len(quarterly_values))])

    annual_values = [
        value
        for value in total_debt_series(data.get("balance")).tolist()
        if not is_missing(value)
    ]
    if len(annual_values) >= 2:
        return mean_recent(annual_values[: min(annual_points, len(annual_values))])

    latest_quarterly = latest_value(total_debt_series(data.get("quarterly_balance")))
    if not is_missing(latest_quarterly):
        return latest_quarterly

    return latest_value(total_debt_series(data.get("balance")))


def current_debt_value(data):
    explicit_current_debt = balance_value(data, CURRENT_DEBT_KEYS)
    if not is_missing(explicit_current_debt):
        return explicit_current_debt

    total_debt = balance_value(data, TOTAL_DEBT_KEYS)
    long_term_debt = balance_value(data, LONG_TERM_DEBT_KEYS)

    if is_missing(total_debt) or is_missing(long_term_debt):
        return None

    return max(total_debt - long_term_debt, 0)


def free_cash_flow_series(frame):
    operating_cash_flow = row_series(frame, OPERATING_CASH_FLOW_KEYS)
    capex = row_series(frame, CAPEX_KEYS)

    if operating_cash_flow.empty or capex.empty:
        return pd.Series(dtype="float64")

    aligned = pd.concat(
        [operating_cash_flow.rename("operating_cash_flow"), capex.abs().rename("capex")],
        axis=1,
    ).dropna()

    if aligned.empty:
        return pd.Series(dtype="float64")

    return aligned["operating_cash_flow"] - aligned["capex"]


def current_free_cash_flow(data):
    quarterly_fcf = trailing_sum(free_cash_flow_series(data.get("quarterly_cashflow")), 4)
    if not is_missing(quarterly_fcf):
        return quarterly_fcf

    return latest_value(free_cash_flow_series(data.get("cashflow")))


def normalized_free_cash_flow(data):
    annual_fcf_series = free_cash_flow_series(data.get("cashflow"))
    annual_normalized = median_recent(annual_fcf_series.tolist()[:3])
    if not is_missing(annual_normalized):
        return annual_normalized

    quarterly_fcf_series = free_cash_flow_series(data.get("quarterly_cashflow"))
    rolling_ttm_fcf = rolling_trailing_sums(quarterly_fcf_series, periods=4, windows=3)
    return median_recent(rolling_ttm_fcf)


def capex_value(data):
    capex = cashflow_value(data, CAPEX_KEYS)
    if is_missing(capex):
        return None

    return abs(capex)


def interest_expense_value(data):
    interest_expense = income_value(data, INTEREST_EXPENSE_KEYS)
    if is_missing(interest_expense):
        return None

    return abs(interest_expense)


def interest_paid_value(data):
    interest_paid = cashflow_value(data, INTEREST_PAID_KEYS)
    if is_missing(interest_paid):
        return None

    return abs(interest_paid)


def net_borrowing_value(data):
    direct_net_borrowing = cashflow_value(data, NET_BORROWING_KEYS)
    if not is_missing(direct_net_borrowing):
        return direct_net_borrowing

    debt_issued = cashflow_value(data, DEBT_ISSUED_KEYS)
    debt_repaid = cashflow_value(data, DEBT_REPAID_KEYS)

    if is_missing(debt_issued) and is_missing(debt_repaid):
        return None

    return (0 if is_missing(debt_issued) else debt_issued) - (
        0 if is_missing(debt_repaid) else abs(debt_repaid)
    )


def market_cap_value(info):
    if not isinstance(info, dict):
        return None

    market_cap = info.get("marketCap")
    if not is_missing(market_cap):
        return market_cap

    current_price = info.get("currentPrice")
    shares_outstanding = info.get("sharesOutstanding")
    if is_missing(current_price) or is_missing(shares_outstanding):
        return None

    return current_price * shares_outstanding
