from utils.financials import (
    NET_INCOME_KEYS,
    OPERATING_CASH_FLOW_KEYS,
    REVENUE_KEYS,
    STOCK_BASED_COMPENSATION_KEYS,
    aligned_flow_values,
    capex_value,
    cashflow_value,
    current_free_cash_flow,
    is_missing,
    market_cap_value,
    net_borrowing_value,
    normalize_output,
    normalized_free_cash_flow,
    safe_div,
    total_debt_value,
)
from utils.financials import income_value  # Keep the public function names explicit at call sites.


def compute_cashflow(data):
    info = data.get("info", {}) if isinstance(data.get("info"), dict) else {}

    operating_cash_flow = cashflow_value(data, OPERATING_CASH_FLOW_KEYS)
    revenue = income_value(data, REVENUE_KEYS)
    capex = capex_value(data)
    total_debt = total_debt_value(data)
    net_borrowing = net_borrowing_value(data)
    market_cap = market_cap_value(info)

    free_cash_flow = current_free_cash_flow(data)
    normalized_fcf = normalized_free_cash_flow(data)

    yield_fcf = normalized_fcf
    if is_missing(yield_fcf) or yield_fcf <= 0:
        yield_fcf = None

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
    if not is_missing(conversion_ocf) and not is_missing(aligned_sbc) and aligned_sbc >= 0:
        # Raw OCF can materially overstate "cash conversion" for SBC-heavy businesses.
        conversion_ocf = conversion_ocf - aligned_sbc

    fcfe = None
    if not is_missing(free_cash_flow):
        fcfe = free_cash_flow + (0 if is_missing(net_borrowing) else net_borrowing)

    cash_burn_rate = None
    if not is_missing(free_cash_flow):
        cash_burn_rate = abs(free_cash_flow) / 12 if free_cash_flow < 0 else 0

    metrics = {
        "OCF": operating_cash_flow,
        "OCF_Margin": safe_div(operating_cash_flow, revenue),
        "FCF": free_cash_flow,
        "FCF_Margin": safe_div(free_cash_flow, revenue),
        # Keep this aligned with valuation.py so "FCF Yield" has one definition.
        "FCF_Yield": safe_div(yield_fcf, market_cap),
        "FCFE": fcfe,
        "Capex_to_OCF_Ratio": safe_div(capex, operating_cash_flow),
        "Cash_Flow_Coverage": safe_div(operating_cash_flow, total_debt),
        "Cash_Burn_Rate": cash_burn_rate,
        # Compute cash conversion on a same-period basis, adjusting for SBC when available.
        "Cash_Conversion_Ratio": safe_div(conversion_ocf, aligned_net_income),
    }

    return {key: normalize_output(value) for key, value in metrics.items()}
