import math
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import pandas as pd
import yfinance as yf


# =============================================================================
# CONFIG
# =============================================================================

SECTOR_KEY_MAP = {
    "Technology": "technology",
    "Healthcare": "healthcare",
    "Financial Services": "financial-services",
    "Energy": "energy",
    "Consumer Cyclical": "consumer-cyclical",
    "Consumer Defensive": "consumer-defensive",
    "Industrials": "industrials",
    "Utilities": "utilities",
    "Real Estate": "real-estate",
    "Basic Materials": "basic-materials",
    "Communication Services": "communication-services",
    "Services": "services",
}

SOURCE_WEIGHTS = {
    "industry_top": 8.0,
    "sector_top": 4.0,
    "etf_holding": 1.0,
}

DISALLOWED_EXCHANGE_MARKERS = {
    "OTC",
    "OTCM",
    "OTCQB",
    "OTCQX",
    "PNK",
    "GREY",
}

DISALLOWED_SYMBOL_SUFFIXES = (
    "-P",
    "-WS",
    "-WT",
    "-RT",
    ".WS",
    ".WT",
    ".RT",
)

TEXT_STOPWORDS = {
    "about",
    "after",
    "also",
    "among",
    "and",
    "business",
    "company",
    "companies",
    "develops",
    "for",
    "from",
    "global",
    "holdings",
    "inc",
    "including",
    "its",
    "offers",
    "operations",
    "plc",
    "products",
    "provides",
    "services",
    "solutions",
    "systems",
    "that",
    "the",
    "through",
    "using",
    "with",
    "worldwide",
}

MINIMUM_PEER_SCORE = 46.0
PRIMARY_SCORE_RATIO = 0.68
RELAXED_SCORE_RATIO = 0.55
RELAXED_MINIMUM_PEER_SCORE = 40.0
MAX_SIZE_RATIO = 40.0
MAX_WORKERS = 8


# =============================================================================
# SMALL HELPERS
# =============================================================================

def _clean_symbol(value: Any) -> Optional[str]:
    if value is None:
        return None

    s = str(value).strip().upper()
    if not s or s in {"NAN", "NONE", "NULL"}:
        return None

    if len(s) > 15 or any(ch.isspace() for ch in s):
        return None

    return s


def _unique_preserve_order(items: Iterable[str]) -> List[str]:
    seen: Set[str] = set()
    out: List[str] = []

    for item in items:
        item = _clean_symbol(item)
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)

    return out


def _first_non_empty(*values: Any) -> Optional[str]:
    for value in values:
        if value is None:
            continue

        text = str(value).strip()
        if text:
            return text

    return None


def _as_float(value: Any) -> Optional[float]:
    if value is None:
        return None

    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(numeric):
        return None

    return numeric


def _normalize_sector_key(sector: Optional[str]) -> Optional[str]:
    if not sector:
        return None

    sector = sector.strip()
    return SECTOR_KEY_MAP.get(sector, sector.lower().replace(" ", "-"))


def _extract_symbols(obj: Any) -> List[str]:
    """
    Extract ticker symbols from DataFrames, Series, dicts, lists, tuples, or scalars.
    Works defensively because yfinance responses can vary by endpoint/version.
    """
    symbols: List[str] = []

    if obj is None:
        return symbols

    if isinstance(obj, pd.DataFrame):
        candidate_cols = [
            "symbol",
            "Symbol",
            "ticker",
            "Ticker",
            "companySymbol",
            "company_symbol",
            "holdingSymbol",
            "holding_symbol",
        ]
        for col in candidate_cols:
            if col in obj.columns:
                symbols.extend(obj[col].tolist())

        if not symbols and obj.index is not None:
            symbols.extend([str(x) for x in obj.index.tolist()])

        return [_clean_symbol(x) for x in symbols if _clean_symbol(x)]

    if isinstance(obj, pd.Series):
        symbols.extend([str(x) for x in obj.tolist()])
        return [_clean_symbol(x) for x in symbols if _clean_symbol(x)]

    if isinstance(obj, dict):
        for key in ("symbol", "Symbol", "ticker", "Ticker", "holdings", "data"):
            if key in obj:
                symbols.extend(_extract_symbols(obj[key]))

        if not symbols:
            symbols.extend(list(obj.keys()))

        return [_clean_symbol(x) for x in symbols if _clean_symbol(x)]

    if isinstance(obj, (list, tuple, set)):
        for item in obj:
            if isinstance(item, dict):
                symbols.extend(_extract_symbols(item))
            else:
                symbols.append(str(item))

        return [_clean_symbol(x) for x in symbols if _clean_symbol(x)]

    return [_clean_symbol(obj)] if _clean_symbol(obj) else []


