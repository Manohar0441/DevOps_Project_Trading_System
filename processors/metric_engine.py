from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, Tuple

import pandas as pd

from utils.financials import (
    CAPEX_KEYS,
    CASH_KEYS,
    EBITDA_KEYS,
    NET_INCOME_KEYS,
    OPERATING_CASH_FLOW_KEYS,
    OPERATING_INCOME_KEYS,
    REVENUE_KEYS,
    cashflow_value,
    current_free_cash_flow,
    income_value,
    is_missing,
    row_series,
    safe_div,
    total_debt_series,
)


DEPRECIATION_KEYS = [
    "Depreciation",
    "Depreciation & Amortization",
    "Depreciation And Amortization",
    "DepreciationAndAmortization",
    "Depreciation Amortization Depletion",
]

CAPITAL_INTENSIVE_SECTORS = {
    "Basic Materials",
    "Communication Services",
    "Energy",
    "Industrials",
    "Real Estate",
    "Utilities",
}

SAAS_EXCEPTION_TERMS = (
    "cloud",
    "cybersecurity",
    "platform",
    "saas",
    "software",
    "subscription",
)


def to_float(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool) or is_missing(value):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(numeric):
        return None
    return numeric


def safe_ratio(numerator: Any, denominator: Any) -> Optional[float]:
    left = to_float(numerator)
    right = to_float(denominator)
    if left is None or right in (None, 0):
        return None
    return safe_div(left, right)


def normalize_decimal_ratio(value: Any) -> Optional[float]:
    numeric = to_float(value)
    if numeric is None:
        return None
    if abs(numeric) > 1 and abs(numeric) <= 100:
        return numeric / 100.0
    return numeric


def clean_date_label(index_value: Any) -> Optional[str]:
    if index_value is None:
        return None
    try:
        timestamp = pd.Timestamp(index_value)
    except (TypeError, ValueError):
        return str(index_value)
    if pd.isna(timestamp):
        return None
    return timestamp.strftime("%Y-%m-%d")


