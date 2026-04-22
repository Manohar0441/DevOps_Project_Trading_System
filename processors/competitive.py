import pandas as pd
from typing import Any, Dict, Optional, List


# -----------------------------
# Helpers
# -----------------------------
def safe_div(numerator, denominator):
    try:
        if numerator is None or denominator in [0, None]:
            return None
        if pd.isna(numerator) or pd.isna(denominator):
            return None
        return float(numerator) / float(denominator)
    except Exception:
        return None


def to_float(value):
    try:
        if value is None:
            return None
        if isinstance(value, str) and value.strip() == "":
            return None
        if pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None


def clamp(value, low=0.0, high=1.0):
    if value is None:
        return None
    try:
        return max(low, min(high, float(value)))
    except Exception:
        return None


def make_field(value=None, source="yfinance", method="direct", note=""):
    return {
        "value": value,
        "source": source,
        "method": method,
        "note": note
    }


def nested_get(d: Dict[str, Any], *keys, default=None):
    cur = d or {}
    for key in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key, default)
    return default if cur is None else cur


def get_df(raw: Dict[str, Any], key: str):
    obj = raw.get(key)
    if isinstance(obj, pd.DataFrame) and not obj.empty:
        return obj
    return None


def find_row(df: Optional[pd.DataFrame], candidates: List[str]):
    if df is None or df.empty:
        return None

    index_list = list(df.index)
    index_lower = {str(idx).strip().lower(): idx for idx in index_list}

    for cand in candidates:
        cand_l = cand.strip().lower()

        if cand_l in index_lower:
            row = df.loc[index_lower[cand_l]]
            return pd.to_numeric(row, errors="coerce")

        for idx in index_list:
            idx_l = str(idx).strip().lower()
            if cand_l in idx_l or idx_l in cand_l:
                row = df.loc[idx]
                return pd.to_numeric(row, errors="coerce")

    return None


def first_valid_from_series(series: Optional[pd.Series]):
    if series is None:
        return None
    try:
        for v in series.values:
            fv = to_float(v)
            if fv is not None:
                return fv
    except Exception:
        pass
    return None


def series_history(series: Optional[pd.Series], n=4):
    if series is None:
        return []
    vals = []
    try:
        for v in series.values:
            fv = to_float(v)
            if fv is not None:
                vals.append(fv)
            if len(vals) >= n:
                break
    except Exception:
        pass
    return vals


def stability_score(values: List[float]):
    vals = [v for v in values if v is not None]
    if len(vals) < 2:
        return None
    mean = sum(vals) / len(vals)
    if mean == 0:
        return None
    var = sum((v - mean) ** 2 for v in vals) / len(vals)
    std = var ** 0.5
    cv = abs(std / mean)
    return clamp(1 - cv, 0.0, 1.0)


def get_latest_row_value(df: Optional[pd.DataFrame], candidates: List[str]):
    row = find_row(df, candidates)
    return first_valid_from_series(row)


def get_row_history(df: Optional[pd.DataFrame], candidates: List[str], n=4):
    row = find_row(df, candidates)
    return series_history(row, n=n)


# -----------------------------
# Core calculations
# -----------------------------
def compute_gross_margin_profile(raw: Dict[str, Any]):
    income = get_df(raw, "income")

    gross_profit = find_row(income, ["Gross Profit"])
    revenue = find_row(income, ["Total Revenue", "Operating Revenue"])

    if gross_profit is None or revenue is None:
        return {
            "latest_gross_margin": None,
            "gross_margin_history": [],
            "stability": None,
            "note": "Gross profit or revenue not available in raw income statement."
        }

    margins = []
    try:
        common_cols = list(income.columns)
        for col in common_cols:
            gp = to_float(gross_profit.get(col))
            rev = to_float(revenue.get(col))
            gm = safe_div(gp, rev)
            if gm is not None:
                margins.append(gm)
    except Exception:
        pass

    latest = margins[0] if margins else None
    return {
        "latest_gross_margin": latest,
        "gross_margin_history": margins[:4],
        "stability": stability_score(margins[:4]),
        "note": "Computed from Gross Profit / Revenue."
    }


