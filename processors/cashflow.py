from utils.financials import (
    NET_INCOME_KEYS,
    OPERATING_CASH_FLOW_KEYS,
    REVENUE_KEYS,
    STOCK_BASED_COMPENSATION_KEYS,
    _safe_gt,
    _safe_lt,
    aligned_flow_values,
    capex_value,
    cashflow_value,
    is_missing,
    net_borrowing_value,
    normalize_output,
    safe_div,
    total_debt_value,
)
from utils.financials import income_value  # Keep the public function names explicit at call sites.
from processors.metric_engine import (
    capital_intensive_sector,
    current_fcf_snapshot,
    market_cap_snapshot,
    safe_ratio,
    to_float,
)


def compute_cashflow(data):
    operating_cash_flow = cashflow_value(data, OPERATING_CASH_FLOW_KEYS)
    revenue = income_value(data, REVENUE_KEYS)
    capex = capex_value(data)
    total_debt = total_debt_value(data)
    net_borrowing = net_borrowing_value(data)
    market_cap_meta = market_cap_snapshot(data)
    market_cap = to_float(market_cap_meta["value"])
    fcf_meta = current_fcf_snapshot(data)
    free_cash_flow = to_float(fcf_meta["value"])

    aligned_ocf, aligned_net_income = aligned_flow_values(
        data.get("quarterly_cashflow"),
        data.get("cashflow"),
        OPERATING_CASH_FLOW_KEYS,
        data.get("quarterly_income"),
        data.get("income"),
        NET_INCOME_KEYS,
    )
    aligned_sbc, _ = aligned_flow_values(
        data.get("quarterly_cashflow"),
        data.get("cashflow"),
        STOCK_BASED_COMPENSATION_KEYS,
        data.get("quarterly_income"),
        data.get("income"),
        NET_INCOME_KEYS,
    )

    conversion_ocf = aligned_ocf
    if not is_missing(conversion_ocf) and not is_missing(aligned_sbc) and not _safe_lt(aligned_sbc, 0):
        # Raw OCF can materially overstate "cash conversion" for SBC-heavy businesses.
        conversion_ocf = conversion_ocf - aligned_sbc

    fcfe = None
    if not is_missing(free_cash_flow):
        fcfe = free_cash_flow + (0 if is_missing(net_borrowing) else net_borrowing)

    raw_capex_to_ocf = safe_ratio(capex, operating_cash_flow)
    capex_to_ocf_ratio = raw_capex_to_ocf
    if capex_to_ocf_ratio is not None and capex_to_ocf_ratio < 0:
        capex_to_ocf_ratio = 0.0

    capex_cap = 0.7 if capital_intensive_sector(data) else 0.6
    if capex_to_ocf_ratio is not None and capex_to_ocf_ratio > capex_cap:
        capex_to_ocf_ratio = capex_cap

    fcf_yield = None
    if market_cap_meta["price_consistent"]:
        fcf_yield = safe_ratio(free_cash_flow, market_cap)

    metrics = {
        "OCF": operating_cash_flow,
        "OCF_Margin": safe_div(operating_cash_flow, revenue),
        "FCF": free_cash_flow,
        "FCF_Margin": safe_div(free_cash_flow, revenue),
        "FCF_Yield": fcf_yield,
        "FCFE": fcfe,
        "Capex_to_OCF_Ratio": capex_to_ocf_ratio,
        "Cash_Flow_Coverage": safe_div(operating_cash_flow, total_debt),
        "Cash_Conversion_Ratio": safe_div(conversion_ocf, aligned_net_income),
        "_meta": {
            "fcf_formula": "operating_cash_flow - capex",
            "fcf_source": fcf_meta["source"],
            "fcf_basis": fcf_meta["basis"],
            "fcf_as_of": fcf_meta["as_of"],
            "market_cap_source": market_cap_meta["source"],
            "market_cap_as_of": market_cap_meta["as_of"],
            "price_consistent_market_cap": market_cap_meta["price_consistent"],
            "capex_to_ocf_raw": raw_capex_to_ocf,
            "capex_to_ocf_cap": capex_cap,
            "data_source_priority": "TTM>ANNUAL>FALLBACK",
        },
    }

    return {key: normalize_output(value) for key, value in metrics.items()}
