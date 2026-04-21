import math
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


# =============================================================================
# SMALL HELPERS
# =============================================================================

def _clean_symbol(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip().upper()
    if not s or s in {"NAN", "NONE", "NULL"}:
        return None
    # Ignore obviously non-ticker values
    if len(s) > 15:
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
    for v in values:
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return None


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
        # Common symbol columns
        candidate_cols = [
            "symbol", "Symbol", "ticker", "Ticker",
            "companySymbol", "company_symbol", "holdingSymbol", "holding_symbol"
        ]
        for col in candidate_cols:
            if col in obj.columns:
                symbols.extend(obj[col].tolist())

        # Sometimes the symbol is in the index
        if not symbols and obj.index is not None:
            symbols.extend([str(x) for x in obj.index.tolist()])

        return [_clean_symbol(x) for x in symbols if _clean_symbol(x)]

    if isinstance(obj, pd.Series):
        symbols.extend([str(x) for x in obj.tolist()])
        return [_clean_symbol(x) for x in symbols if _clean_symbol(x)]

    if isinstance(obj, dict):
        # Try common keys first
        for key in ("symbol", "Symbol", "ticker", "Ticker", "holdings", "data"):
            if key in obj:
                symbols.extend(_extract_symbols(obj[key]))
        # Fallback: use keys if dict looks like {SYM: value}
        if not symbols:
            symbols.extend(list(obj.keys()))
        return [_clean_symbol(x) for x in symbols if _clean_symbol(x)]

    if isinstance(obj, (list, tuple, set)):
        for x in obj:
            if isinstance(x, dict):
                symbols.extend(_extract_symbols(x))
            else:
                symbols.append(str(x))
        return [_clean_symbol(x) for x in symbols if _clean_symbol(x)]

    return [_clean_symbol(obj)] if _clean_symbol(obj) else []


def _log_similarity(a: Optional[float], b: Optional[float]) -> float:
    """
    Returns 1.0 when equal, approaching 0 as values diverge.
    Uses log scale for market cap similarity.
    """
    if a is None or b is None:
        return 0.0
    try:
        a = float(a)
        b = float(b)
        if a <= 0 or b <= 0:
            return 0.0
        diff = abs(math.log(a) - math.log(b))
        # About 1.0 at equal, ~0 at 10x difference or more
        return max(0.0, 1.0 - min(diff / math.log(10), 1.0))
    except Exception:
        return 0.0


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
    industry = _first_non_empty(info.get("industry"), info.get("industryName"))
    sector_key = _first_non_empty(info.get("sectorKey"), _normalize_sector_key(sector))
    industry_key = _first_non_empty(info.get("industryKey"))

    quote_type = _first_non_empty(info.get("quoteType"))
    market_cap = info.get("marketCap")
    if market_cap is not None:
        try:
            market_cap = float(market_cap)
        except Exception:
            market_cap = None

    return {
        "symbol": _clean_symbol(symbol),
        "sector": sector,
        "industry": industry,
        "sector_key": sector_key,
        "industry_key": industry_key,
        "quote_type": quote_type,
        "market_cap": market_cap,
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
    Primary universe: sector top companies.
    """
    sector_obj = get_sector_obj(company_profile.get("sector_key"))
    if not sector_obj:
        return []

    candidates: List[str] = []
    try:
        candidates.extend(_extract_symbols(getattr(sector_obj, "top_companies", None)))
    except Exception:
        pass

    # Sector-level ETFs are not the main peer source, but can help as fallback.
    try:
        top_etfs = getattr(sector_obj, "top_etfs", None)
        candidates.extend(_extract_symbols(top_etfs))
    except Exception:
        pass

    return _unique_preserve_order(candidates)


def get_universe_from_industry(company_profile: Dict[str, Any]) -> List[str]:
    """
    Best universe: industry top performers and growth names.
    """
    industry_obj = get_industry_obj(company_profile.get("industry_key"))
    if not industry_obj:
        return []

    candidates: List[str] = []
    try:
        candidates.extend(_extract_symbols(getattr(industry_obj, "top_performing_companies", None)))
    except Exception:
        pass

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
            fd = yf.Ticker(etf).funds_data
            top_holdings = getattr(fd, "top_holdings", None)
            holdings.extend(_extract_symbols(top_holdings))
            if len(holdings) >= limit_holdings * 3:
                break
        except Exception:
            continue

    return _unique_preserve_order(holdings)


def build_peer_universe(ticker: str) -> Tuple[Dict[str, Any], List[str]]:
    """
    Build a candidate universe quickly without validating equity type yet.
    """
    profile = get_company_profile(ticker)

    universe: List[str] = []
    universe.extend(get_universe_from_industry(profile))
    universe.extend(get_universe_from_sector(profile))
    universe.extend(get_universe_from_etf_fallback(profile.get("sector"), limit_holdings=20))

    # Remove duplicates and self. Note: We removed the slow get_ticker_info() equity check from here.
    universe = _unique_preserve_order(universe)
    filtered = [s for s in universe if s != profile["symbol"]]

    return profile, filtered


# =============================================================================
# PERFORMANCE / SCORING
# =============================================================================

def get_return(symbol: str, period: str = "1y") -> Optional[float]:
    """
    Total return over the chosen period using adjusted prices when available.
    """
    symbol = _clean_symbol(symbol)
    if not symbol:
        return None

    try:
        hist = yf.Ticker(symbol).history(period=period, auto_adjust=True)
        if hist is None or hist.empty:
            return None

        close_col = None
        for col in ("Close", "Adj Close"):
            if col in hist.columns:
                close_col = col
                break

        if close_col is None:
            return None

        series = hist[close_col].dropna()
        if len(series) < 2:
            return None

        first = float(series.iloc[0])
        last = float(series.iloc[-1])
        if first <= 0:
            return None

        return (last / first) - 1.0
    except Exception:
        return None


def score_peer(
    target_profile: Dict[str, Any],
    candidate: str,
    candidate_profile: Dict[str, Any],
    candidate_return: Optional[float],
    target_return: Optional[float],
) -> float:
    """
    Composite peer score.
    """
    score = 0.0

    target_sector_key = target_profile.get("sector_key")
    target_industry_key = target_profile.get("industry_key")
    target_market_cap = target_profile.get("market_cap")

    cand_sector_key = candidate_profile.get("sector_key")
    cand_industry_key = candidate_profile.get("industry_key")
    cand_market_cap = candidate_profile.get("market_cap")

    if target_industry_key and cand_industry_key and target_industry_key == cand_industry_key:
        score += 60.0

    if target_sector_key and cand_sector_key and target_sector_key == cand_sector_key:
        score += 20.0

    score += 15.0 * _log_similarity(target_market_cap, cand_market_cap)

    if target_return is not None and candidate_return is not None:
        diff = abs(float(target_return) - float(candidate_return))
        ret_sim = max(0.0, 1.0 - min(diff / 1.0, 1.0))
        score += 5.0 * ret_sim

    t_ex = target_profile.get("info", {}).get("exchange")
    c_ex = candidate_profile.get("info", {}).get("exchange")
    if t_ex and c_ex and t_ex == c_ex:
        score += 2.0

    return score


def get_top_peers(ticker: str, top_n: int = 10, return_period: str = "1y") -> List[str]:
    """
    Returns the best peer list available for the ticker.
    """
    ticker = _clean_symbol(ticker)
    if not ticker:
        return []

    print(f"Fetching peer universe for {ticker}...", flush=True)

    # This is now fast because we moved the heavy equity check out of it
    target_profile, universe = build_peer_universe(ticker)

    if not target_profile.get("sector_key") and not target_profile.get("industry_key"):
        print("Sector/industry information not available for this ticker.", flush=True)
        return []

    if not universe:
        print("No peer universe found from sector/industry data.", flush=True)
        return []

    # Add backup candidates
    if len(universe) < max(10, top_n):
        sector_only = get_universe_from_sector(target_profile)
        universe = _unique_preserve_order(universe + sector_only)

    # --- ESTIMATED WAITING TIME (Now triggers instantly) ---
    estimated_seconds = len(universe) * 1.0  # ~1 second per candidate API call
    mins = int(estimated_seconds // 60)
    secs = int(estimated_seconds % 60)
    
    if mins > 0:
        print(f"Evaluating {len(universe)} potential peers. Estimated waiting time: ~{mins}m {secs}s...", flush=True)
    else:
        print(f"Evaluating {len(universe)} potential peers. Estimated waiting time: ~{secs}s...", flush=True)
    # -------------------------------------------------------

    # Fetch target returns
    target_return = get_return(ticker, period=return_period)

    scored: List[Tuple[str, float]] = []
    for symbol in universe:
        try:
            # We now do the API call here, which accurately reflects the waiting time estimate
            cand_profile = get_company_profile(symbol)
            
            # Defer the equity check to here so it doesn't block our initial print statements
            qt = str(cand_profile.get("quote_type", "")).upper()
            if qt != "EQUITY":
                continue

            cand_return = get_return(symbol, period=return_period)
            s = score_peer(
                target_profile=target_profile,
                candidate=symbol,
                candidate_profile=cand_profile,
                candidate_return=cand_return,
                target_return=target_return,
            )
            scored.append((symbol, s))
        except Exception:
            continue

    scored.sort(key=lambda x: x[1], reverse=True)

    # Remove duplicates, self, and keep top_n
    result: List[str] = []
    seen: Set[str] = set()
    for symbol, _ in scored:
        symbol = _clean_symbol(symbol)
        if not symbol or symbol == ticker or symbol in seen:
            continue
        seen.add(symbol)
        result.append(symbol)
        if len(result) >= top_n:
            break

    print("Target profile:", {
        "sector": target_profile.get("sector"),
        "industry": target_profile.get("industry"),
        "sector_key": target_profile.get("sector_key"),
        "industry_key": target_profile.get("industry_key"),
    }, flush=True)
    print("Top peers:", result, flush=True)

    return result

# Example usage to test output speed:
# if __name__ == "__main__":
#     get_top_peers("AAPL")