def compute_roic_proxy(raw: Dict[str, Any], metrics: Dict[str, Any]):
    income = get_df(raw, "income")
    balance = get_df(raw, "balance")

    ebit = get_latest_row_value(income, ["EBIT", "Operating Income"])
    pretax = get_latest_row_value(income, ["Pretax Income"])
    tax_provision = get_latest_row_value(income, ["Tax Provision", "Income Tax Expense"])

    total_equity = get_latest_row_value(balance, ["Total Stockholder Equity", "Stockholders Equity", "Total Equity Gross Minority Interest"])
    total_debt = get_latest_row_value(balance, ["Total Debt", "Long Term Debt", "Short Long Term Debt", "Long Term Debt And Capital Lease Obligation"])
    cash = get_latest_row_value(balance, ["Cash And Cash Equivalents", "Cash", "Cash And Cash Equivalents And Short Term Investments"])

    invested_capital = None
    if total_equity is not None or total_debt is not None or cash is not None:
        invested_capital = (total_equity or 0) + (total_debt or 0) - (cash or 0)
        if invested_capital == 0:
            invested_capital = None

    tax_rate = None
    if pretax not in [None, 0] and tax_provision is not None:
        tax_rate = abs(safe_div(tax_provision, pretax))
        tax_rate = clamp(tax_rate, 0.0, 0.4)

    if ebit is not None and invested_capital is not None:
        if tax_rate is None:
            tax_rate = 0.21
        nopat = ebit * (1 - tax_rate)
        roic = safe_div(nopat, invested_capital)
        return {
            "value": roic,
            "method": "derived",
            "source": "income + balance",
            "note": "NOPAT / Invested Capital. Uses tax rate from statements when available."
        }

    roe = nested_get(metrics, "profitability", "ROE")
    return {
        "value": roe,
        "method": "proxy",
        "source": "metrics.profitability.ROE",
        "note": "ROIC unavailable from raw data; using ROE as proxy."
    }


def compute_capital_allocation_efficiency(raw: Dict[str, Any]):
    income = get_df(raw, "income")
    cashflow = get_df(raw, "cashflow")
    balance = get_df(raw, "balance")

    net_income = get_latest_row_value(income, ["Net Income", "Net Income Common Stockholders"])
    revenue = get_latest_row_value(income, ["Total Revenue", "Operating Revenue"])
    capex = get_latest_row_value(cashflow, ["Capital Expenditure", "Capital Expenditures", "Capex"])
    operating_cash_flow = get_latest_row_value(cashflow, ["Operating Cash Flow", "Total Cash From Operating Activities"])
    free_cash_flow = get_latest_row_value(cashflow, ["Free Cash Flow"])
    total_equity = get_latest_row_value(balance, ["Total Stockholder Equity", "Stockholders Equity"])
    total_debt = get_latest_row_value(balance, ["Total Debt", "Long Term Debt", "Short Long Term Debt"])
    cash = get_latest_row_value(balance, ["Cash And Cash Equivalents", "Cash", "Cash And Cash Equivalents And Short Term Investments"])

    if free_cash_flow is None and operating_cash_flow is not None and capex is not None:
        free_cash_flow = operating_cash_flow + capex

    fcf_conversion = safe_div(free_cash_flow, net_income)
    capex_intensity = safe_div(abs(capex) if capex is not None else None, revenue)

    invested_capital = None
    if total_equity is not None or total_debt is not None or cash is not None:
        invested_capital = (total_equity or 0) + (total_debt or 0) - (cash or 0)
        if invested_capital == 0:
            invested_capital = None

    roic_proxy = safe_div(net_income, invested_capital) if net_income is not None and invested_capital is not None else None

    return {
        "fcf": free_cash_flow,
        "fcf_conversion": fcf_conversion,
        "capex_intensity": capex_intensity,
        "roic_proxy": roic_proxy,
        "note": "Uses free cash flow conversion, capex intensity, and a rough invested-capital return proxy."
    }


