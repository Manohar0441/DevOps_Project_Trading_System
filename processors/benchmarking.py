import logging
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Metric classification
# ─────────────────────────────────────────────

# Valuation and coverage ratios where a negative value means the denominator
# is negative (losses), not that the stock is "cheap".  Including negatives
# in a peer average would pull the mean down and misrepresent the group.
_RATIO_POSITIVE_ONLY = {
    # Valuation multiples
    "PE_Ratio", "PE Ratio", "Forward_PE", "Forward PE",
    "PB_Ratio", "PB Ratio", "PS_Ratio", "PS Ratio",
    "PEG_Ratio", "PEG Ratio",
    "EV_EBITDA", "EV/EBITDA",
    "EV_Revenue", "EV/Revenue",
    "EV_FCF", "EV/FCF",
    "Price_to_FCF", "Price to FCF",
    # Coverage / efficiency
    "Interest_Coverage", "Interest Coverage",
    "Asset_Turnover", "Asset Turnover",
    "Inventory_Turnover", "Inventory Turnover",
    "Receivables_Turnover", "Receivables Turnover",
    # Margin ratios — a negative margin is meaningful but outliers
    # (e.g. -400 %) distort averages; clip at zero for peer mean.
    "Gross_Margin", "Gross Margin",
    "Operating_Margin", "Operating Margin",
    "Net_Margin", "Net Margin",
    "EBITDA_Margin", "EBITDA Margin",
    "FCF_Margin", "FCF Margin",
}


def _is_valid_peer_value(key: str, value: Any) -> bool:
    """Return True only when the value is a finite number and meaningful for
    this metric.

    For ratio / margin metrics, negative values are excluded from peer
    averages because they indicate a loss-making denominator and would
    corrupt the group mean (e.g. one peer with PE = -50 dragging the
    average to near-zero even when the rest trade at PE = 25).
    """
    if value is None:
        return False
    if not isinstance(value, (int, float)):
        return False
    try:
        if pd.isna(value):
            return False
    except Exception:
        return False
    if not pd.api.types.is_float(float(value)) or not pd.notna(float(value)):
        return False

    if key in _RATIO_POSITIVE_ONLY and float(value) <= 0:
        return False

    return True


def safe_avg(values: List[Any], key: str = "") -> Optional[float]:
    """Mean of valid peer values, with metric-aware filtering."""
    cleaned = [
        float(v)
        for v in values
        if _is_valid_peer_value(key, v)
    ]
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


# ─────────────────────────────────────────────
# Peer comparison
# ─────────────────────────────────────────────

def compare_with_peers(
    company_metrics: Dict[str, Dict[str, Any]],
    peer_metrics_list: List[Dict[str, Dict[str, Any]]],
) -> Dict[str, Any]:
    """Compare company metrics against peer averages, section by section.

    Negative / invalid ratio values are excluded from the peer average so
    that loss-making peers do not corrupt multiples like P/E or EV/EBITDA.
    """
    comparison: Dict[str, Any] = {}
    sections = [
        "valuation",
        "profitability",
        "growth",
        "financial_health",
        "cashflow",
        "risk",
        "ownership",
    ]

    for section in sections:
        company_section = company_metrics.get(section, {}) or {}
        section_result: Dict[str, Any] = {}

        for key, company_value in company_section.items():
            raw_peer_values = [
                (peer.get(section, {}) or {}).get(key)
                for peer in peer_metrics_list
            ]
            # Collect all raw values for count reporting (before validity filter)
            valid_peer_values = [
                float(v) for v in raw_peer_values if _is_valid_peer_value(key, v)
            ]
            excluded_count = len(
                [v for v in raw_peer_values if v is not None]
            ) - len(valid_peer_values)

            peer_avg = safe_avg(raw_peer_values, key=key)

            entry: Dict[str, Any] = {
                "company": company_value,
                "peer_avg": peer_avg,
                "peer_count": len(valid_peer_values),
                "relative_position": _relative_position(company_value, peer_avg),
            }
            if excluded_count > 0:
                entry["peers_excluded_invalid"] = excluded_count

            section_result[key] = entry

        if section_result:
            comparison[section] = section_result

    logger.info("Peer comparison completed for %d sections.", len(comparison))
    return comparison


# ─────────────────────────────────────────────
# Historical trend analysis
# ─────────────────────────────────────────────

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
        "Cumulative_Return": cumulative_return,
        "Average_Daily_Return": float(returns.mean()) if not returns.empty else None,
        "Volatility": float(returns.std(ddof=1)) if not returns.empty else None,
        "Max_Drawdown": max_drawdown,
        "CAGR": cagr,
    }

    logger.info("Historical trend analysis completed.")
    return result


# ─────────────────────────────────────────────
# Industry benchmarking
# ─────────────────────────────────────────────

def industry_benchmarking(
    company_metrics: Dict[str, Dict[str, Any]],
    industry_metrics: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Compare each metric to the industry benchmark value.

    Industry metrics are treated as externally supplied medians / means,
    so no additional filtering is applied — they should already be clean.
    """
    benchmarking: Dict[str, Any] = {}
    sections = [
        "valuation",
        "profitability",
        "growth",
        "financial_health",
        "cashflow",
        "risk",
        "ownership",
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


# ─────────────────────────────────────────────
# Composite entry point
# ─────────────────────────────────────────────

def comparative_analysis(
    company_metrics: Dict[str, Dict[str, Any]],
    peer_metrics_list: List[Dict[str, Dict[str, Any]]],
    price_data: Optional[pd.DataFrame],
    industry_metrics: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "Peer_Comparison": compare_with_peers(company_metrics, peer_metrics_list),
        "Historical_Trend_Analysis": historical_trend_analysis(price_data),
        "Industry_Benchmarking": industry_benchmarking(company_metrics, industry_metrics),
    }


# Backward-compatible alias
def peer_comparison(
    company_metrics: Dict[str, Dict[str, Any]],
    peer_metrics_list: List[Dict[str, Dict[str, Any]]],
) -> Dict[str, Any]:
    return compare_with_peers(company_metrics, peer_metrics_list)


__all__ = [
    "compare_with_peers",
    "peer_comparison",
    "historical_trend_analysis",
    "industry_benchmarking",
    "comparative_analysis",
]