def _tokenize_text(*values: Any) -> Set[str]:
    tokens: Set[str] = set()

    for value in values:
        if not value:
            continue

        for token in re.findall(r"[A-Za-z][A-Za-z0-9&-]{2,}", str(value).lower()):
            token = token.strip("-")
            if not token or token in TEXT_STOPWORDS:
                continue
            tokens.add(token)

    return tokens


def _jaccard_similarity(left: Set[str], right: Set[str]) -> float:
    if not left or not right:
        return 0.0

    union = left | right
    if not union:
        return 0.0

    return len(left & right) / len(union)


def _bounded_similarity(left: Optional[float], right: Optional[float], scale: float) -> float:
    if left is None or right is None or scale <= 0:
        return 0.0

    diff = abs(float(left) - float(right))
    return max(0.0, 1.0 - min(diff / scale, 1.0))


def _ratio_band(left: Optional[float], right: Optional[float]) -> Optional[float]:
    if left is None or right is None or left <= 0 or right <= 0:
        return None

    higher = max(float(left), float(right))
    lower = min(float(left), float(right))
    if lower <= 0:
        return None

    return higher / lower


def _log_similarity(left: Optional[float], right: Optional[float]) -> float:
    """
    Returns 1.0 when equal, approaching 0 as values diverge.
    Uses log scale for market cap and revenue similarity.
    """
    if left is None or right is None:
        return 0.0

    try:
        left = float(left)
        right = float(right)
        if left <= 0 or right <= 0:
            return 0.0

        diff = abs(math.log(left) - math.log(right))
        return max(0.0, 1.0 - min(diff / math.log(10), 1.0))
    except Exception:
        return 0.0


def _issuer_key(profile: Dict[str, Any]) -> str:
    name = _first_non_empty(profile.get("long_name"), profile.get("symbol")) or ""
    normalized = name.lower()
    normalized = re.sub(r"\bclass\s+[a-z0-9]+\b", " ", normalized)
    normalized = re.sub(r"\bseries\s+[a-z0-9]+\b", " ", normalized)
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized).strip()
    return normalized or str(profile.get("symbol") or "").upper()


def _contains_disallowed_exchange(exchange: Optional[str]) -> bool:
    if not exchange:
        return False

    exchange_text = str(exchange).upper()
    return any(marker in exchange_text for marker in DISALLOWED_EXCHANGE_MARKERS)


def _is_common_stock_symbol(symbol: Optional[str]) -> bool:
    symbol = _clean_symbol(symbol)
    if not symbol:
        return False

    if any(marker in symbol for marker in ("^", "/", "=")):
        return False

    return not any(symbol.endswith(suffix) for suffix in DISALLOWED_SYMBOL_SUFFIXES)


def _add_symbols_with_source(target: Dict[str, Set[str]], source: str, symbols: Iterable[str]) -> None:
    for symbol in _unique_preserve_order(symbols):
        target.setdefault(symbol, set()).add(source)


# =============================================================================
# YFINANCE LOOKUPS
# =============================================================================

@lru_cache(maxsize=2048)
def get_ticker_info(symbol: str) -> Dict[str, Any]:
    """
    Cached info fetch. yfinance info can be incomplete, so all access is defensive.
    """
    symbol = _clean_symbol(symbol)
    if not symbol:
        return {}

    try:
        return yf.Ticker(symbol).info or {}
    except Exception:
        return {}


