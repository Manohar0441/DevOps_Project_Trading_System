import pandas as pd

from utils.financials import (
    NET_INCOME_KEYS,
    OPERATING_CASH_FLOW_KEYS,
    REVENUE_KEYS,
    _safe_gt,
    _safe_lt,
    cashflow_value,
    income_value,
    is_missing,
    normalize_output,
    rolling_trailing_sums,
    row_series,
    safe_div,
)


EPS_KEYS = ["Diluted EPS", "Basic EPS"]
AVERAGE_SHARES_KEYS = [
    "Diluted Average Shares",
    "Diluted Average Shares Number",
    "Diluted Weighted Average Shares",
    "Basic Average Shares",
    "Basic Average Shares Number",
    "Basic Weighted Average Shares",
]


def _growth_rate(current_value, previous_value):
    if is_missing(current_value) or is_missing(previous_value) or not _safe_gt(previous_value, 0):
        return None
    return (current_value - previous_value) / previous_value


def _clean_values(series):
    if series is None or series.empty:
        return []
    sorted_series = series.sort_index(ascending=False)
    return [float(v) for v in sorted_series.tolist() if not is_missing(v)]


def _annual_yoy(annual_series):
    values = _clean_values(annual_series)
    if len(values) >= 2:
        return values[0], values[1]
    return None, None


def _ttm_yoy(quarterly_series):
    values = _clean_values(quarterly_series)
    if len(values) >= 8:
        return sum(values[:4]), sum(values[4:8])
    return None, None


def _stability_from_values(values):
    cleaned = [v for v in values if not is_missing(v)]
    if len(cleaned) < 3:
        return None

    series = pd.Series(cleaned, dtype="float64")
    mean_value = series.mean()
    if mean_value == 0:
        return None

    coefficient_of_variation = series.std(ddof=0) / abs(mean_value)
    return 1 / (1 + coefficient_of_variation)


def _earnings_stability_score(quarterly_series, annual_series):
    quarterly_values = _clean_values(quarterly_series)
    if len(quarterly_values) >= 8:
        ttm_windows = rolling_trailing_sums(
            pd.Series(quarterly_values, dtype="float64"),
            periods=4,
            windows=5,
        )
        if len(ttm_windows) >= 3:
            return _stability_from_values(ttm_windows)

    annual_values = _clean_values(annual_series)
    if len(annual_values) >= 3:
        return _stability_from_values(annual_values[:4])

    return None


def _ratio_series(numerator_series, denominator_series):
    if numerator_series.empty or denominator_series.empty:
        return pd.Series(dtype="float64")

    aligned = pd.concat(
        [numerator_series.rename("numerator"), denominator_series.rename("denominator")],
        axis=1,
    ).dropna()

    if aligned.empty:
        return pd.Series(dtype="float64")

    aligned = aligned[aligned["denominator"] != 0]
    if aligned.empty:
        return pd.Series(dtype="float64")

    return aligned["numerator"] / aligned["denominator"]


def _eps_series(data):
    quarterly_income = data.get("quarterly_income")
    annual_income = data.get("income")

    quarterly_eps = row_series(quarterly_income, EPS_KEYS)
    annual_eps = row_series(annual_income, EPS_KEYS)

    if not quarterly_eps.empty or not annual_eps.empty:
        return quarterly_eps, annual_eps

    quarterly_net_income = row_series(quarterly_income, NET_INCOME_KEYS)
    annual_net_income = row_series(annual_income, NET_INCOME_KEYS)
    quarterly_average_shares = row_series(quarterly_income, AVERAGE_SHARES_KEYS)
    annual_average_shares = row_series(annual_income, AVERAGE_SHARES_KEYS)

    return (
        _ratio_series(quarterly_net_income, quarterly_average_shares),
        _ratio_series(annual_net_income, annual_average_shares),
    )


def _preferred_eps_growth_inputs(quarterly_eps, annual_eps):
    annual_current, annual_previous = _annual_yoy(annual_eps)
    if not is_missing(annual_current) and not is_missing(annual_previous):
        return annual_current, annual_previous, "ANNUAL_YOY"

    ttm_current, ttm_previous = _ttm_yoy(quarterly_eps)
    if not is_missing(ttm_current) and not is_missing(ttm_previous):
        return ttm_current, ttm_previous, "TTM_YOY"

    return None, None, None


