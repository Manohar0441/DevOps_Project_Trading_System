import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

TRADING_DAYS = 252

# Metrics where only strictly positive values are meaningful.
# A negative P/E or negative EV/EBITDA is not a "cheap" stock — it means the
# denominator is negative and the ratio should be excluded from averages.
_POSITIVE_ONLY_METRICS = {
    "PE_Ratio", "PE Ratio", "Forward_PE", "Forward PE",
    "PB_Ratio", "PB Ratio", "PS_Ratio", "PS Ratio",
    "EV_EBITDA", "EV/EBITDA", "EV_Revenue", "EV/Revenue",
    "PEG_Ratio", "PEG Ratio",
    "Price_to_FCF", "Price to FCF",
    "EV_FCF", "EV/FCF",
}


# ─────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────

def _get_price_series(df: pd.DataFrame) -> pd.Series:
    """Prefer Adjusted Close (total-return accuracy); fall back to Close."""
    if "Adj Close" in df.columns:
        return df["Adj Close"].dropna().astype(float)
    if "Close" in df.columns:
        return df["Close"].dropna().astype(float)
    raise KeyError("Price data must contain either 'Adj Close' or 'Close'.")


def _strip_timezone(index: pd.Index) -> pd.Index:
    """Normalise a DatetimeIndex to timezone-naive UTC so joins always succeed.

    Timezone mismatches between asset and benchmark indices (one tz-aware, one
    tz-naive) silently produce an empty inner-join, causing beta / IR / alpha
    / Treynor to all return None.  Stripping tz from both sides before the
    join prevents this.
    """
    if isinstance(index, pd.DatetimeIndex) and index.tz is not None:
        return index.tz_convert("UTC").tz_localize(None)
    return index


def _safe_series(series: pd.Series) -> pd.Series:
    """Return a timezone-naive, float, non-null Series sorted by date."""
    series = series.copy()
    series.index = _strip_timezone(series.index)
    return series.sort_index().dropna().astype(float)


def _annualized_cagr(price_series: pd.Series) -> Optional[float]:
    price_series = _safe_series(price_series)
    if len(price_series) < 2:
        return None

    start_price = float(price_series.iloc[0])
    end_price = float(price_series.iloc[-1])
    if start_price <= 0:
        return None

    if isinstance(price_series.index, pd.DatetimeIndex):
        years = (price_series.index[-1] - price_series.index[0]).days / 365.25
    else:
        years = (len(price_series) - 1) / TRADING_DAYS

    if years <= 0:
        return None

    return (end_price / start_price) ** (1 / years) - 1


def _beta_from_info(info: dict) -> Optional[float]:
    """Use the broker-reported beta from the info dict as a fallback."""
    for key in ("beta", "Beta", "beta3Year"):
        value = info.get(key)
        if value is not None:
            try:
                f = float(value)
                if np.isfinite(f):
                    return f
            except (TypeError, ValueError):
                continue
    return None


# ─────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────