def get_management_ownership(raw: Dict[str, Any]):
    info = raw.get("info", {}) or {}
    insiders = info.get("heldPercentInsiders")
    institutions = info.get("heldPercentInstitutions")

    return {
        "insider_ownership": insiders,
        "institutional_confidence": institutions,
        "comment": "Higher insider holding generally suggests stronger incentive alignment."
    }


def get_management_stability(raw: Dict[str, Any]):
    info = raw.get("info", {}) or {}
    officers = info.get("companyOfficers") or []

    ceo = None
    for officer in officers:
        title = str(officer.get("title", "")).lower()
        if "chief executive officer" in title or title == "ceo" or "ceo" in title:
            ceo = officer
            break

    exec_names = []
    for officer in officers[:10]:
        name = officer.get("name")
        if name:
            exec_names.append(name)

    return {
        "executive_count": len(officers) if isinstance(officers, list) else None,
        "ceo_found": ceo.get("name") if isinstance(ceo, dict) else None,
        "executives_sample": exec_names,
        "note": "True management stability needs tenure/history data; Yahoo Finance does not always provide it reliably."
    }


# -----------------------------
# External competitive data
# -----------------------------
def compute_market_share(external_data: Dict[str, Any]):
    direct_share = external_data.get("market_share")
    if direct_share is not None:
        return make_field(
            value=direct_share,
            source="external_data.market_share",
            method="direct",
            note="Direct market share input supplied externally."
        )

    company_revenue = external_data.get("company_revenue")
    tam = external_data.get("tam") or external_data.get("market_size")
    if company_revenue is not None and tam not in [None, 0]:
        return make_field(
            value=safe_div(company_revenue, tam),
            source="external_data.company_revenue + external_data.tam",
            method="derived",
            note="Market share = company revenue / TAM."
        )

    return make_field(
        value=None,
        source="external_data",
        method="unavailable",
        note="Needs company revenue and TAM/market size from an external source."
    )


def compute_tam(external_data: Dict[str, Any]):
    tam = external_data.get("tam") or external_data.get("market_size")
    return make_field(
        value=tam,
        source="external_data",
        method="direct" if tam is not None else "unavailable",
        note="TAM is not available from Yahoo Finance alone."
    )


def compute_brand_value(external_data: Dict[str, Any]):
    brand_value = external_data.get("brand_value")
    return make_field(
        value=brand_value,
        source="external_data",
        method="direct" if brand_value is not None else "unavailable",
        note="Brand value requires an external brand valuation source."
    )


def compute_customer_concentration(external_data: Dict[str, Any]):
    value = (
        external_data.get("customer_concentration")
        if external_data.get("customer_concentration") is not None
        else external_data.get("top_customer_revenue_share")
        if external_data.get("top_customer_revenue_share") is not None
        else external_data.get("top5_customer_share")
    )

    return make_field(
        value=value,
        source="external_data",
        method="direct" if value is not None else "unavailable",
        note="Customer concentration typically comes from annual reports or segment disclosures."
    )


def compute_market_concentration(external_data: Dict[str, Any]):
    if external_data.get("hhi") is not None:
        return make_field(
            value=external_data.get("hhi"),
            source="external_data.hhi",
            method="direct",
            note="HHI supplied externally."
        )

    if external_data.get("top3_share") is not None:
        return make_field(
            value=external_data.get("top3_share"),
            source="external_data.top3_share",
            method="direct",
            note="Top-3 market share supplied externally."
        )

    competitor_revenues = external_data.get("competitor_revenues")
    if competitor_revenues:
        try:
            if isinstance(competitor_revenues, dict):
                revs = [to_float(v) for v in competitor_revenues.values() if to_float(v) is not None]
            elif isinstance(competitor_revenues, list):
                revs = [to_float(v) for v in competitor_revenues if to_float(v) is not None]
            else:
                revs = []

            total = sum(revs)
            if total > 0:
                shares = [r / total for r in revs]
                hhi = sum((s * 100) ** 2 for s in shares)
                return make_field(
                    value=hhi,
                    source="external_data.competitor_revenues",
                    method="derived",
                    note="Computed as sum of squared market shares on the 0-10,000 HHI scale."
                )
        except Exception:
            pass

    return make_field(
        value=None,
        source="external_data",
        method="unavailable",
        note="Needs market structure data, competitor revenues, or a direct concentration index."
    )