def _normalize_timestamp(value: Any) -> Optional[pd.Timestamp]:
    if value is None:
        return None
    try:
        timestamp = pd.Timestamp(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(timestamp):
        return None
    if timestamp.tzinfo is not None:
        return timestamp.tz_convert("UTC").tz_localize(None)
    return timestamp


def _normalize_datetime_series(series: pd.Series) -> pd.Series:
    normalized = series.copy()
    if isinstance(normalized.index, pd.DatetimeIndex) and normalized.index.tz is not None:
        normalized.index = normalized.index.tz_convert("UTC").tz_localize(None)
    return normalized


def _series_pairs(series: pd.Series) -> list[Tuple[Any, float]]:
    if series is None or getattr(series, "empty", True):
        return []

    pairs: list[Tuple[Any, float]] = []
    for index_value, raw_value in series.items():
        numeric = to_float(raw_value)
        if numeric is None:
            continue
        pairs.append((index_value, numeric))
    return pairs


def flow_value_with_meta(
    data: Dict[str, Any],
    quarterly_key: str,
    annual_key: str,
    keys: Iterable[str],
) -> Dict[str, Any]:
    quarterly_pairs = _series_pairs(row_series(data.get(quarterly_key), list(keys)))
    if len(quarterly_pairs) >= 4:
        return {
            "value": sum(value for _, value in quarterly_pairs[:4]),
            "basis": "TTM",
            "as_of": clean_date_label(quarterly_pairs[0][0]),
            "source": f"{quarterly_key}_ttm",
        }

    annual_pairs = _series_pairs(row_series(data.get(annual_key), list(keys)))
    if annual_pairs:
        return {
            "value": annual_pairs[0][1],
            "basis": "ANNUAL",
            "as_of": clean_date_label(annual_pairs[0][0]),
            "source": f"{annual_key}_annual",
        }

    return {"value": None, "basis": None, "as_of": None, "source": "missing"}


def point_in_time_value_with_meta(
    data: Dict[str, Any],
    quarterly_key: str,
    annual_key: str,
    keys: Iterable[str],
) -> Dict[str, Any]:
    quarterly_pairs = _series_pairs(row_series(data.get(quarterly_key), list(keys)))
    if quarterly_pairs:
        return {
            "value": quarterly_pairs[0][1],
            "basis": "POINT_IN_TIME",
            "as_of": clean_date_label(quarterly_pairs[0][0]),
            "source": f"{quarterly_key}_latest",
        }

    annual_pairs = _series_pairs(row_series(data.get(annual_key), list(keys)))
    if annual_pairs:
        return {
            "value": annual_pairs[0][1],
            "basis": "POINT_IN_TIME",
            "as_of": clean_date_label(annual_pairs[0][0]),
            "source": f"{annual_key}_latest",
        }

    return {"value": None, "basis": None, "as_of": None, "source": "missing"}


def total_debt_with_meta(data: Dict[str, Any]) -> Dict[str, Any]:
    quarterly_pairs = _series_pairs(total_debt_series(data.get("quarterly_balance")))
    if quarterly_pairs:
        return {
            "value": quarterly_pairs[0][1],
            "basis": "POINT_IN_TIME",
            "as_of": clean_date_label(quarterly_pairs[0][0]),
            "source": "quarterly_balance_latest",
        }

    annual_pairs = _series_pairs(total_debt_series(data.get("balance")))
    if annual_pairs:
        return {
            "value": annual_pairs[0][1],
            "basis": "POINT_IN_TIME",
            "as_of": clean_date_label(annual_pairs[0][0]),
            "source": "balance_latest",
        }

    return {"value": None, "basis": None, "as_of": None, "source": "missing"}


def latest_price_snapshot(data: Dict[str, Any]) -> Dict[str, Any]:
    price_df = data.get("price")
    if price_df is not None and hasattr(price_df, "empty") and not price_df.empty:
        column = "Adj Close" if "Adj Close" in price_df.columns else "Close" if "Close" in price_df.columns else None
        if column is not None:
            series = price_df[column].dropna()
            if not series.empty:
                latest_index = series.index[-1]
                return {
                    "value": to_float(series.iloc[-1]),
                    "as_of": clean_date_label(latest_index),
                    "source": f"price.{column}",
                }

    info = data.get("info", {}) if isinstance(data.get("info"), dict) else {}
    for key in ("currentPrice", "regularMarketPrice", "previousClose"):
        numeric = to_float(info.get(key))
        if numeric is not None:
            return {"value": numeric, "as_of": None, "source": f"info.{key}"}

    return {"value": None, "as_of": None, "source": "missing"}


def market_cap_snapshot(data: Dict[str, Any]) -> Dict[str, Any]:
    info = data.get("info", {}) if isinstance(data.get("info"), dict) else {}
    price_snapshot = latest_price_snapshot(data)
    shares = to_float(info.get("sharesOutstanding") or info.get("impliedSharesOutstanding"))

    if price_snapshot["value"] is not None and shares is not None:
        return {
            "value": price_snapshot["value"] * shares,
            "as_of": price_snapshot["as_of"],
            "source": "price_x_shares_outstanding",
            "price_consistent": True,
        }

    fallback_market_cap = to_float(info.get("marketCap"))
    if fallback_market_cap is not None:
        return {
            "value": fallback_market_cap,
            "as_of": price_snapshot["as_of"],
            "source": "info.marketCap",
            "price_consistent": False,
        }

    return {"value": None, "as_of": price_snapshot["as_of"], "source": "missing", "price_consistent": False}


def dividend_yield_snapshot(data: Dict[str, Any]) -> Dict[str, Any]:
    price_snapshot = latest_price_snapshot(data)
    dividends = data.get("dividends")
    if dividends is None or not hasattr(dividends, "empty") or dividends.empty:
        return {
            "value": None,
            "as_of": price_snapshot["as_of"],
            "source": "missing",
            "price_consistent": price_snapshot["value"] is not None,
        }

    dividend_series = _normalize_datetime_series(dividends.dropna())
    if dividend_series.empty or price_snapshot["value"] is None:
        return {
            "value": None,
            "as_of": price_snapshot["as_of"],
            "source": "missing",
            "price_consistent": False,
        }

    anchor = _normalize_timestamp(dividend_series.index.max())
    if price_snapshot["as_of"]:
        anchor = _normalize_timestamp(price_snapshot["as_of"]) or anchor
    if anchor is None:
        return {
            "value": None,
            "as_of": price_snapshot["as_of"],
            "source": "missing",
            "price_consistent": False,
        }

    window_start = anchor - pd.Timedelta(days=365)
    current_ttm = dividend_series[
        (dividend_series.index > window_start) & (dividend_series.index <= anchor)
    ].sum()

    return {
        "value": safe_ratio(current_ttm, price_snapshot["value"]),
        "as_of": clean_date_label(anchor),
        "source": "dividends_ttm_over_price",
        "price_consistent": True,
    }


def capital_intensive_sector(data: Dict[str, Any]) -> bool:
    info = data.get("info", {}) if isinstance(data.get("info"), dict) else {}
    sector = str(info.get("sector") or "").strip()
    industry = str(info.get("industry") or "").strip().lower()
    return sector in CAPITAL_INTENSIVE_SECTORS or "telecom" in industry or "airline" in industry


def saas_exception(data: Dict[str, Any]) -> bool:
    info = data.get("info", {}) if isinstance(data.get("info"), dict) else {}
    combined = " ".join(
        str(info.get(key) or "")
        for key in ("industry", "longBusinessSummary", "shortBusinessSummary", "sector")
    ).lower()
    return any(term in combined for term in SAAS_EXCEPTION_TERMS)


def validate_ebitda(ebitda_value: Optional[float], operating_income: Optional[float]) -> Optional[float]:
    """
    Only reject EBITDA if it is missing or non-positive.
    Do not compare against operating income here.
    SaaS businesses can legitimately have EBITDA above operating income.
    """
    if ebitda_value is None:
        return None
    if not isinstance(ebitda_value, (int, float)):
        return None
    if ebitda_value <= 0:
        return None
    return ebitda_value


def ebitda_snapshot(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return a complete EBITDA snapshot.

    Priority:
    1. Explicit EBITDA from the income statement.
    2. Reconstructed EBITDA = operating income + depreciation/amortization.
    """
    explicit_ebitda = to_float(income_value(data, EBITDA_KEYS))
    if explicit_ebitda is not None:
        source_flow = flow_value_with_meta(data, "quarterly_income", "income", EBITDA_KEYS)
        return {
            "value": explicit_ebitda,
            "source": source_flow["source"],
            "basis": source_flow["basis"],
            "as_of": source_flow["as_of"],
            "operating_income": to_float(income_value(data, OPERATING_INCOME_KEYS)),
            "depreciation": None,
            "validated": True,
            "validation_reason": "explicit EBITDA from income statement",
        }

    operating_income_meta = flow_value_with_meta(
        data, "quarterly_income", "income", OPERATING_INCOME_KEYS
    )
    depreciation_meta = flow_value_with_meta(
        data, "quarterly_cashflow", "cashflow", DEPRECIATION_KEYS
    )

    operating_income = to_float(operating_income_meta["value"])
    depreciation = to_float(depreciation_meta["value"])

    reconstructed = None
    if operating_income is not None and depreciation is not None:
        reconstructed = operating_income + abs(depreciation)

    validated_value = validate_ebitda(reconstructed, operating_income)

    return {
        "value": validated_value,
        "source": "reconstructed_from_operating_income_plus_depreciation"
        if validated_value is not None
        else "missing",
        "basis": operating_income_meta["basis"] or depreciation_meta["basis"],
        "as_of": operating_income_meta["as_of"] or depreciation_meta["as_of"],
        "operating_income": operating_income,
        "depreciation": depreciation,
        "validated": validated_value is not None,
        "validation_reason": (
            "reconstructed EBITDA accepted"
            if validated_value is not None
            else "EBITDA could not be reconstructed"
        ),
    }


def core_flow_snapshots(data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {
        "revenue": flow_value_with_meta(data, "quarterly_income", "income", REVENUE_KEYS),
        "net_income": flow_value_with_meta(data, "quarterly_income", "income", NET_INCOME_KEYS),
        "operating_cash_flow": flow_value_with_meta(data, "quarterly_cashflow", "cashflow", OPERATING_CASH_FLOW_KEYS),
        "capex": flow_value_with_meta(data, "quarterly_cashflow", "cashflow", CAPEX_KEYS),
    }


def current_fcf_snapshot(data: Dict[str, Any]) -> Dict[str, Any]:
    snapshots = core_flow_snapshots(data)
    operating_cash_flow = to_float(snapshots["operating_cash_flow"]["value"])
    capex = to_float(snapshots["capex"]["value"])
    current_fcf = to_float(current_free_cash_flow(data))

    if current_fcf is not None:
        return {
            "value": current_fcf,
            "basis": snapshots["operating_cash_flow"]["basis"],
            "as_of": snapshots["operating_cash_flow"]["as_of"] or snapshots["capex"]["as_of"],
            "source": "ttm_ocf_minus_capex",
        }

    if operating_cash_flow is not None and capex is not None:
        return {
            "value": operating_cash_flow - abs(capex),
            "basis": snapshots["operating_cash_flow"]["basis"],
            "as_of": snapshots["operating_cash_flow"]["as_of"] or snapshots["capex"]["as_of"],
            "source": "flow_snapshot_rebuild",
        }

    return {"value": None, "basis": None, "as_of": None, "source": "missing"}