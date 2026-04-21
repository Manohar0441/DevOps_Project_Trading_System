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

# ─────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────

def _growth_rate(current_value, previous_value):
    """Safe YoY growth rate. Returns None if inputs are invalid or previous <= 0."""
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


def _clean_values(series):
    """Return a list of non-missing floats from a Series, most-recent first.

    Sorts by index descending so that callers can safely use positional
    slicing (index 0 = latest period, index 1 = one period prior, …)
    regardless of the order the data source returns columns.
    """
    if series is None or series.empty:
        return []
    sorted_series = series.sort_index(ascending=False)
    return [float(v) for v in sorted_series.tolist() if not is_missing(v)]


# ── Annual YoY ────────────────────────────────

def _annual_yoy(annual_series):
    """Return (latest_annual, prior_annual) for true YoY comparison.

    Requires at least 2 annual data points.
    """
    values = _clean_values(annual_series)
    if len(values) >= 2:
        return values[0], values[1]
    return None, None


# ── Trailing-twelve-month (quarterly) ────────

def _ttm_current(quarterly_series):
    """Sum of the 4 most-recent quarters (TTM). Returns None if <4 quarters."""
    values = _clean_values(quarterly_series)
    if len(values) >= 4:
        return sum(values[:4])
    return None


def _ttm_yoy(quarterly_series):
    """Return (TTM_current, TTM_previous) using 8 quarters.

    Requires exactly 8 non-missing quarters to produce a valid YoY
    comparison.  Avoids the old fallback that compared two consecutive
    quarters (Q vs Q-1) which produced wildly wrong growth rates.
    """
    values = _clean_values(quarterly_series)
    if len(values) >= 8:
        return sum(values[:4]), sum(values[4:8])
    return None, None


# ── EPS helpers ───────────────────────────────

def _latest_and_previous(series):
    values = _clean_values(series)
    if len(values) >= 2:
        return values[0], values[1]
    return None, None


def _quarter_yoy_momentum(series):
    """Compare the most-recent quarter to the same quarter one year ago (index 4)."""
    values = _clean_values(series)
    if len(values) < 5:
        return None
    return _growth_rate(values[0], values[4])


def _earnings_stability_score(quarterly_series, annual_series):
    quarterly_values = _clean_values(quarterly_series)
    if len(quarterly_values) >= 8:
        ttm_windows = rolling_trailing_sums(
            pd.Series(quarterly_values, dtype="float64"), periods=4, windows=5
        )
        if len(ttm_windows) >= 3:
            return _stability_from_values(ttm_windows)

    annual_values = _clean_values(annual_series)
    if len(annual_values) >= 3:
        return _stability_from_values(annual_values[:4])

    return None


def _stability_from_values(values):
    cleaned = [v for v in values if not is_missing(v)]
    if len(cleaned) < 3:
        return None
    s = pd.Series(cleaned, dtype="float64")
    mean_value = s.mean()
    if mean_value == 0:
        return None
    coefficient_of_variation = s.std(ddof=0) / abs(mean_value)
    return 1 / (1 + coefficient_of_variation)


def _eps_series(data):
    quarterly_income = data.get("quarterly_income")
    annual_income = data.get("income")

    quarterly_eps = row_series(quarterly_income, EPS_KEYS)
    annual_eps = row_series(annual_income, EPS_KEYS)

    if not quarterly_eps.empty or not annual_eps.empty:
        return quarterly_eps, annual_eps

    # Fallback: derive EPS from net income ÷ shares
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
    """Annual EPS YoY is the primary source; TTM quarterly is the fallback."""
    annual_current, annual_previous = _annual_yoy(annual_eps)
    if not is_missing(annual_current) and not is_missing(annual_previous):
        return annual_current, annual_previous

    ttm_current, ttm_previous = _ttm_yoy(quarterly_eps)
    if not is_missing(ttm_current) and not is_missing(ttm_previous):
        return ttm_current, ttm_previous

    return None, None


def _earnings_quality_indicator(operating_cash_flow, net_income):
    raw_ratio = safe_div(operating_cash_flow, net_income)
    if is_missing(raw_ratio) or raw_ratio <= 0:
        return None
    # Treat 1.0 as ideal cash realisation; penalise both weak conversion and
    # inflated conversion caused by temporary working-capital swings.
    return 1 / (1 + abs(1 - raw_ratio))


# ── Dividend helpers ──────────────────────────

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

    current_ttm = dividend_series[
        (dividend_series.index > current_start) & (dividend_series.index <= anchor_date)
    ].sum()
    previous_ttm = dividend_series[
        (dividend_series.index > previous_start) & (dividend_series.index <= current_start)
    ].sum()

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


# ─────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────

def compute_growth(data):
    info = data.get("info", {}) if isinstance(data.get("info"), dict) else {}

    quarterly_income = data.get("quarterly_income")
    annual_income = data.get("income")

    quarterly_revenue = row_series(quarterly_income, REVENUE_KEYS)
    annual_revenue = row_series(annual_income, REVENUE_KEYS)

    # ── Revenue growth ────────────────────────────────────────────────────────
    # Priority 1: Annual YoY  (most reliable — avoids seasonal distortion and
    #             the 8-quarter data requirement of TTM comparison).
    # Priority 2: TTM quarterly YoY  (requires exactly 8 clean quarters).
    # NOTE: the old code was quarterly-first; when <8 quarters existed it fell
    #       back to values[0] vs values[1] which compared *consecutive quarters*
    #       rather than the same period YoY — the root cause of the ~40% anomaly.
    revenue_current, revenue_previous = _annual_yoy(annual_revenue)
    if is_missing(revenue_current) or is_missing(revenue_previous):
        revenue_current, revenue_previous = _ttm_yoy(quarterly_revenue)

    # ── EPS growth ────────────────────────────────────────────────────────────
    quarterly_eps, annual_eps = _eps_series(data)
    eps_current, eps_previous = _preferred_eps_growth_inputs(quarterly_eps, annual_eps)

    # ── Net income (used for stability & quality) ─────────────────────────────
    quarterly_net_income = row_series(quarterly_income, NET_INCOME_KEYS)
    annual_net_income = row_series(annual_income, NET_INCOME_KEYS)

    # ── Derived metrics ───────────────────────────────────────────────────────
    revenue_growth_rate = _growth_rate(revenue_current, revenue_previous)
    eps_growth_rate = _growth_rate(eps_current, eps_previous)

    # EPS momentum: same quarter YoY (more timely than full-year comparison).
    eps_momentum = _quarter_yoy_momentum(quarterly_eps)
    if is_missing(eps_momentum):
        eps_momentum = eps_growth_rate  # graceful degradation

    earnings_stability = _earnings_stability_score(quarterly_net_income, annual_net_income)

    # ── Cash-flow quality ─────────────────────────────────────────────────────
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
    # Subtract SBC from OCF so quality score reflects real cash earnings.
    quality_ocf = aligned_ocf
    if not is_missing(quality_ocf) and not is_missing(aligned_sbc) and aligned_sbc >= 0:
        quality_ocf = quality_ocf - aligned_sbc
    earnings_quality_indicator = _earnings_quality_indicator(quality_ocf, aligned_net_income)

    # ── Dividends ─────────────────────────────────────────────────────────────
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

    # ── Output ────────────────────────────────────────────────────────────────
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