def estimate_cost_advantage(gross_margin_profile, external_data: Dict[str, Any]):
    latest_gm = gross_margin_profile.get("latest_gross_margin")
    peer_gm = external_data.get("peer_gross_margin") or external_data.get("industry_gross_margin")

    if latest_gm is not None and peer_gm is not None:
        spread = latest_gm - peer_gm
        return make_field(
            value=spread,
            source="gross_margin_profile + external_data.peer_gross_margin",
            method="derived",
            note="Positive spread suggests a possible cost advantage or pricing strength versus peers."
        )

    return make_field(
        value=None,
        source="external_data",
        method="unavailable",
        note="Needs peer or industry gross margin to assess cost advantage accurately."
    )


def estimate_product_differentiation(metrics, raw, external_data: Dict[str, Any]):
    if external_data.get("product_differentiation_score") is not None:
        return make_field(
            value=external_data.get("product_differentiation_score"),
            source="external_data.product_differentiation_score",
            method="direct",
            note="Direct differentiation score supplied externally."
        )

    rd_intensity = external_data.get("rd_intensity")
    gross_margin = nested_get(metrics, "profitability", "Gross_Margin")
    pe = nested_get(metrics, "valuation", "PE")

    score = None
    reasons = []

    if rd_intensity is not None:
        score = clamp(float(rd_intensity), 0.0, 1.0)
        reasons.append("Uses R&D intensity as a partial proxy.")

    if gross_margin is not None:
        reasons.append("Higher gross margin can indicate differentiation or pricing power.")

    if pe is not None:
        reasons.append("Premium valuation can sometimes reflect perceived differentiation.")

    return make_field(
        value=score,
        source="metrics + external_data",
        method="proxy",
        note="True differentiation needs product, brand, and peer comparison data. " + " ".join(reasons)
    )


def estimate_switching_costs(external_data: Dict[str, Any], gross_margin_profile):
    if external_data.get("switching_costs_score") is not None:
        return make_field(
            value=external_data.get("switching_costs_score"),
            source="external_data.switching_costs_score",
            method="direct",
            note="Direct switching-cost score supplied externally."
        )

    recurring = external_data.get("recurring_revenue_ratio")
    retention = external_data.get("retention_rate") or external_data.get("net_revenue_retention")
    stability = gross_margin_profile.get("stability")

    proxy_parts = [v for v in [recurring, retention, stability] if v is not None]
    proxy_value = sum(proxy_parts) / len(proxy_parts) if proxy_parts else None

    return make_field(
        value=proxy_value,
        source="external_data + gross_margin_profile",
        method="proxy",
        note="Switching costs are best measured using retention, recurring revenue, or contract data."
    )


def estimate_network_effects(external_data: Dict[str, Any]):
    if external_data.get("network_effects_score") is not None:
        return make_field(
            value=external_data.get("network_effects_score"),
            source="external_data.network_effects_score",
            method="direct",
            note="Direct network-effects score supplied externally."
        )

    user_growth = external_data.get("user_growth")
    transaction_growth = external_data.get("transaction_growth")
    active_users = external_data.get("active_users")

    if active_users is not None or user_growth is not None or transaction_growth is not None:
        return make_field(
            value=None,
            source="external_data",
            method="proxy",
            note="Network effects generally need platform usage, engagement, or transaction data."
        )

    return make_field(
        value=None,
        source="external_data",
        method="unavailable",
        note="Not enough data to infer network effects."
    )


def estimate_regulatory_barriers(raw: Dict[str, Any], external_data: Dict[str, Any]):
    if external_data.get("regulatory_barriers_score") is not None:
        return make_field(
            value=external_data.get("regulatory_barriers_score"),
            source="external_data.regulatory_barriers_score",
            method="direct",
            note="Direct regulatory-barriers score supplied externally."
        )

    info = raw.get("info", {}) or {}
    sector = info.get("sector")
    industry = info.get("industry")

    return make_field(
        value=None,
        source="yfinance.info",
        method="proxy",
        note=f"Sector='{sector}', Industry='{industry}'. Real regulatory barriers require legal or industry research."
    )


