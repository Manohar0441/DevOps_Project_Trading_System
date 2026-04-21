import pandas as pd

from utils.financials import (
    NET_INCOME_KEYS,
    OPERATING_CASH_FLOW_KEYS,
    REVENUE_KEYS,
    STOCK_BASED_COMPENSATION_KEYS,
    aligned_flow_values,
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
    if is_missing(current_value) or is_missing(previous_value) or previous_value <= 0:
        return None

    return (current_value - previous_value) / previous_value


def _latest_price(data, info):
    price = data.get("price")
    if price is not None and hasattr(price, "empty") and not price.empty and "Close" in price:
        latest_close = price["Close"].dropna()
        if not latest_close.empty:
            return latest_close.iloc[-1]

    if isinstance(info, dict):
        for key in ["currentPrice", "regularMarketPrice", "previousClose"]:
            value = info.get(key)
            if not is_missing(value):
                return value

    return None


def _ttm_and_previous_period(series):
    values = [value for value in series.tolist() if not is_missing(value)]
    if len(values) >= 8:
        return sum(values[:4]), sum(values[4:8])

    if len(values) >= 2:
        return values[0], values[1]

    return None, None


def _latest_and_previous(series):
    values = [value for value in series.tolist() if not is_missing(value)]
    if len(values) >= 2:
        return values[0], values[1]

    return None, None


def _quarter_yoy_momentum(series):
    values = [value for value in series.tolist() if not is_missing(value)]
    if len(values) < 5:
        return None

    return _growth_rate(values[0], values[4])


def _earnings_stability_score(quarterly_series, annual_series):
    quarterly_values = [value for value in quarterly_series.tolist() if not is_missing(value)]
    if len(quarterly_values) >= 8:
        ttm_windows = rolling_trailing_sums(pd.Series(quarterly_values, dtype="float64"), periods=4, windows=5)
        if len(ttm_windows) >= 3:
            return _stability_from_values(ttm_windows)

    annual_values = [value for value in annual_series.tolist() if not is_missing(value)]
    if len(annual_values) >= 3:
        return _stability_from_values(annual_values[:4])

    return None


def _stability_from_values(values):
    cleaned = [value for value in values if not is_missing(value)]
    if len(cleaned) < 3:
        return None

    mean_value = pd.Series(cleaned, dtype="float64").mean()
    if mean_value == 0:
        return None

    coefficient_of_variation = pd.Series(cleaned, dtype="float64").std(ddof=0) / abs(mean_value)
    return 1 / (1 + coefficient_of_variation)


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

    quarterly_eps = _ratio_series(quarterly_net_income, quarterly_average_shares)
    annual_eps = _ratio_series(annual_net_income, annual_average_shares)

    return quarterly_eps, annual_eps


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


def _preferred_eps_growth_inputs(quarterly_eps, annual_eps):
    annual_current, annual_previous = _latest_and_previous(annual_eps)
    if not is_missing(annual_current) and not is_missing(annual_previous):
        return annual_current, annual_previous

    ttm_current, ttm_previous = _ttm_and_previous_period(quarterly_eps)
    if not is_missing(ttm_current) and not is_missing(ttm_previous):
        return ttm_current, ttm_previous

    return None, None


def _earnings_quality_indicator(operating_cash_flow, net_income):
    raw_ratio = safe_div(operating_cash_flow, net_income)
    if is_missing(raw_ratio) or raw_ratio <= 0:
        return None

    # Treat 1.0 as ideal cash realization and penalize both weak conversion and
    # overly inflated conversion caused by temporary working-capital swings.
    return 1 / (1 + abs(1 - raw_ratio))


def _dividend_windows(data):
    dividends = data.get("dividends")
    if dividends is None or not hasattr(dividends, "empty") or dividends.empty:
        return None, None

    dividend_series = dividends.dropna()
    if dividend_series.empty:
        return None, None

    anchor_date = _anchor_date(data, dividend_series.index.max())
    current_start = anchor_date - pd.Timedelta(days=365)
    previous_start = current_start - pd.Timedelta(days=365)

    current_ttm = dividend_series[(dividend_series.index > current_start) & (dividend_series.index <= anchor_date)].sum()
    previous_ttm = dividend_series[(dividend_series.index > previous_start) & (dividend_series.index <= current_start)].sum()

    return current_ttm, previous_ttm


def _anchor_date(data, fallback_date):
    price = data.get("price")
    if price is not None and hasattr(price, "empty") and not price.empty:
        try:
            latest_price_date = price.index.max()
            if latest_price_date is not None:
                return pd.Timestamp(latest_price_date)
        except (TypeError, ValueError):
            pass

    return pd.Timestamp(fallback_date)


def compute_growth(data):
    info = data.get("info", {}) if isinstance(data.get("info"), dict) else {}

    quarterly_income = data.get("quarterly_income")
    annual_income = data.get("income")

    quarterly_revenue = row_series(quarterly_income, REVENUE_KEYS)
    annual_revenue = row_series(annual_income, REVENUE_KEYS)
    revenue_current, revenue_previous = _ttm_and_previous_period(quarterly_revenue)
    if is_missing(revenue_current) or is_missing(revenue_previous):
        revenue_current, revenue_previous = _ttm_and_previous_period(annual_revenue)

    quarterly_eps, annual_eps = _eps_series(data)
    eps_current, eps_previous = _preferred_eps_growth_inputs(quarterly_eps, annual_eps)
    if is_missing(eps_current) or is_missing(eps_previous):
        eps_current, eps_previous = _ttm_and_previous_period(quarterly_eps)

    quarterly_net_income = row_series(quarterly_income, NET_INCOME_KEYS)
    annual_net_income = row_series(annual_income, NET_INCOME_KEYS)

    revenue_growth_rate = _growth_rate(revenue_current, revenue_previous)
    eps_growth_rate = _growth_rate(eps_current, eps_previous)
    eps_momentum = _quarter_yoy_momentum(quarterly_eps)
    if is_missing(eps_momentum):
        eps_momentum = _growth_rate(eps_current, eps_previous)

    earnings_stability = _earnings_stability_score(quarterly_net_income, annual_net_income)

    aligned_ocf, aligned_net_income = aligned_flow_values(
        data.get("quarterly_cashflow"),
        data.get("cashflow"),
        OPERATING_CASH_FLOW_KEYS,
        quarterly_income,
        annual_income,
        NET_INCOME_KEYS,
    )
    aligned_sbc, _ = aligned_flow_values(
        data.get("quarterly_cashflow"),
        data.get("cashflow"),
        STOCK_BASED_COMPENSATION_KEYS,
        quarterly_income,
        annual_income,
        NET_INCOME_KEYS,
    )
    quality_ocf = aligned_ocf
    if not is_missing(quality_ocf) and not is_missing(aligned_sbc) and aligned_sbc >= 0:
        quality_ocf = quality_ocf - aligned_sbc
    earnings_quality_indicator = _earnings_quality_indicator(quality_ocf, aligned_net_income)

    current_dividend_ttm, previous_dividend_ttm = _dividend_windows(data)
    latest_price = _latest_price(data, info)

    dividend_yield = safe_div(current_dividend_ttm, latest_price)
    dividend_growth_rate = _growth_rate(current_dividend_ttm, previous_dividend_ttm)
    dividend_payout_ratio = safe_div(current_dividend_ttm, eps_current)
    if not is_missing(dividend_payout_ratio) and dividend_payout_ratio < 0:
        dividend_payout_ratio = None

    retention_ratio = None
    if not is_missing(dividend_payout_ratio):
        retention_ratio = 1 - dividend_payout_ratio

    metrics = {
        "Revenue_Growth": revenue_growth_rate,
        "Revenue_Growth_Rate": revenue_growth_rate,
        "EPS_Growth": eps_growth_rate,
        "EPS_Growth_Rate": eps_growth_rate,
        "EPS_Momentum": eps_momentum,
        "Earnings_Stability": earnings_stability,
        "Earnings_Quality_Indicator": earnings_quality_indicator,
        "Dividend_Payout_Ratio": dividend_payout_ratio,
        "Retention_Ratio": retention_ratio,
        "Dividend_Yield": dividend_yield,
        "Dividend_Growth_Rate": dividend_growth_rate,
    }

    return {key: normalize_output(value) for key, value in metrics.items()}
