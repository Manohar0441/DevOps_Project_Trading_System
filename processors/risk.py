import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

TRADING_DAYS = 252


def _get_price_series(df: pd.DataFrame) -> pd.Series:
    """Prefer Adjusted Close for total-return accuracy; fall back to Close."""
    if "Adj Close" in df.columns:
        return df["Adj Close"].dropna().astype(float)
    if "Close" in df.columns:
        return df["Close"].dropna().astype(float)
    raise KeyError("Price data must contain either 'Adj Close' or 'Close'.")


def _strip_timezone(index: pd.Index) -> pd.Index:
    """Normalize DatetimeIndex to timezone-naive UTC so joins always succeed."""
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


def _max_drawdown(price_series: pd.Series) -> Optional[float]:
    """Maximum drawdown as a negative decimal, e.g. -0.23 for -23%."""
    price_series = _safe_series(price_series)
    if len(price_series) < 2:
        return None

    running_max = price_series.cummax()
    drawdowns = price_series / running_max - 1.0
    return float(drawdowns.min())


def _beta_from_info(info: dict) -> Optional[float]:
    """Use broker-reported beta from info dict as fallback."""
    for key in ("beta", "Beta", "beta3Year"):
        value = info.get(key)
        if value is None:
            continue
        try:
            f = float(value)
            if np.isfinite(f):
                return f
        except (TypeError, ValueError):
            continue
    return None


def compute_risk(data, benchmark_data=None) -> dict:
    """
    Minimal risk module for the swing strategy.

    Returns:
      Beta
      Volatility
      Max_Drawdown
    """
    info = data.get("info", {}) if isinstance(data.get("info"), dict) else {}

    price_df = data["price"]
    price_series = _safe_series(_get_price_series(price_df))

    # Core return stats
    asset_returns = price_series.pct_change(fill_method=None).dropna()

    volatility = None
    if len(asset_returns) >= 2:
        volatility = float(asset_returns.std(ddof=1) * np.sqrt(TRADING_DAYS))

    max_drawdown = _max_drawdown(price_series)

    # Beta: benchmark-based first, fallback to provider info if needed
    beta = None
    if benchmark_data is not None:
        benchmark_df = (
            benchmark_data["price"]
            if isinstance(benchmark_data, dict) and "price" in benchmark_data
            else benchmark_data
        )

        try:
            benchmark_series = _safe_series(_get_price_series(benchmark_df))
            benchmark_returns = benchmark_series.pct_change(fill_method=None).dropna()

            aligned = pd.concat(
                [asset_returns.rename("asset"), benchmark_returns.rename("bench")],
                axis=1,
                join="inner",
            ).dropna()

            if len(aligned) >= 30:
                asset = aligned["asset"]
                bench = aligned["bench"]

                bench_var = float(bench.var(ddof=1))
                if bench_var > 0:
                    beta = float(asset.cov(bench) / bench_var)

        except Exception as exc:  # noqa: BLE001
            logger.warning("Beta calculation failed: %s", exc)

    if beta is None:
        beta = _beta_from_info(info)

    return {
        "Beta": beta,
        "Volatility": volatility,
        "Max_Drawdown": max_drawdown,
    }