def compute_risk(
    data,
    benchmark_data=None,
    risk_free_rate: float = 0.0,
    periods_per_year: int = TRADING_DAYS,
):
    """
    Returns a dict with:
      Beta, Standard Deviation, Coefficient of Variation,
      Sharpe Ratio, Sortino Ratio, Information Ratio,
      Jensen's Alpha, Treynor Ratio,
      Total Shareholder Return, Cumulative Return, CAGR

    Parameters
    ----------
    data              : dict  – must contain key "price" -> DataFrame (Close / Adj Close)
    benchmark_data    : optional DataFrame or dict with "price" key
    risk_free_rate    : annual rate as decimal  (e.g. 0.05 for 5 %)
    periods_per_year  : 252 daily | 52 weekly | 12 monthly
    """
    info = data.get("info", {}) if isinstance(data.get("info"), dict) else {}

    price_df = data["price"]
    price_series = _safe_series(_get_price_series(price_df))

    # ── Core return statistics ────────────────────────────────────────────────
    asset_returns = price_series.pct_change(fill_method=None).dropna()

    mean_return = float(asset_returns.mean())
    std_dev = float(asset_returns.std(ddof=1))

    coeff_variation = (
        (std_dev / abs(mean_return)) if (mean_return != 0 and std_dev > 0) else None
    )

    # ── Risk-free periodic rate ───────────────────────────────────────────────
    rf_periodic = (1 + risk_free_rate) ** (1 / periods_per_year) - 1

    # ── Sharpe Ratio ─────────────────────────────────────────────────────────
    sharpe_ratio = (
        ((mean_return - rf_periodic) / std_dev) * np.sqrt(periods_per_year)
        if std_dev > 0
        else None
    )

    # ── Sortino Ratio ─────────────────────────────────────────────────────────
    downside_returns = asset_returns[asset_returns < rf_periodic]
    sortino_ratio = None
    if len(downside_returns) > 0:
        downside_deviation = float(
            np.sqrt(np.mean((downside_returns - rf_periodic) ** 2))
        )
        if downside_deviation > 0:
            sortino_ratio = (
                (mean_return - rf_periodic) / downside_deviation
            ) * np.sqrt(periods_per_year)

    # ── Return-based metrics ──────────────────────────────────────────────────
    cagr = _annualized_cagr(price_series)
    cumulative_return = None
    total_shareholder_return = None

    if len(price_series) >= 2:
        start_price = float(price_series.iloc[0])
        end_price = float(price_series.iloc[-1])

        if start_price > 0:
            cumulative_return = (end_price / start_price) - 1

            if "Adj Close" in price_df.columns:
                adj = _safe_series(price_df["Adj Close"])
                if len(adj) >= 2 and float(adj.iloc[0]) > 0:
                    total_shareholder_return = (float(adj.iloc[-1]) / float(adj.iloc[0])) - 1
            else:
                dividends = (
                    float(price_df["Dividends"].fillna(0).sum())
                    if "Dividends" in price_df.columns
                    else 0.0
                )
                total_shareholder_return = (
                    (end_price - start_price) + dividends
                ) / start_price

    # ── Benchmark-dependent metrics ───────────────────────────────────────────
    # Primary: calculate from price series alignment.
    # Fallback for beta only: use broker-reported value from info dict.
    beta = None
    information_ratio = None
    jensens_alpha = None
    treynor_ratio = None

    if benchmark_data is not None:
        benchmark_df = (
            benchmark_data["price"]
            if isinstance(benchmark_data, dict) and "price" in benchmark_data
            else benchmark_data
        )

        try:
            benchmark_series = _safe_series(_get_price_series(benchmark_df))
            benchmark_returns = benchmark_series.pct_change(fill_method=None).dropna()

            # Inner join on date index — both series are now tz-naive so this
            # will not silently produce an empty DataFrame.
            aligned = pd.concat(
                [asset_returns.rename("asset"), benchmark_returns.rename("bench")],
                axis=1,
                join="inner",
            ).dropna()

            if len(aligned) >= 30:  # require at least 30 overlapping periods
                asset = aligned["asset"]
                bench = aligned["bench"]

                bench_var = float(bench.var(ddof=1))
                if bench_var > 0:
                    beta = float(asset.cov(bench) / bench_var)

                # Information Ratio (annualised)
                active_return = asset - bench
                active_std = float(active_return.std(ddof=1))
                if active_std > 0:
                    information_ratio = (
                        float(active_return.mean()) / active_std
                    ) * np.sqrt(periods_per_year)

                # Jensen's Alpha and Treynor (use annualised CAGR)
                asset_cagr = _annualized_cagr(price_series)
                bench_cagr = _annualized_cagr(benchmark_series)

                if beta is not None and asset_cagr is not None and bench_cagr is not None:
                    jensens_alpha = asset_cagr - (
                        risk_free_rate + beta * (bench_cagr - risk_free_rate)
                    )
                    excess = asset_cagr - risk_free_rate
                    if beta != 0:
                        treynor_ratio = excess / beta
            else:
                logger.warning(
                    "Only %d overlapping periods between asset and benchmark — "
                    "skipping benchmark metrics.",
                    len(aligned),
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Benchmark metric calculation failed: %s", exc)

    # Fallback: broker-reported beta from info dict when calculation not possible.
    if beta is None:
        beta = _beta_from_info(info)
        if beta is not None:
            logger.debug("Beta sourced from info dict (broker-reported).")

    return {
        "Beta": beta,
        "Standard_Deviation": std_dev,
        "Coefficient_of_Variation": coeff_variation,
        "Sharpe_Ratio": sharpe_ratio,
        "Sortino_Ratio": sortino_ratio,
        "Information_Ratio": information_ratio,
        "Jensens_Alpha": jensens_alpha,
        "Treynor_Ratio": treynor_ratio,
        "Total_Shareholder_Return": total_shareholder_return,
        "Cumulative_Return": cumulative_return,
        "CAGR": cagr,
    }