def _earnings_quality_indicator(operating_cash_flow, net_income):
    raw_ratio = safe_div(operating_cash_flow, net_income)
    if is_missing(raw_ratio) or not _safe_gt(raw_ratio, 0):
        return None
    return 1 / (1 + abs(1 - raw_ratio))


def _dividend_windows(data):
    dividends = data.get("dividends")
    if dividends is None or not hasattr(dividends, "empty") or dividends.empty:
        return None, None

    dividend_series = dividends.dropna()
    if dividend_series.empty:
        return None, None

    anchor_date = pd.Timestamp(dividend_series.index.max())
    price = data.get("price")
    if price is not None and hasattr(price, "empty") and not price.empty:
        try:
            latest_price_date = price.index.max()
            if latest_price_date is not None:
                anchor_date = pd.Timestamp(latest_price_date)
        except (TypeError, ValueError):
            pass

    current_start = anchor_date - pd.Timedelta(days=365)
    previous_start = current_start - pd.Timedelta(days=365)

    current_ttm = dividend_series[
        (dividend_series.index > current_start) & (dividend_series.index <= anchor_date)
    ].sum()
    previous_ttm = dividend_series[
        (dividend_series.index > previous_start) & (dividend_series.index <= current_start)
    ].sum()

    return current_ttm, previous_ttm


def revenue_growth_details(data):
    quarterly_revenue = row_series(data.get("quarterly_income"), REVENUE_KEYS)
    annual_revenue = row_series(data.get("income"), REVENUE_KEYS)

    current_value, previous_value = _annual_yoy(annual_revenue)
    basis = "ANNUAL_YOY"
    if is_missing(current_value) or is_missing(previous_value):
        current_value, previous_value = _ttm_yoy(quarterly_revenue)
        basis = "TTM_YOY"

    return _growth_rate(current_value, previous_value), basis


def eps_growth_details(data):
    quarterly_eps, annual_eps = _eps_series(data)
    current_value, previous_value, basis = _preferred_eps_growth_inputs(quarterly_eps, annual_eps)
    return _growth_rate(current_value, previous_value), basis


def compute_revenue_growth_rate(data):
    value, _ = revenue_growth_details(data)
    return value


def compute_eps_growth_rate(data):
    value, _ = eps_growth_details(data)
    return value


def compute_growth(data):
    quarterly_eps, annual_eps = _eps_series(data)
    revenue_growth_rate, revenue_growth_basis = revenue_growth_details(data)
    eps_growth_rate, eps_growth_basis = eps_growth_details(data)
    eps_current, _, _ = _preferred_eps_growth_inputs(quarterly_eps, annual_eps)

    current_dividend_ttm, previous_dividend_ttm = _dividend_windows(data)
    dividend_growth_rate = _growth_rate(current_dividend_ttm, previous_dividend_ttm)
    dividend_payout_ratio = safe_div(current_dividend_ttm, eps_current)
    if not is_missing(dividend_payout_ratio) and _safe_lt(dividend_payout_ratio, 0):
        dividend_payout_ratio = None

    retention_ratio = None
    if not is_missing(dividend_payout_ratio):
        retention_ratio = 1 - dividend_payout_ratio

    metrics = {
        "Revenue_Growth": revenue_growth_rate,
        "Revenue_Growth_Rate": revenue_growth_rate,
        "EPS_Growth": eps_growth_rate,
        "EPS_Growth_Rate": eps_growth_rate,
        "Dividend_Payout_Ratio": dividend_payout_ratio,
        "Retention_Ratio": retention_ratio,
        "Dividend_Growth_Rate": dividend_growth_rate,
        "Earnings_Stability": _earnings_stability_score(quarterly_eps, annual_eps),
        "Earnings_Quality_Indicator": _earnings_quality_indicator(
            cashflow_value(data, OPERATING_CASH_FLOW_KEYS),
            income_value(data, NET_INCOME_KEYS),
        ),
        "_meta": {
            "revenue_growth_basis": revenue_growth_basis,
            "eps_growth_basis": eps_growth_basis,
            "period_policy": "ANNUAL_YOY_PRIMARY_TTM_YOY_FALLBACK",
        },
    }

    return {key: normalize_output(value) for key, value in metrics.items()}
