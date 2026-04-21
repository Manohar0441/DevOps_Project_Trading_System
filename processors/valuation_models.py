import logging
import math

import pandas as pd

from utils.financials import (
    CASH_KEYS,
    EQUITY_KEYS,
    NET_INCOME_KEYS,
    OPERATING_CASH_FLOW_KEYS,
    PRETAX_INCOME_KEYS,
    REVENUE_KEYS,
    TAX_EXPENSE_KEYS,
    average_total_debt_value,
    balance_value,
    cashflow_value,
    current_free_cash_flow,
    income_value,
    interest_expense_value,
    is_missing,
    market_cap_value,
    normalize_output,
    normalized_free_cash_flow,
    row_series,
    safe_div,
    total_debt_value,
)

logger = logging.getLogger(__name__)

EPS_KEYS = ["Diluted EPS", "Basic EPS"]
AVERAGE_SHARES_KEYS = [
    "Diluted Average Shares",
    "Diluted Average Shares Number",
    "Diluted Weighted Average Shares",
    "Basic Average Shares",
    "Basic Average Shares Number",
    "Basic Weighted Average Shares",
]

RISK_FREE_RATE = 0.045
EQUITY_RISK_PREMIUM = 0.055
BASELINE_BOND_YIELD = 0.044
TERMINAL_GROWTH_RATE = 0.025
DCF_PROJECTION_YEARS = 10          # Extended from 5 → better captures quality-company value


# ─────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────

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


def _shares_outstanding(data, info):
    if isinstance(info, dict):
        shares = info.get("sharesOutstanding")
        if not is_missing(shares):
            return shares

    quarterly_shares = row_series(data.get("quarterly_income"), AVERAGE_SHARES_KEYS)
    annual_shares = row_series(data.get("income"), AVERAGE_SHARES_KEYS)

    for series in [quarterly_shares, annual_shares]:
        values = [v for v in series.tolist() if not is_missing(v) and v > 0]
        if values:
            return values[0]

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


def _eps_value(data, shares_outstanding):
    annual_eps = row_series(data.get("income"), EPS_KEYS)
    # Sort most-recent first before picking
    annual_eps = annual_eps.sort_index(ascending=False)
    annual_eps_values = [v for v in annual_eps.tolist() if not is_missing(v)]
    if annual_eps_values:
        return annual_eps_values[0]

    net_income = income_value(data, NET_INCOME_KEYS)
    if is_missing(net_income) or is_missing(shares_outstanding) or shares_outstanding <= 0:
        return None

    return net_income / shares_outstanding


def _book_value_per_share(data, shares_outstanding):
    equity = balance_value(data, EQUITY_KEYS)
    if is_missing(equity) or is_missing(shares_outstanding) or shares_outstanding <= 0:
        return None

    return equity / shares_outstanding


def _per_share(value, shares_outstanding):
    if is_missing(value) or is_missing(shares_outstanding) or shares_outstanding <= 0:
        return None

    return value / shares_outstanding


def _clamp(value, floor_value, ceiling_value):
    # Handle None
    if value is None:
        return None

    # Handle complex numbers
    if isinstance(value, complex):
        if value.imag != 0:
            return None  # discard invalid financial result
        value = value.real

    # Handle NaN / inf
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None

    return max(floor_value, min(ceiling_value, value))

# ── Growth rate helpers ───────────────────────────────────────────────────────

def _clean_sorted_values(series):
    """Return non-missing floats from a Series, most-recent first.

    Explicit sort prevents the direction returned by the data source
    (ascending vs descending) from corrupting positional slicing.
    """
    if series is None or series.empty:
        return []
    sorted_series = series.sort_index(ascending=False)
    return [float(v) for v in sorted_series.tolist() if not is_missing(v)]


def _ttm_yoy_growth(quarterly_series):
    """TTM YoY: sum of 4 most-recent quarters vs prior 4 quarters.

    Returns None when fewer than 8 clean quarters are available — the old
    fallback that compared two consecutive quarters (values[0] vs values[1])
    produced a *quarterly* change that was then mistaken for annual growth.
    """
    values = _clean_sorted_values(quarterly_series)
    if len(values) >= 8:
        current = sum(values[:4])
        previous = sum(values[4:8])
        if previous > 0:
            return (current - previous) / previous
    return None


