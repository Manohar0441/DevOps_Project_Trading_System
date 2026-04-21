import numpy as np
import pandas as pd

TRADING_DAYS = 252


def _get_price_series(df: pd.DataFrame) -> pd.Series:
    """
    Prefer Adjusted Close for total-return accuracy.
    Fallback to Close if Adjusted Close is not available.
    """
    if "Adj Close" in df.columns:
        return df["Adj Close"].dropna().astype(float)
    if "Close" in df.columns:
        return df["Close"].dropna().astype(float)
    raise KeyError("Price data must contain either 'Adj Close' or 'Close'.")


def _annualized_cagr(price_series: pd.Series) -> float | None:
    price_series = price_series.dropna()
    if len(price_series) < 2:
        return None

    start_price = float(price_series.iloc[0])
    end_price = float(price_series.iloc[-1])

    if start_price <= 0:
        return None

    if isinstance(price_series.index, pd.DatetimeIndex) and len(price_series.index) >= 2:
        years = (price_series.index[-1] - price_series.index[0]).days / 365.25
        if years <= 0:
            return None
    else:
        years = (len(price_series) - 1) / TRADING_DAYS
        if years <= 0:
            return None

    return (end_price / start_price) ** (1 / years) - 1


def compute_risk(data, benchmark_data=None, risk_free_rate=0.0, periods_per_year=TRADING_DAYS):
    """
    Returns:
      Beta
      Standard Deviation
      Coefficient of Variation
      Sharpe Ratio
      Sortino Ratio
      Information Ratio
      Jensen's Alpha
      Treynor Ratio
      Total Shareholder Return
      Cumulative Return
      CAGR

    Parameters:
      data: dict with key "price" -> DataFrame containing Close / Adj Close
      benchmark_data: optional DataFrame or dict-like with benchmark prices
      risk_free_rate: annual risk-free rate as decimal (example: 0.06 for 6%)
      periods_per_year: 252 for daily data, 52 for weekly, 12 for monthly
    """
    price_df = data["price"]
    price_series = _get_price_series(price_df)

    # Main asset returns
    asset_returns = price_series.pct_change(fill_method=None).dropna()

    # Core statistics
    mean_return = asset_returns.mean()
    std_dev = asset_returns.std(ddof=1)

    if std_dev is not None and std_dev != 0:
        coeff_variation = std_dev / abs(mean_return) if mean_return != 0 else None
    else:
        coeff_variation = None

    # Risk-free rate converted to periodic rate
    rf_periodic = (1 + risk_free_rate) ** (1 / periods_per_year) - 1

    # Sharpe Ratio
    sharpe_ratio = None
    if std_dev is not None and std_dev != 0:
        sharpe_ratio = ((mean_return - rf_periodic) / std_dev) * np.sqrt(periods_per_year)

    # Sortino Ratio
    downside_returns = asset_returns[asset_returns < rf_periodic]
    downside_deviation = None
    sortino_ratio = None
    if len(downside_returns) > 0:
        downside_deviation = np.sqrt(np.mean((downside_returns - rf_periodic) ** 2))
        if downside_deviation != 0:
            sortino_ratio = ((mean_return - rf_periodic) / downside_deviation) * np.sqrt(periods_per_year)

    # Return-based metrics
    cumulative_return = None
    total_shareholder_return = None
    cagr = _annualized_cagr(price_series)

    if len(price_series) >= 2:
        start_price = float(price_series.iloc[0])
        end_price = float(price_series.iloc[-1])

        if start_price != 0:
            cumulative_return = (end_price / start_price) - 1

            # TSR:
            # If adjusted close exists, it already captures dividends/splits better.
            # If only close exists, add dividends if available.
            if "Adj Close" in price_df.columns:
                adj_series = price_df["Adj Close"].dropna().astype(float)
                if len(adj_series) >= 2 and float(adj_series.iloc[0]) != 0:
                    total_shareholder_return = (float(adj_series.iloc[-1]) / float(adj_series.iloc[0])) - 1
            else:
                dividends = 0.0
                if "Dividends" in price_df.columns:
                    dividends = float(price_df["Dividends"].fillna(0).sum())
                total_shareholder_return = ((end_price - start_price) + dividends) / start_price

    # Benchmark-dependent metrics
    beta = None
    information_ratio = None
    jensens_alpha = None
    treynor_ratio = None

    if benchmark_data is not None:
        if isinstance(benchmark_data, dict) and "price" in benchmark_data:
            benchmark_df = benchmark_data["price"]
        else:
            benchmark_df = benchmark_data

        benchmark_series = _get_price_series(benchmark_df)
        benchmark_returns = benchmark_series.pct_change(fill_method=None).dropna()

        aligned = pd.concat(
            [asset_returns.rename("asset"), benchmark_returns.rename("bench")],
            axis=1,
            join="inner"
        ).dropna()

        if len(aligned) >= 2:
            asset = aligned["asset"]
            bench = aligned["bench"]

            bench_var = bench.var(ddof=1)
            if bench_var != 0:
                beta = asset.cov(bench) / bench_var

            # Information Ratio
            active_return = asset - bench
            active_std = active_return.std(ddof=1)
            if active_std != 0:
                information_ratio = active_return.mean() / active_std * np.sqrt(periods_per_year)

            # Annualized returns for alpha and treynor
            asset_cagr = _annualized_cagr(price_series)
            bench_cagr = _annualized_cagr(benchmark_series)

            if beta is not None and asset_cagr is not None and bench_cagr is not None:
                jensens_alpha = asset_cagr - (risk_free_rate + beta * (bench_cagr - risk_free_rate))

                excess_asset_return = asset_cagr - risk_free_rate
                if beta != 0:
                    treynor_ratio = excess_asset_return / beta

    return {
        "Beta": beta,
        "Standard Deviation": std_dev,
        "Coefficient of Variation": coeff_variation,
        "Sharpe Ratio": sharpe_ratio,
        "Sortino Ratio": sortino_ratio,
        "Information Ratio": information_ratio,
        "Jensen's Alpha": jensens_alpha,
        "Treynor Ratio": treynor_ratio,
        "Total Shareholder Return": total_shareholder_return,
        "Cumulative Return": cumulative_return,
        "CAGR": cagr
    }