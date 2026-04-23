import logging
from typing import Any, Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────



def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        f = float(value)
        return f if pd.notna(f) else None
    except (TypeError, ValueError):
        return None

# ─────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────

def compute_ownership(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns:
      Institutional_Ownership    – fraction held by institutions (from info)
      Insider_Ownership          – fraction held by insiders (from info)
    
      Insider_Concentration      – top-5 insider holders as fraction of shares outstanding
    
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

   
    


    return {
        "Institutional_Ownership": institutional_ownership,

    }