# -----------------------------
# Porter's Five Forces
# -----------------------------
def estimate_porters_five_forces(compiled: Dict[str, Any]):
    gross = compiled["gross_margin_profile"]
    cost_adv = compiled["cost_advantage"]
    diff = compiled["product_differentiation"]
    switch = compiled["switching_costs"]
    network = compiled["network_effects"]
    reg = compiled["regulatory_barriers"]
    market_conc = compiled["market_concentration"]
    customer_conc = compiled["customer_concentration"]

    def clamp01(v):
        if v is None:
            return None
        try:
            return clamp(float(v), 0, 1)
        except Exception:
            return None

    reg_v = reg.get("value")
    cost_v = cost_adv.get("value")
    diff_v = diff.get("value")
    switch_v = switch.get("value")
    net_v = network.get("value")
    hhi_v = market_conc.get("value")
    cust_v = customer_conc.get("value")
    gm_stability = gross.get("stability")
    gm = gross.get("latest_gross_margin")

    barriers_strength = None
    barrier_parts = [v for v in [reg_v, diff_v, switch_v, net_v] if v is not None]
    if barrier_parts:
        barriers_strength = sum(barrier_parts) / len(barrier_parts)

    new_entrants_score = None
    if barriers_strength is not None:
        new_entrants_score = 5 - 4 * clamp01(barriers_strength)
        new_entrants_score = round(new_entrants_score, 2)

    supplier_power_score = None
    if cost_v is not None:
        supplier_power_score = 5 - 4 * clamp01(abs(cost_v))
        supplier_power_score = round(supplier_power_score, 2)
    elif gm is not None:
        supplier_power_score = 5 - 4 * clamp01(gm)
        supplier_power_score = round(supplier_power_score, 2)

    buyer_power_score = None
    if cust_v is not None:
        buyer_power_score = 1 + 4 * clamp01(cust_v)
        buyer_power_score = round(buyer_power_score, 2)

    substitutes_score = None
    substitute_parts = [v for v in [diff_v, switch_v] if v is not None]
    if substitute_parts:
        strength = sum(substitute_parts) / len(substitute_parts)
        substitutes_score = 5 - 4 * clamp01(strength)
        substitutes_score = round(substitutes_score, 2)

    rivalry_score = None
    rivalry_inputs = []
    if hhi_v is not None:
        rivalry_inputs.append(1 - clamp01(hhi_v / 10_000))
    if gm_stability is not None:
        rivalry_inputs.append(1 - clamp01(gm_stability))
    if gm is not None:
        rivalry_inputs.append(1 - clamp01(gm))
    if rivalry_inputs:
        rivalry_score = 1 + 4 * (sum(rivalry_inputs) / len(rivalry_inputs))
        rivalry_score = round(rivalry_score, 2)

    return {
        "threat_of_new_entrants": {
            "score": new_entrants_score,
            "interpretation": "Lower is better for the company.",
            "drivers": ["Regulatory barriers", "Product differentiation", "Switching costs", "Network effects"]
        },
        "supplier_power": {
            "score": supplier_power_score,
            "interpretation": "Lower is better for the company.",
            "drivers": ["Cost advantage", "Gross margin strength"]
        },
        "buyer_power": {
            "score": buyer_power_score,
            "interpretation": "Lower is better for the company.",
            "drivers": ["Customer concentration"]
        },
        "threat_of_substitutes": {
            "score": substitutes_score,
            "interpretation": "Lower is better for the company.",
            "drivers": ["Product differentiation", "Switching costs"]
        },
        "industry_rivalry": {
            "score": rivalry_score,
            "interpretation": "Lower is better for the company.",
            "drivers": ["Market concentration", "Gross margin stability", "Gross margin level"]
        }
    }