def get_company_profile(symbol: str) -> Dict[str, Any]:
    info = get_ticker_info(symbol)

    sector = _first_non_empty(info.get("sector"), info.get("sectorName"))
    industry = _first_non_empty(
        info.get("industry"),
        info.get("industryName"),
        info.get("industryDisp"),
    )
    sector_key = _first_non_empty(info.get("sectorKey"), _normalize_sector_key(sector))
    industry_key = _first_non_empty(info.get("industryKey"))

    quote_type = _first_non_empty(info.get("quoteType"))
    market_cap = _as_float(info.get("marketCap"))
    revenue = _as_float(info.get("totalRevenue"))
    gross_margin = _as_float(info.get("grossMargins"))
    operating_margin = _as_float(info.get("operatingMargins"))
    beta = _as_float(info.get("beta"))

    long_name = _first_non_empty(info.get("longName"), info.get("shortName"), symbol)
    summary = _first_non_empty(
        info.get("longBusinessSummary"),
        info.get("description"),
        info.get("businessSummary"),
    )

    country = _first_non_empty(info.get("country"))
    exchange = _first_non_empty(info.get("exchange"), info.get("fullExchangeName"))
    currency = _first_non_empty(info.get("financialCurrency"), info.get("currency"))

    industry_tokens = _tokenize_text(industry, industry_key)
    business_tokens = _tokenize_text(long_name, industry, summary)

    return {
        "symbol": _clean_symbol(symbol),
        "sector": sector,
        "industry": industry,
        "sector_key": sector_key,
        "industry_key": industry_key,
        "quote_type": quote_type,
        "market_cap": market_cap,
        "revenue": revenue,
        "gross_margin": gross_margin,
        "operating_margin": operating_margin,
        "beta": beta,
        "country": country,
        "exchange": exchange,
        "currency": currency,
        "long_name": long_name,
        "industry_tokens": industry_tokens,
        "business_tokens": business_tokens,
        "info": info,
    }


def get_sector_obj(sector_key: Optional[str]):
    if not sector_key:
        return None

    try:
        return yf.Sector(sector_key)
    except Exception:
        return None


def get_industry_obj(industry_key: Optional[str]):
    if not industry_key:
        return None

    try:
        return yf.Industry(industry_key)
    except Exception:
        return None


# =============================================================================
# UNIVERSE BUILDERS
# =============================================================================

def get_universe_from_sector(company_profile: Dict[str, Any]) -> List[str]:
    """
    Secondary universe: sector leaders.
    """
    sector_obj = get_sector_obj(company_profile.get("sector_key"))
    if not sector_obj:
        return []

    candidates: List[str] = []
    try:
        candidates.extend(_extract_symbols(getattr(sector_obj, "top_companies", None)))
    except Exception:
        pass

    return _unique_preserve_order(candidates)


def get_universe_from_industry(company_profile: Dict[str, Any]) -> List[str]:
    """
    Primary universe: industry leaders and top performers.
    We only pull growth names when the industry universe is too thin.
    """
    industry_obj = get_industry_obj(company_profile.get("industry_key"))
    if not industry_obj:
        return []

    candidates: List[str] = []
    for attr in ("top_companies", "top_performing_companies"):
        try:
            candidates.extend(_extract_symbols(getattr(industry_obj, attr, None)))
        except Exception:
            continue

    deduped = _unique_preserve_order(candidates)
    if len(deduped) >= 6:
        return deduped

    try:
        candidates.extend(_extract_symbols(getattr(industry_obj, "top_growth_companies", None)))
    except Exception:
        pass

    return _unique_preserve_order(candidates)


def get_universe_from_etf_fallback(sector: Optional[str], limit_holdings: int = 10) -> List[str]:
    """
    Last-resort fallback: use sector ETF top holdings.
    """
    sector_key = _normalize_sector_key(sector)
    if not sector_key:
        return []

    sector_obj = get_sector_obj(sector_key)
    if not sector_obj:
        return []

    etf_candidates: List[str] = []
    try:
        etf_candidates.extend(_extract_symbols(getattr(sector_obj, "top_etfs", None)))
    except Exception:
        pass

    etf_candidates = _unique_preserve_order(etf_candidates)
    holdings: List[str] = []

    for etf in etf_candidates[:5]:
        try:
            funds_data = yf.Ticker(etf).funds_data
            top_holdings = getattr(funds_data, "top_holdings", None)
            holdings.extend(_extract_symbols(top_holdings))
            if len(holdings) >= limit_holdings * 3:
                break
        except Exception:
            continue

    return _unique_preserve_order(holdings)