def _annual_yoy_growth(annual_series):
    """Most-recent annual period vs the one before."""
    values = _clean_sorted_values(annual_series)
    if len(values) >= 2 and values[1] > 0:
        return (values[0] - values[1]) / values[1]
    return None


def _historical_growth_rate(data, keys):
    """Annual-first growth rate; TTM quarterly as fallback.

    Old order (quarterly-first) caused inflated growth when quarterly data
    had < 8 values and the consecutive-quarter fallback fired.
    """
    annual_series = row_series(data.get("income"), keys)
    quarterly_series = row_series(data.get("quarterly_income"), keys)

    # Priority 1: annual YoY — stable, no data-count requirements beyond 2 years
    growth = _annual_yoy_growth(annual_series)
    if not is_missing(growth):
        return growth

    # Priority 2: TTM quarterly — only if 8 clean quarters exist
    return _ttm_yoy_growth(quarterly_series)


def _multi_year_cagr(data, keys, years=3):
    """CAGR over `years` annual periods for a smoother growth estimate."""
    annual_series = row_series(data.get("income"), keys)
    values = _clean_sorted_values(annual_series)
    if len(values) > years and values[years] > 0:
        return (values[0] / values[years]) ** (1 / years) - 1
    return None


# ─────────────────────────────────────────────
# WACC
# ─────────────────────────────────────────────

def _effective_tax_rate(data):
    tax_expense = income_value(data, TAX_EXPENSE_KEYS)
    pretax_income = income_value(data, PRETAX_INCOME_KEYS)
    tax_rate = safe_div(tax_expense, pretax_income)

    if is_missing(tax_rate):
        return 0.21

    return _clamp(tax_rate, 0.0, 0.35)


def compute_wacc(data):
    info = data.get("info", {}) if isinstance(data.get("info"), dict) else {}

    market_cap = market_cap_value(info)
    total_debt = total_debt_value(data)

    if is_missing(market_cap) and is_missing(total_debt):
        return None

    market_cap = 0 if is_missing(market_cap) else market_cap
    total_debt = 0 if is_missing(total_debt) else total_debt

    total_capital = market_cap + total_debt
    if total_capital <= 0:
        return None

    beta = info.get("beta") if isinstance(info, dict) else None
    if is_missing(beta):
        beta = 1.0
    beta = _clamp(beta, 0.5, 2.0)

    cost_of_equity = _clamp(RISK_FREE_RATE + (beta * EQUITY_RISK_PREMIUM), 0.07, 0.18)

    average_debt = average_total_debt_value(data)
    interest_expense = interest_expense_value(data)
    cost_of_debt = safe_div(interest_expense, average_debt)
    if is_missing(cost_of_debt):
        cost_of_debt = 0.045
    cost_of_debt = _clamp(cost_of_debt, 0.03, 0.12)

    tax_rate = _effective_tax_rate(data)

    return (
        (market_cap / total_capital) * cost_of_equity
        + (total_debt / total_capital) * cost_of_debt * (1 - tax_rate)
    )


# ─────────────────────────────────────────────
# DCF
# ─────────────────────────────────────────────

def _quality_terminal_growth(data, wacc):
    """Scale terminal growth by company quality (FCF margin & revenue stability).

    Quality companies (high FCF margins, consistent growth) sustain above-GDP
    nominal growth longer — using a flat 2.5 % for all companies undervalues them.
    Floor 2.0 %, ceiling 3.5 % (capped below WACC−1 %).
    """
    revenue_series = row_series(data.get("income"), REVENUE_KEYS)
    revenue_values = _clean_sorted_values(revenue_series)

    # Simple proxy: mean of 1- and 3-year revenue CAGR as a quality signal
    growth_1y = _annual_yoy_growth(revenue_series)
    growth_3y = _multi_year_cagr(data, REVENUE_KEYS, years=3)

    candidates = [g for g in [growth_1y, growth_3y] if not is_missing(g)]
    avg_growth = sum(candidates) / len(candidates) if candidates else 0.05

    # Terminal growth scales from 2.0 % (slow grower) up to 3.5 % (fast grower)
    # based on historical growth, with a hard ceiling at WACC − 1 %.
    raw_terminal = TERMINAL_GROWTH_RATE + _clamp(avg_growth - 0.05, -0.005, 0.01)
    ceiling = (wacc - 0.01) if not is_missing(wacc) else 0.035
    return _clamp(raw_terminal, 0.02, min(0.035, ceiling))