# -----------------------------
# Main moat and management
# -----------------------------
def competitive_moat_score(metrics, raw, external_data=None):
    external_data = external_data or {}

    def to_float(value):
        try:
            if value in [None, "", "NaN"]:
                return None
            return float(value)
        except:
            return None

    def safe_val(obj, key):
        return to_float(obj.get(key)) if obj else None

    gross_margin_profile = compute_gross_margin_profile(raw)
    roic_data = compute_roic_proxy(raw, metrics)
    cap_alloc = compute_capital_allocation_efficiency(raw)

    score = 0
    reasons = []

    # -----------------------------------
    # 1. ROIC (High importance)
    # -----------------------------------
    roic = to_float(roic_data.get("value"))
    if roic is not None and roic > 0.15:
        score += 2
        reasons.append("High sustained return on invested capital")

    # -----------------------------------
    # 2. Gross Margin Stability
    # -----------------------------------
    gm = to_float(gross_margin_profile.get("latest_gross_margin"))
    gm_stability = to_float(gross_margin_profile.get("stability"))

    if gm is not None and gm > 0.30 and gm_stability is not None and gm_stability >= 0.75:
        score += 1
        reasons.append("Stable gross margins")

    # -----------------------------------
    # 3. Cost Advantage
    # -----------------------------------
    cost_advantage = estimate_cost_advantage(gross_margin_profile, external_data)
    cost_val = to_float(cost_advantage.get("value"))

    if cost_val is not None and cost_val > 0.7:
        score += 1
        reasons.append("Cost advantage vs peers")

    # -----------------------------------
    # 4. Product Differentiation
    # -----------------------------------
    differentiation = estimate_product_differentiation(metrics, raw, external_data)
    diff_val = to_float(differentiation.get("value"))

    if diff_val is not None and diff_val > 0.7:
        score += 1
        reasons.append("Strong product differentiation")

    # -----------------------------------
    # 5. Switching Costs
    # -----------------------------------
    switching_costs = estimate_switching_costs(external_data, gross_margin_profile)
    switch_val = to_float(switching_costs.get("value"))

    if switch_val is not None and switch_val > 0.7:
        score += 1
        reasons.append("High switching costs")

    # -----------------------------------
    # 6. Network Effects
    # -----------------------------------
    network_effects = estimate_network_effects(external_data)
    net_val = to_float(network_effects.get("value"))

    if net_val is not None and net_val > 0.7:
        score += 1
        reasons.append("Network effects present")

    # -----------------------------------
    # 7. Regulatory Barriers
    # -----------------------------------
    regulatory_barriers = estimate_regulatory_barriers(raw, external_data)
    reg_val = to_float(regulatory_barriers.get("value"))

    if reg_val is not None and reg_val > 0.7:
        score += 1
        reasons.append("Regulatory barriers present")

    # -----------------------------------
    # 8. Management Ownership
    # -----------------------------------
    management_ownership = get_management_ownership(raw)
    insiders = to_float(management_ownership.get("insider_ownership"))

    if insiders is not None and insiders > 0.05:
        score += 1
        reasons.append("Aligned management incentives")

    # -----------------------------------
    # 9. Capital Allocation
    # -----------------------------------
    cap_eff = to_float(cap_alloc.get("fcf_conversion"))

    if cap_eff is not None and cap_eff > 0.6:
        score += 1
        reasons.append("Strong capital allocation")

    # -----------------------------------
    # 10. Market Premium (Valuation Signal)
    # -----------------------------------
    info = raw.get("info", {}) or {}
    raw_pe = info.get("trailingPE")

    if raw_pe is None:
        raw_pe = nested_get(metrics, "valuation", "PE")

    pe = to_float(raw_pe)

    if pe is not None and pe > 25:
        score += 1
        reasons.append("Market assigns premium valuation")

    # -----------------------------------
    # Final Output
    # -----------------------------------
    return {
        "moat_score": score,
        "max_score": 12,  # updated due to weighting
        "strength": (
            "Strong" if score >= 8 else
            "Moderate" if score >= 5 else
            "Weak"
        ),
        "reasons": reasons
    }

