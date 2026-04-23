from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from statistics import median
from typing import Any, Dict, Iterable, List, Optional, Sequence


SUFFIX_FACTORS = {
    "K": 1_000.0,
    "M": 1_000_000.0,
    "B": 1_000_000_000.0,
    "T": 1_000_000_000_000.0,
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def safe_float(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        numeric = float(value)
        return numeric if math.isfinite(numeric) else None

    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text or text.lower() in {"n/a", "na", "none", "null", "-", "--"}:
        return None

    negative = text.startswith("(") and text.endswith(")")
    cleaned = text.strip("()").replace(",", "").replace("$", "").replace("x", "")
    cleaned = cleaned.replace("USD", "").replace("usd", "").strip()

    percent = cleaned.endswith("%")
    if percent:
        cleaned = cleaned[:-1].strip()

    suffix_match = re.search(r"([KMBT])$", cleaned, re.IGNORECASE)
    factor = 1.0
    if suffix_match:
        factor = SUFFIX_FACTORS[suffix_match.group(1).upper()]
        cleaned = cleaned[:-1].strip()

    try:
        numeric = float(cleaned)
    except ValueError:
        return None

    if negative:
        numeric *= -1
    numeric *= factor
    if percent:
        numeric /= 100.0
    return numeric if math.isfinite(numeric) else None


def normalize_ratio(value: Any) -> Optional[float]:
    numeric = safe_float(value)
    if numeric is None:
        return None
    if abs(numeric) > 1 and abs(numeric) <= 100:
        return numeric / 100.0
    return numeric


def percent_difference(left: Optional[float], right: Optional[float]) -> Optional[float]:
    if left is None or right is None:
        return None
    denominator = abs(right) if right not in (None, 0) else abs(left)
    if denominator == 0:
        return 0.0 if left == right else None
    return abs(left - right) / denominator


def consensus(values: Sequence[float]) -> Optional[float]:
    cleaned = [float(value) for value in values if value is not None]
    if not cleaned:
        return None
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return sum(cleaned) / 2.0
    return float(median(cleaned))


def first_present(mapping: Dict[str, Any], aliases: Sequence[str]) -> Any:
    for alias in aliases:
        if alias in mapping:
            return mapping[alias]
    return None


def normalize_period_label(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10]
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return text


def to_json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: to_json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [to_json_safe(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def compute_rsi(prices: Sequence[float], period: int = 14) -> Optional[float]:
    cleaned = [safe_float(price) for price in prices]
    cleaned = [price for price in cleaned if price is not None]
    if len(cleaned) <= period:
        return None

    gains: List[float] = []
    losses: List[float] = []
    for index in range(1, len(cleaned)):
        delta = cleaned[index] - cleaned[index - 1]
        gains.append(max(delta, 0.0))
        losses.append(abs(min(delta, 0.0)))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    if avg_loss == 0:
        return 100.0

    for idx in range(period, len(gains)):
        avg_gain = ((avg_gain * (period - 1)) + gains[idx]) / period
        avg_loss = ((avg_loss * (period - 1)) + losses[idx]) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))
