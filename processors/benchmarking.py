import logging
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


def safe_avg(values: List[Any]) -> Optional[float]:
    cleaned = []
    for v in values:
        if v is None:
            continue
        try:
            if pd.isna(v):
                continue
        except Exception:
            pass
        if isinstance(v, (int, float)):
            cleaned.append(float(v))
    return sum(cleaned) / len(cleaned) if cleaned else None


def _relative_position(company_value: Any, benchmark_value: Any) -> Optional[str]:
    if company_value is None or benchmark_value is None:
        return None
    try:
        if company_value > benchmark_value:
            return "Above"
        if company_value < benchmark_value:
            return "Below"
        return "Equal"
    except Exception:
        return None


def compare_with_peers(
    company_metrics: Dict[str, Dict[str, Any]],
    peer_metrics_list: List[Dict[str, Dict[str, Any]]]
) -> Dict[str, Any]:
    """
    Backward-compatible peer comparison.
    Compares company metrics against peer averages.
    """
    comparison: Dict[str, Any] = {}
    sections = [
        "valuation",
        "profitability",
        "growth",
        "financial_health",
        "cashflow",
        "risk",
        "ownership"
    ]

    for section in sections:
        company_section = company_metrics.get(section, {}) or {}
        section_result: Dict[str, Any] = {}

        for key, company_value in company_section.items():
            peer_values = []
            for peer in peer_metrics_list:
                peer_value = (peer.get(section, {}) or {}).get(key)
                if peer_value is None:
                    continue
                try:
                    if not pd.isna(peer_value) and isinstance(peer_value, (int, float)):
                        peer_values.append(float(peer_value))
                except Exception:
                    continue

            peer_avg = safe_avg(peer_values)
            section_result[key] = {
                "company": company_value,
                "peer_avg": peer_avg,
                "peer_count": len(peer_values),
                "relative_position": _relative_position(company_value, peer_avg),
            }

        if section_result:
            comparison[section] = section_result

    logger.info("Peer comparison completed for %d sections.", len(comparison))
    return comparison


def peer_comparison(
    company_metrics: Dict[str, Dict[str, Any]],
    peer_metrics_list: List[Dict[str, Dict[str, Any]]]
) -> Dict[str, Any]:
    return compare_with_peers(company_metrics, peer_metrics_list)


def historical_trend_analysis(price_data: Optional[pd.DataFrame]) -> Optional[Dict[str, Any]]:
    if price_data is None or price_data.empty:
        return None

    if "Adj Close" in price_data.columns:
        prices = price_data["Adj Close"].copy()
    elif "Close" in price_data.columns:
        prices = price_data["Close"].copy()
    else:
        return None

    prices = pd.to_numeric(prices, errors="coerce").dropna()
    if len(prices) < 2:
        return None

    returns = prices.pct_change(fill_method=None).dropna()

    start_price = float(prices.iloc[0])
    end_price = float(prices.iloc[-1])

    cumulative_return = None if start_price == 0 else (end_price / start_price) - 1

    if isinstance(prices.index, pd.DatetimeIndex) and len(prices.index) >= 2:
        years = (prices.index[-1] - prices.index[0]).days / 365.25
    else:
        years = (len(prices) - 1) / 252

    cagr = None
    if years and years > 0 and start_price > 0:
        cagr = (end_price / start_price) ** (1 / years) - 1

    max_drawdown = float(((prices / prices.cummax()) - 1).min())

    result = {
        "Cumulative Return": cumulative_return,
        "Average Daily Return": float(returns.mean()) if not returns.empty else None,
        "Volatility": float(returns.std(ddof=1)) if not returns.empty else None,
        "Max Drawdown": max_drawdown,
        "CAGR": cagr,
    }

    logger.info("Historical trend analysis completed.")
    return result


def industry_benchmarking(
    company_metrics: Dict[str, Dict[str, Any]],
    industry_metrics: Dict[str, Dict[str, Any]]
) -> Dict[str, Any]:
    benchmarking: Dict[str, Any] = {}
    sections = [
        "valuation",
        "profitability",
        "growth",
        "financial_health",
        "cashflow",
        "risk",
        "ownership"
    ]

    for section in sections:
        company_section = company_metrics.get(section, {}) or {}
        industry_section = industry_metrics.get(section, {}) or {}
        section_result: Dict[str, Any] = {}

        for key, company_value in company_section.items():
            industry_value = industry_section.get(key)
            section_result[key] = {
                "company": company_value,
                "industry": industry_value,
                "relative_position": _relative_position(company_value, industry_value),
            }

        if section_result:
            benchmarking[section] = section_result

    logger.info("Industry benchmarking completed for %d sections.", len(benchmarking))
    return benchmarking


def comparative_analysis(
    company_metrics: Dict[str, Dict[str, Any]],
    peer_metrics_list: List[Dict[str, Dict[str, Any]]],
    price_data: Optional[pd.DataFrame],
    industry_metrics: Dict[str, Dict[str, Any]]
) -> Dict[str, Any]:
    return {
        "Peer Comparison": compare_with_peers(company_metrics, peer_metrics_list),
        "Historical Trend Analysis": historical_trend_analysis(price_data),
        "Industry Benchmarking": industry_benchmarking(company_metrics, industry_metrics),
    }


__all__ = [
    "compare_with_peers",
    "peer_comparison",
    "historical_trend_analysis",
    "industry_benchmarking",
    "comparative_analysis",
]