def management_quality(raw, external_data=None):
    external_data = external_data or {}
    info = raw.get("info", {}) or {}

    return {
        "insider_ownership": info.get("heldPercentInsiders"),
        "institutional_confidence": info.get("heldPercentInstitutions"),
        "comment": "Higher insider holding = aligned incentives",
        "stability": get_management_stability(raw),
        "ownership_note": "Ownership is directly from Yahoo Finance when available."
    }


def competitive_analysis(metrics, raw, external_data=None):
    external_data = external_data or {}

    gross_margin_profile = compute_gross_margin_profile(raw)
    roic_data = compute_roic_proxy(raw, metrics)
    cap_alloc = compute_capital_allocation_efficiency(raw)
    management_own = get_management_ownership(raw)
    management_stab = get_management_stability(raw)

    cost_advantage = estimate_cost_advantage(gross_margin_profile, external_data)
    product_differentiation = estimate_product_differentiation(metrics, raw, external_data)
    switching_costs = estimate_switching_costs(external_data, gross_margin_profile)
    network_effects = estimate_network_effects(external_data)
    regulatory_barriers = estimate_regulatory_barriers(raw, external_data)
    market_share = compute_market_share(external_data)
    tam = compute_tam(external_data)
    brand_value = compute_brand_value(external_data)
    market_concentration = compute_market_concentration(external_data)
    customer_concentration = compute_customer_concentration(external_data)

    competitive = {
        "moat": competitive_moat_score(metrics, raw, external_data),
        "management": management_quality(raw, external_data),

        "sustained_roic": {
            "value": roic_data.get("value"),
            "source": roic_data.get("source"),
            "method": roic_data.get("method"),
            "note": roic_data.get("note")
        },

        "gross_margin_profile": {
            "latest_gross_margin": gross_margin_profile.get("latest_gross_margin"),
            "gross_margin_history": gross_margin_profile.get("gross_margin_history"),
            "stability": gross_margin_profile.get("stability"),
            "note": gross_margin_profile.get("note")
        },

        "stable_gross_margins": {
            "latest_gross_margin": gross_margin_profile.get("latest_gross_margin"),
            "gross_margin_history": gross_margin_profile.get("gross_margin_history"),
            "stability": gross_margin_profile.get("stability"),
            "note": gross_margin_profile.get("note")
        },

        "market_share": market_share,
        "brand_value": brand_value,
        "cost_advantage": cost_advantage,
        "product_differentiation": product_differentiation,
        "switching_costs": switching_costs,
        "network_effects": network_effects,
        "regulatory_barriers": regulatory_barriers,

        "management_ownership": {
            "value": management_own.get("insider_ownership"),
            "source": "yfinance.info.heldPercentInsiders",
            "method": "direct",
            "note": "Direct insider ownership from Yahoo Finance."
        },

        "capital_allocation_efficiency": {
            "fcf": cap_alloc.get("fcf"),
            "fcf_conversion": cap_alloc.get("fcf_conversion"),
            "capex_intensity": cap_alloc.get("capex_intensity"),
            "roic_proxy": cap_alloc.get("roic_proxy"),
            "note": cap_alloc.get("note")
        },

        "management_stability": management_stab,
        "tam": tam,
        "market_concentration": market_concentration,
        "customer_concentration": customer_concentration,
    }

    competitive["porters_five_forces"] = estimate_porters_five_forces({
        "gross_margin_profile": competitive["gross_margin_profile"],
        "cost_advantage": competitive["cost_advantage"],
        "product_differentiation": competitive["product_differentiation"],
        "switching_costs": competitive["switching_costs"],
        "network_effects": competitive["network_effects"],
        "regulatory_barriers": competitive["regulatory_barriers"],
        "market_concentration": competitive["market_concentration"],
        "customer_concentration": competitive["customer_concentration"]
    })

    competitive["moat_detail"] = {
        "gross_margin_profile": competitive["gross_margin_profile"],
        "capital_allocation_efficiency": competitive["capital_allocation_efficiency"],
        "ownership": management_own
    }

    return {
        "moat": competitive["moat"],  # <-- ADD THIS
        "competitive": competitive
        
    }