def _dcf_assumptions(data, wacc):
    """Return (initial_growth, terminal_growth) for the DCF model.

    Uses blended 1-year and 3-year CAGR for a more stable initial growth
    estimate rather than a single-period comparison that can be distorted
    by one-off events.
    """
    revenue_1y = _historical_growth_rate(data, REVENUE_KEYS)
    revenue_3y = _multi_year_cagr(data, REVENUE_KEYS, years=3)
    earnings_1y = _historical_growth_rate(data, NET_INCOME_KEYS)
    earnings_3y = _multi_year_cagr(data, NET_INCOME_KEYS, years=3)

    candidates = [
        g for g in [revenue_1y, revenue_3y, earnings_1y, earnings_3y]
        if not is_missing(g)
    ]

    initial_growth = sum(candidates) / len(candidates) if candidates else 0.05
    initial_growth = _clamp(initial_growth, 0.0, 0.20)   # raised ceiling: 15 → 20 %

    terminal_growth = _quality_terminal_growth(data, wacc)

    if not is_missing(wacc) and terminal_growth >= wacc:
        terminal_growth = max(0.01, wacc - 0.01)

    return initial_growth, terminal_growth


def compute_dcf(data):
    normalized_fcf = normalized_free_cash_flow(data)
    if is_missing(normalized_fcf) or normalized_fcf <= 0:
        return None

    wacc = compute_wacc(data)
    if is_missing(wacc):
        return None

    initial_growth, terminal_growth = _dcf_assumptions(data, wacc)
    if is_missing(initial_growth) or is_missing(terminal_growth) or terminal_growth >= wacc:
        return None

    projection_years = DCF_PROJECTION_YEARS   # 10-year horizon
    projected_fcf = normalized_fcf
    present_value_of_flows = 0.0

    for year in range(1, projection_years + 1):
        # Linear fade from initial to terminal growth across the forecast window
        if projection_years == 1:
            year_growth = terminal_growth
        else:
            fade = (year - 1) / (projection_years - 1)
            year_growth = initial_growth + (terminal_growth - initial_growth) * fade

        projected_fcf *= (1 + year_growth)
        present_value_of_flows += projected_fcf / ((1 + wacc) ** year)

    terminal_value = projected_fcf * (1 + terminal_growth) / (wacc - terminal_growth)
    present_value_of_terminal = terminal_value / ((1 + wacc) ** projection_years)

    enterprise_value = present_value_of_flows + present_value_of_terminal

    cash = balance_value(data, CASH_KEYS)
    total_debt = total_debt_value(data)
    equity_value = (
        enterprise_value
        - (0 if is_missing(total_debt) else total_debt)
        + (0 if is_missing(cash) else cash)
    )

    shares_outstanding = _shares_outstanding(data, data.get("info", {}))
    return {
        "Enterprise_Value": normalize_output(enterprise_value),
        "Equity_Value": normalize_output(equity_value),
        "Per_Share_Value": normalize_output(_per_share(equity_value, shares_outstanding)),
    }


def _terminal_value_block(data):
    """Standalone terminal value breakdown — re-uses DCF assumptions for consistency."""
    dcf = compute_dcf(data)
    if dcf is None:
        return None

    normalized_fcf = normalized_free_cash_flow(data)
    wacc = compute_wacc(data)
    initial_growth, terminal_growth = _dcf_assumptions(data, wacc)
    if is_missing(normalized_fcf) or is_missing(wacc) or is_missing(terminal_growth) or terminal_growth >= wacc:
        return None

    projection_years = DCF_PROJECTION_YEARS
    projected_fcf = normalized_fcf
    for year in range(1, projection_years + 1):
        if projection_years == 1:
            year_growth = terminal_growth
        else:
            fade = (year - 1) / (projection_years - 1)
            year_growth = initial_growth + (terminal_growth - initial_growth) * fade
        projected_fcf *= (1 + year_growth)

    terminal_value = projected_fcf * (1 + terminal_growth) / (wacc - terminal_growth)
    present_value_of_terminal = terminal_value / ((1 + wacc) ** projection_years)
    shares_outstanding = _shares_outstanding(data, data.get("info", {}))

    return {
        "Enterprise_Value": normalize_output(terminal_value),
        "Present_Value": normalize_output(present_value_of_terminal),
        "Per_Share_Present_Value": normalize_output(
            _per_share(present_value_of_terminal, shares_outstanding)
        ),
    }