def build_peer_universe(ticker: str) -> Tuple[Dict[str, Any], Dict[str, Set[str]]]:
    """
    Build a candidate universe with source labels so the scorer can trust
    industry-derived names more than loose ETF fallbacks.
    """
    profile = get_company_profile(ticker)

    sources: Dict[str, Set[str]] = {}
    _add_symbols_with_source(sources, "industry_top", get_universe_from_industry(profile))
    _add_symbols_with_source(sources, "sector_top", get_universe_from_sector(profile))

    if len(sources) < 12:
        _add_symbols_with_source(
            sources,
            "etf_holding",
            get_universe_from_etf_fallback(profile.get("sector"), limit_holdings=20),
        )

    sources.pop(profile.get("symbol"), None)
    return profile, sources


# =============================================================================
# SCORING
# =============================================================================

def _candidate_is_eligible(target_profile: Dict[str, Any], candidate_profile: Dict[str, Any]) -> bool:
    """
    Precision-first filter. We would rather return fewer peers than pollute
    downstream benchmarking with weak matches.
    """
    symbol = candidate_profile.get("symbol")
    if not symbol or symbol == target_profile.get("symbol"):
        return False

    if not _is_common_stock_symbol(symbol):
        return False

    if _issuer_key(candidate_profile) == _issuer_key(target_profile):
        return False

    if str(candidate_profile.get("quote_type") or "").upper() != "EQUITY":
        return False

    target_sector_key = target_profile.get("sector_key")
    candidate_sector_key = candidate_profile.get("sector_key")
    if target_sector_key and candidate_sector_key and target_sector_key != candidate_sector_key:
        return False

    target_exchange = target_profile.get("exchange")
    candidate_exchange = candidate_profile.get("exchange")
    if _contains_disallowed_exchange(candidate_exchange) and not _contains_disallowed_exchange(target_exchange):
        return False

    market_cap_ratio = _ratio_band(target_profile.get("market_cap"), candidate_profile.get("market_cap"))
    if market_cap_ratio is not None and market_cap_ratio > MAX_SIZE_RATIO:
        return False

    revenue_ratio = _ratio_band(target_profile.get("revenue"), candidate_profile.get("revenue"))
    if market_cap_ratio is None and revenue_ratio is not None and revenue_ratio > MAX_SIZE_RATIO:
        return False

    target_industry_key = target_profile.get("industry_key")
    candidate_industry_key = candidate_profile.get("industry_key")
    exact_industry_match = (
        bool(target_industry_key)
        and bool(candidate_industry_key)
        and target_industry_key == candidate_industry_key
    )

    industry_similarity = _jaccard_similarity(
        target_profile.get("industry_tokens", set()),
        candidate_profile.get("industry_tokens", set()),
    )
    business_similarity = _jaccard_similarity(
        target_profile.get("business_tokens", set()),
        candidate_profile.get("business_tokens", set()),
    )

    return exact_industry_match or industry_similarity >= 0.20 or business_similarity >= 0.10


def score_peer(
    target_profile: Dict[str, Any],
    candidate_profile: Dict[str, Any],
    candidate_sources: Set[str],
) -> float:
    """
    Composite peer score built from business similarity, size similarity, and
    source confidence. Historical return similarity was removed because it was
    noisy, slow, and not a reliable proxy for peer quality.
    """
    score = 0.0

    target_industry_key = target_profile.get("industry_key")
    candidate_industry_key = candidate_profile.get("industry_key")
    if target_industry_key and candidate_industry_key and target_industry_key == candidate_industry_key:
        score += 45.0

    target_sector_key = target_profile.get("sector_key")
    candidate_sector_key = candidate_profile.get("sector_key")
    if target_sector_key and candidate_sector_key and target_sector_key == candidate_sector_key:
        score += 12.0

    industry_similarity = _jaccard_similarity(
        target_profile.get("industry_tokens", set()),
        candidate_profile.get("industry_tokens", set()),
    )
    business_similarity = _jaccard_similarity(
        target_profile.get("business_tokens", set()),
        candidate_profile.get("business_tokens", set()),
    )
    score += 18.0 * industry_similarity
    score += 10.0 * business_similarity

    score += 8.0 * _log_similarity(target_profile.get("market_cap"), candidate_profile.get("market_cap"))
    score += 6.0 * _log_similarity(target_profile.get("revenue"), candidate_profile.get("revenue"))

    score += 5.0 * _bounded_similarity(
        target_profile.get("operating_margin"),
        candidate_profile.get("operating_margin"),
        0.20,
    )
    score += 4.0 * _bounded_similarity(
        target_profile.get("gross_margin"),
        candidate_profile.get("gross_margin"),
        0.25,
    )
    score += 2.0 * _bounded_similarity(
        target_profile.get("beta"),
        candidate_profile.get("beta"),
        0.75,
    )

    if target_profile.get("country") and candidate_profile.get("country"):
        if target_profile.get("country") == candidate_profile.get("country"):
            score += 2.0

    if target_profile.get("currency") and candidate_profile.get("currency"):
        if target_profile.get("currency") == candidate_profile.get("currency"):
            score += 2.0

    if target_profile.get("exchange") and candidate_profile.get("exchange"):
        if target_profile.get("exchange") == candidate_profile.get("exchange"):
            score += 1.0

    score += sum(SOURCE_WEIGHTS.get(source, 0.0) for source in candidate_sources)
    return score


