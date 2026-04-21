import logging
from typing import Any, Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────

def _find_column(df: pd.DataFrame, keywords: list[str]) -> Optional[str]:
    """Return the first column name whose lowercase form contains any keyword."""
    for col in df.columns:
        col_lower = col.lower()
        if any(kw in col_lower for kw in keywords):
            return col
    return None


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        f = float(value)
        return f if pd.notna(f) else None
    except (TypeError, ValueError):
        return None


def _insider_trading_activity(
    insider_df: pd.DataFrame,
) -> Optional[Dict[str, Any]]:
    """Aggregate insider buy / sell share counts from the transactions table."""
    shares_col = _find_column(insider_df, ["share", "amount", "quantity"])
    type_col = _find_column(insider_df, ["type", "transaction", "transactiontype"])

    if shares_col is None or type_col is None:
        logger.debug(
            "Insider activity skipped — could not identify shares column (%s) "
            "or transaction-type column (%s).",
            shares_col,
            type_col,
        )
        return None

    # Convert shares to numeric; invalid rows become NaN and are excluded.
    shares = pd.to_numeric(insider_df[shares_col], errors="coerce")
    tx_type = insider_df[type_col].astype(str).str.lower()

    buys = float(shares[tx_type.str.contains("buy", na=False)].sum())
    sells = float(shares[tx_type.str.contains("sell", na=False)].sum())

    return {
        "Total_Buy_Shares": buys,
        "Total_Sell_Shares": sells,
        "Net_Activity": buys - sells,
    }


def _insider_concentration(
    insider_df: pd.DataFrame,
    shares_outstanding: Optional[float],
) -> Optional[float]:
    """Fraction of *total shares outstanding* held by the top-5 insider filers.

    Old behaviour divided by the sum of shares *in the transactions table*,
    which is a meaningless ratio — a large sell would increase apparent
    concentration.  Using shares_outstanding gives the correct figure.
    """
    shares_col = _find_column(insider_df, ["share", "amount", "quantity"])
    if shares_col is None:
        return None

    shares = pd.to_numeric(insider_df[shares_col], errors="coerce").dropna()
    if shares.empty:
        return None

    top5_total = float(shares.nlargest(5).sum())

    # Prefer total shares outstanding as denominator.
    if shares_outstanding and shares_outstanding > 0:
        return top5_total / shares_outstanding

    # Fallback: fraction within the insider transactions table.
    total_in_table = float(shares.sum())
    if total_in_table > 0:
        logger.debug(
            "insider_concentration: shares_outstanding unavailable; "
            "using transaction-table total as denominator."
        )
        return top5_total / total_in_table

    return None


# ─────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────

def compute_ownership(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns:
      Institutional_Ownership    – fraction held by institutions (from info)
      Insider_Ownership          – fraction held by insiders (from info)
      Insider_Trading_Activity   – dict of buy / sell / net share counts
      Insider_Concentration      – top-5 insider holders as fraction of shares outstanding
      Public_Float               – float shares count
    """
    info: Dict[str, Any] = data.get("info", {}) or {}
    institutional_df: Optional[pd.DataFrame] = data.get("institutional")
    insider_df: Optional[pd.DataFrame] = data.get("insider")

    # ── Institutional ownership ───────────────────────────────────────────────
    institutional_ownership = _safe_float(info.get("heldPercentInstitutions"))

    # ── Insider ownership (from info; most reliable source) ───────────────────
    insider_ownership = _safe_float(info.get("heldPercentInsiders"))

    # ── Shares outstanding (used for concentration denominator) ───────────────
    shares_outstanding = _safe_float(
        info.get("sharesOutstanding") or info.get("impliedSharesOutstanding")
    )

    # ── Insider trading activity ──────────────────────────────────────────────
    insider_activity: Optional[Dict[str, Any]] = None
    if insider_df is not None and not insider_df.empty:
        try:
            insider_activity = _insider_trading_activity(insider_df)
        except Exception as exc:
            logger.warning("Insider trading activity computation failed: %s", exc)

    # ── Insider concentration ─────────────────────────────────────────────────
    # Measures what fraction of total shares outstanding the top-5 insider
    # filers control — a true ownership-concentration signal.
    insider_concentration: Optional[float] = None
    if insider_df is not None and not insider_df.empty:
        try:
            insider_concentration = _insider_concentration(insider_df, shares_outstanding)
        except Exception as exc:
            logger.warning("Insider concentration computation failed: %s", exc)

    # ── Public float ──────────────────────────────────────────────────────────
    public_float = _safe_float(info.get("floatShares"))

    return {
        "Institutional_Ownership": institutional_ownership,
        "Insider_Ownership": insider_ownership,
        "Insider_Trading_Activity": insider_activity,
        "Insider_Concentration": insider_concentration,
        "Public_Float": public_float,
    }