# ─────────────────────────────────────────────
# Dividend discount models
# ─────────────────────────────────────────────

def _dividend_ttm_and_growth(data):
    dividends = data.get("dividends")
    if dividends is None or not hasattr(dividends, "empty") or dividends.empty:
        return None, None

    dividend_series = dividends.dropna()
    if dividend_series.empty:
        return None, None

    price = data.get("price")
    if price is not None and hasattr(price, "empty") and not price.empty:
        try:
            anchor_date = pd.Timestamp(price.index.max())
        except (TypeError, ValueError):
            anchor_date = pd.Timestamp(dividend_series.index.max())
    else:
        anchor_date = pd.Timestamp(dividend_series.index.max())

    annual_totals = []
    for offset in range(4):
        end_date = anchor_date - pd.Timedelta(days=365 * offset)
        start_date = end_date - pd.Timedelta(days=365)
        annual_totals.append(
            dividend_series[
                (dividend_series.index > start_date) & (dividend_series.index <= end_date)
            ].sum()
        )

    current_dividend = annual_totals[0]
    historical_totals = [v for v in annual_totals if not is_missing(v) and v > 0]

    growth_rate = None
    if len(historical_totals) >= 2:
        oldest = historical_totals[-1]
        newest = historical_totals[0]
        periods = len(historical_totals) - 1
        if oldest > 0 and periods > 0:
            growth_rate = (newest / oldest) ** (1 / periods) - 1

    return current_dividend, growth_rate


def _cost_of_equity(data):
    info = data.get("info", {}) if isinstance(data.get("info"), dict) else {}
    beta = info.get("beta") if isinstance(info, dict) else None
    if is_missing(beta):
        beta = 1.0
    return _clamp(RISK_FREE_RATE + (beta * EQUITY_RISK_PREMIUM), 0.07, 0.18)


def _gordon_growth_model(data):
    current_dividend, dividend_growth = _dividend_ttm_and_growth(data)
    cost_of_equity = _cost_of_equity(data)

    if is_missing(current_dividend) or current_dividend <= 0 or is_missing(cost_of_equity):
        return None

    stable_growth = dividend_growth if not is_missing(dividend_growth) else TERMINAL_GROWTH_RATE
    stable_growth = _clamp(stable_growth, 0.0, 0.03)
    if stable_growth >= cost_of_equity:
        return None

    next_dividend = current_dividend * (1 + stable_growth)
    return next_dividend / (cost_of_equity - stable_growth)


def _two_stage_ddm(data):
    current_dividend, dividend_growth = _dividend_ttm_and_growth(data)
    cost_of_equity = _cost_of_equity(data)

    if is_missing(current_dividend) or current_dividend <= 0 or is_missing(cost_of_equity):
        return None

    high_growth = _clamp(
        dividend_growth if not is_missing(dividend_growth) else 0.06, 0.0, 0.12
    )
    stable_growth = _clamp(TERMINAL_GROWTH_RATE, 0.0, 0.03)
    if stable_growth >= cost_of_equity:
        return None

    dividend = current_dividend
    present_value = 0.0
    for year in range(1, 6):
        dividend *= (1 + high_growth)
        present_value += dividend / ((1 + cost_of_equity) ** year)

    terminal_dividend = dividend * (1 + stable_growth)
    terminal_value = terminal_dividend / (cost_of_equity - stable_growth)
    return present_value + (terminal_value / ((1 + cost_of_equity) ** 5))


def _multi_stage_ddm(data):
    current_dividend, dividend_growth = _dividend_ttm_and_growth(data)
    cost_of_equity = _cost_of_equity(data)

    if is_missing(current_dividend) or current_dividend <= 0 or is_missing(cost_of_equity):
        return None

    high_growth = _clamp(
        dividend_growth if not is_missing(dividend_growth) else 0.06, 0.0, 0.12
    )
    stable_growth = _clamp(TERMINAL_GROWTH_RATE, 0.0, 0.03)
    if stable_growth >= cost_of_equity:
        return None

    years = 10
    dividend = current_dividend
    present_value = 0.0
    for year in range(1, years + 1):
        fade = (year - 1) / (years - 1)
        year_growth = high_growth + (stable_growth - high_growth) * fade
        dividend *= (1 + year_growth)
        present_value += dividend / ((1 + cost_of_equity) ** year)

    terminal_dividend = dividend * (1 + stable_growth)
    terminal_value = terminal_dividend / (cost_of_equity - stable_growth)
    return present_value + (terminal_value / ((1 + cost_of_equity) ** years))


