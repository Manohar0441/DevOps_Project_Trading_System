from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


PERCENT_METRICS = {
    "revenue_growth",
    "net_profit_margin",
    "debt_to_equity",
    "rsi",
    "pullback_percentage",
}

SERIES_METRICS = {
    "quarterly_revenue",
    "quarterly_net_income",
    "quarterly_operating_cash_flow",
    "quarterly_ebitda",
    "quarterly_net_profit_margin",
}

CRITICAL_METRICS = {
    "revenue_growth",
    "net_profit_margin",
    "operating_cash_flow",
    "net_income",
    "debt_to_equity",
    "pe_ratio",
    "industry_average_pe",
    "current_price",
    "recent_high",
    "rsi",
    "pullback_percentage",
    "quarterly_revenue",
    "quarterly_net_income",
}

SECTOR_DEBT_LIMITS = {
    "financial services": 4.0,
    "banks": 6.0,
    "insurance": 4.0,
    "utilities": 3.5,
    "real estate": 3.5,
}

USER_INPUT_KEYS = (
    "entry_price",
    "stop_loss",
    "target_price",
    "exit_logic",
    "risk_level",
)


@dataclass(frozen=True)
class MetricDefinition:
    key: str
    label: str
    aliases: Tuple[str, ...]
    input_aliases: Tuple[str, ...]
    required: bool = False


METRIC_DEFINITIONS = {
    "revenue": MetricDefinition(
        key="revenue",
        label="Revenue",
        aliases=("revenue", "sales", "total_revenue"),
        input_aliases=("Revenue", "revenue", "sales", "total_revenue"),
    ),
    "revenue_growth": MetricDefinition(
        key="revenue_growth",
        label="Revenue Growth",
        aliases=("revenue_growth", "revenue_growth_rate", "sales_growth"),
        input_aliases=("Revenue_Growth", "Revenue Growth", "revenue_growth"),
        required=True,
    ),
    "net_income": MetricDefinition(
        key="net_income",
        label="Net Income",
        aliases=("net_income", "income", "earnings"),
        input_aliases=("Net_Income", "net_income", "earnings"),
        required=True,
    ),
    "net_profit_margin": MetricDefinition(
        key="net_profit_margin",
        label="Net Profit Margin",
        aliases=("net_profit_margin", "profit_margin", "net_margin"),
        input_aliases=("Net_Margin", "Net Profit Margin", "net_profit_margin"),
        required=True,
    ),
    "operating_cash_flow": MetricDefinition(
        key="operating_cash_flow",
        label="Operating Cash Flow",
        aliases=("operating_cash_flow", "ocf", "cash_from_operations"),
        input_aliases=("OCF", "Operating Cash Flow", "operating_cash_flow"),
        required=True,
    ),
    "ebitda": MetricDefinition(
        key="ebitda",
        label="EBITDA",
        aliases=("ebitda",),
        input_aliases=("EBITDA", "ebitda"),
    ),
    "debt": MetricDefinition(
        key="debt",
        label="Debt",
        aliases=("debt", "total_debt"),
        input_aliases=("Debt", "Total_Debt", "total_debt"),
    ),
    "debt_to_equity": MetricDefinition(
        key="debt_to_equity",
        label="Debt to Equity",
        aliases=("debt_to_equity", "debt_equity", "debt_to_equity_ratio"),
        input_aliases=("Debt_to_Equity", "Debt to Equity", "debt_to_equity"),
        required=True,
    ),
    "interest_expense": MetricDefinition(
        key="interest_expense",
        label="Interest Expense",
        aliases=("interest_expense",),
        input_aliases=("Interest_Expense", "interest_expense"),
    ),
    "intangibles": MetricDefinition(
        key="intangibles",
        label="Intangibles",
        aliases=("intangibles", "intangible_assets", "goodwill_and_intangibles"),
        input_aliases=("Intangibles", "intangibles", "intangible_assets"),
    ),
    "amortization": MetricDefinition(
        key="amortization",
        label="Amortization",
        aliases=("amortization", "amortisation"),
        input_aliases=("Amortization", "amortization"),
    ),
    "shares_outstanding": MetricDefinition(
        key="shares_outstanding",
        label="Shares Outstanding",
        aliases=("shares_outstanding", "shares", "shares_out"),
        input_aliases=("Shares_Outstanding", "shares_outstanding", "shares"),
    ),
    "pe_ratio": MetricDefinition(
        key="pe_ratio",
        label="P/E Ratio",
        aliases=("pe_ratio", "pe", "trailing_pe"),
        input_aliases=("PE", "P/E", "pe_ratio"),
        required=True,
    ),
    "industry_average_pe": MetricDefinition(
        key="industry_average_pe",
        label="Industry Average P/E",
        aliases=("industry_average_pe", "industry_pe", "peer_average_pe"),
        input_aliases=("Industry_Average_PE", "industry_average_pe", "industry_pe"),
        required=True,
    ),
    "current_price": MetricDefinition(
        key="current_price",
        label="Current Price",
        aliases=("current_price", "price", "entry_reference_price"),
        input_aliases=("Current_Price", "current_price", "price"),
        required=True,
    ),
    "recent_high": MetricDefinition(
        key="recent_high",
        label="Recent High",
        aliases=("recent_high", "fifty_two_week_high", "52_week_high"),
        input_aliases=("Recent_High", "recent_high", "52_week_high"),
        required=True,
    ),
    "rsi": MetricDefinition(
        key="rsi",
        label="RSI",
        aliases=("rsi", "rsi_14", "rsi14"),
        input_aliases=("RSI", "rsi", "rsi_14"),
        required=True,
    ),
    "pullback_percentage": MetricDefinition(
        key="pullback_percentage",
        label="Pullback Percentage",
        aliases=("pullback_percentage", "pullback_pct"),
        input_aliases=("Pullback_Percentage", "pullback_percentage", "pullback_pct"),
        required=True,
    ),
    "quarterly_revenue": MetricDefinition(
        key="quarterly_revenue",
        label="Quarterly Revenue",
        aliases=("quarterly_revenue",),
        input_aliases=("quarterly_revenue", "Quarterly_Revenue"),
        required=True,
    ),
    "quarterly_net_income": MetricDefinition(
        key="quarterly_net_income",
        label="Quarterly Net Income",
        aliases=("quarterly_net_income",),
        input_aliases=("quarterly_net_income", "Quarterly_Net_Income"),
        required=True,
    ),
    "quarterly_operating_cash_flow": MetricDefinition(
        key="quarterly_operating_cash_flow",
        label="Quarterly Operating Cash Flow",
        aliases=("quarterly_operating_cash_flow",),
        input_aliases=("quarterly_operating_cash_flow", "Quarterly_Operating_Cash_Flow"),
    ),
    "quarterly_ebitda": MetricDefinition(
        key="quarterly_ebitda",
        label="Quarterly EBITDA",
        aliases=("quarterly_ebitda",),
        input_aliases=("quarterly_ebitda", "Quarterly_EBITDA"),
    ),
    "quarterly_net_profit_margin": MetricDefinition(
        key="quarterly_net_profit_margin",
        label="Quarterly Net Profit Margin",
        aliases=("quarterly_net_profit_margin",),
        input_aliases=("quarterly_net_profit_margin", "Quarterly_Net_Profit_Margin"),
    ),
}