def _evaluate_candidate(
    target_profile: Dict[str, Any],
    symbol: str,
    candidate_sources: Set[str],
) -> Optional[Tuple[str, float, Dict[str, Any]]]:
    try:
        candidate_profile = get_company_profile(symbol)
        if not _candidate_is_eligible(target_profile, candidate_profile):
            return None

        score = score_peer(target_profile, candidate_profile, candidate_sources)
        return symbol, score, candidate_profile
    except Exception:
        return None


def get_top_peers(ticker: str, top_n: int = 10, return_period: str = "1y") -> List[str]:
    """
    Returns the best peer list available for the ticker.
    """
    _ = return_period  # Backward compatibility; return-based scoring was removed.

    ticker = _clean_symbol(ticker)
    if not ticker:
        return []

    print(f"Fetching peer universe for {ticker}...", flush=True)
    target_profile, candidate_sources = build_peer_universe(ticker)

    if not target_profile.get("sector_key") and not target_profile.get("industry_key"):
        print("Sector/industry information not available for this ticker.", flush=True)
        return []

    if not candidate_sources:
        print("No peer universe found from sector/industry data.", flush=True)
        return []

    max_workers = max(1, min(MAX_WORKERS, len(candidate_sources)))
    print(
        f"Evaluating {len(candidate_sources)} potential peers with up to {max_workers} workers...",
        flush=True,
    )

    scored: List[Tuple[str, float, Dict[str, Any]]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(_evaluate_candidate, target_profile, symbol, sources): symbol
            for symbol, sources in candidate_sources.items()
        }
        for future in as_completed(future_map):
            result = future.result()
            if result is not None:
                scored.append(result)

    if not scored:
        print("No high-confidence peer candidates survived filtering.", flush=True)
        return []

    scored.sort(key=lambda item: item[1], reverse=True)
    best_score = scored[0][1]
    primary_floor = max(MINIMUM_PEER_SCORE, best_score * PRIMARY_SCORE_RATIO)
    relaxed_floor = max(RELAXED_MINIMUM_PEER_SCORE, best_score * RELAXED_SCORE_RATIO)

    result: List[str] = []
    seen_symbols: Set[str] = set()
    seen_issuers: Set[str] = {_issuer_key(target_profile)}

    # First pass keeps only the strongest matches. If that leaves us too few
    # names, we relax slightly, but we still refuse to pad with weak candidates.
    for score_floor in (primary_floor, relaxed_floor):
        for symbol, score, candidate_profile in scored:
            if len(result) >= top_n:
                break

            if score < score_floor:
                continue

            issuer_key = _issuer_key(candidate_profile)
            if symbol in seen_symbols or issuer_key in seen_issuers:
                continue

            seen_symbols.add(symbol)
            seen_issuers.add(issuer_key)
            result.append(symbol)

        if len(result) >= min(top_n, 5):
            break

    print(
        "Target profile:",
        {
            "sector": target_profile.get("sector"),
            "industry": target_profile.get("industry"),
            "sector_key": target_profile.get("sector_key"),
            "industry_key": target_profile.get("industry_key"),
        },
        flush=True,
    )
    print(
        f"Selected {len(result)} high-confidence peers from {len(scored)} eligible candidates.",
        flush=True,
    )
    print("Top peers:", result, flush=True)

    return result


# Example usage to test output speed:
# if __name__ == "__main__":
#     get_top_peers("AAPL")