# ─────────────────────────────────────────────
# Graham / comparable analysis
# ─────────────────────────────────────────────

def _benjamin_graham_formula(data):
    shares_outstanding = _shares_outstanding(data, data.get("info", {}))
    eps = _eps_value(data, shares_outstanding)
    if is_missing(eps) or eps <= 0:
        return None

    growth_rate = _historical_growth_rate(data, NET_INCOME_KEYS)
    growth_percent = _clamp(
        (0 if is_missing(growth_rate) else growth_rate) * 100, 0, 15
    )

    return eps * (8.5 + (2 * growth_percent)) * (4.4 / (BASELINE_BOND_YIELD * 100))


def graham_number(data):
    shares_outstanding = _shares_outstanding(data, data.get("info", {}))
    eps = _eps_value(data, shares_outstanding)
    book_value_per_share = _book_value_per_share(data, shares_outstanding)

    if (
        is_missing(eps)
        or is_missing(book_value_per_share)
        or eps <= 0
        or book_value_per_share <= 0
    ):
        return None

    return math.sqrt(22.5 * eps * book_value_per_share)


def _comparable_company_analysis(data, peer_metrics_list):
    if not peer_metrics_list:
        return None

    info = data.get("info", {}) if isinstance(data.get("info"), dict) else {}
    shares_outstanding = _shares_outstanding(data, info)

    if is_missing(shares_outstanding) or shares_outstanding <= 0:
        return None

    eps = _eps_value(data, shares_outstanding)
    revenue_per_share = _per_share(income_value(data, REVENUE_KEYS), shares_outstanding)
    book_value_per_share = _book_value_per_share(data, shares_outstanding)
    ocf_per_share = _per_share(cashflow_value(data, OPERATING_CASH_FLOW_KEYS), shares_outstanding)
    normalized_fcf_per_share = _per_share(normalized_free_cash_flow(data), shares_outstanding)

    peer_multiple_map = {
        "PE": eps,
        "PS": revenue_per_share,
        "PB": book_value_per_share,
        "P_CF": ocf_per_share,
        "P_FCF": normalized_fcf_per_share,
    }

    peer_medians: dict = {}
    implied_prices: dict = {}

    for multiple_key, base_value in peer_multiple_map.items():
        # Exclude non-positive multiples from peer median to avoid corruption
        peer_values = [
            float(v)
            for peer in peer_metrics_list
            for v in [peer.get("valuation", {}).get(multiple_key)]
            if v is not None and isinstance(v, (int, float)) and float(v) > 0
        ]

        if not peer_values:
            continue

        peer_median = float(pd.Series(peer_values, dtype="float64").median())
        peer_medians[f"Peer_Median_{multiple_key}"] = peer_median

        if not is_missing(base_value) and base_value > 0:
            implied_prices[f"Implied_Price_{multiple_key}"] = peer_median * base_value

    if not implied_prices:
        return None

    implied_price = float(pd.Series(list(implied_prices.values()), dtype="float64").median())
    current_price = _latest_price(data, info)

    return {
        "Implied_Price": normalize_output(implied_price),
        "Current_Price": normalize_output(current_price),
        "Upside_Downside": normalize_output(
            safe_div(implied_price - current_price, current_price)
        ),
        **{k: normalize_output(v) for k, v in peer_medians.items()},
        **{k: normalize_output(v) for k, v in implied_prices.items()},
    }


# ─────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────

def compute_valuation_models(data, peer_metrics_list=None):
    dcf = compute_dcf(data)

    return {
        "DCF": dcf,
        "WACC": normalize_output(compute_wacc(data)),
        "Terminal_Value": _terminal_value_block(data),
        "Gordon_Growth_Model": normalize_output(_gordon_growth_model(data)),
        "Two_Stage_DDM": normalize_output(_two_stage_ddm(data)),
        "Multi_Stage_DDM": normalize_output(_multi_stage_ddm(data)),
        "Comparable_Company_Analysis": _comparable_company_analysis(data, peer_metrics_list),
        "Benjamin_Graham_Formula": normalize_output(_benjamin_graham_formula(data)),
        "Graham_Number": normalize_output(graham_number(data)),
    }