from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional

import requests
import yfinance as yf
from bs4 import BeautifulSoup

from auto_peers_web import get_top_peers
from services.screening.helpers import compute_rsi, normalize_period_label, normalize_ratio, safe_float, utc_now_iso
from utils.financials import (
    EBITDA_KEYS,
    EQUITY_KEYS,
    INTEREST_EXPENSE_KEYS,
    NET_INCOME_KEYS,
    OPERATING_CASH_FLOW_KEYS,
    REVENUE_KEYS,
    balance_value,
    cashflow_value,
    income_value,
    row_series,
    total_debt_value,
)


logger = logging.getLogger(__name__)

INTANGIBLE_KEYS = [
    "Goodwill And Other Intangible Assets",
    "Other Intangible Assets",
    "Intangible Assets",
    "Net Intangible Assets",
    "Goodwill",
]
AMORTIZATION_KEYS = [
    "Amortization",
    "Amortization Of Intangibles",
    "Amortization Of Intangible Assets",
    "Depreciation And Amortization",
]
SEC_HEADERS = {
    "User-Agent": "TradingDevOpsProject/1.0 stock-screening@example.com",
    "Accept-Encoding": "gzip, deflate",
}


def _series_to_quarters(series, limit: int = 8) -> List[Dict[str, Any]]:
    if series is None or getattr(series, "empty", True):
        return []
    items: List[Dict[str, Any]] = []
    for period, value in series.dropna().items():
        numeric = safe_float(value)
        if numeric is None:
            continue
        label = normalize_period_label(period)
        if label is None:
            continue
        items.append({"period": label, "value": numeric})
    return sorted(items, key=lambda item: item["period"], reverse=True)[:limit]


def _quarter_series_to_ttm(items: List[Dict[str, Any]]) -> Optional[float]:
    if len(items) < 4:
        return None
    return sum(item["value"] for item in items[:4])


class YahooFinanceCollector:
    name = "yahoo_finance"

    def collect(self, ticker: str) -> Dict[str, Any]:
        stock = yf.Ticker(ticker)
        info = stock.info or {}
        quarterly_income = getattr(stock, "quarterly_financials", None)
        quarterly_balance = getattr(stock, "quarterly_balance_sheet", None)
        quarterly_cashflow = getattr(stock, "quarterly_cashflow", None)
        annual_income = stock.financials
        annual_balance = stock.balance_sheet
        annual_cashflow = stock.cashflow
        history = stock.history(period="2y", auto_adjust=False)

        quarterly_revenue = _series_to_quarters(row_series(quarterly_income, REVENUE_KEYS))
        quarterly_net_income = _series_to_quarters(row_series(quarterly_income, NET_INCOME_KEYS))
        quarterly_ocf = _series_to_quarters(row_series(quarterly_cashflow, OPERATING_CASH_FLOW_KEYS))
        quarterly_ebitda = _series_to_quarters(row_series(quarterly_income, EBITDA_KEYS))

        data_context = {
            "quarterly_income": quarterly_income,
            "quarterly_balance": quarterly_balance,
            "quarterly_cashflow": quarterly_cashflow,
            "income": annual_income,
            "balance": annual_balance,
            "cashflow": annual_cashflow,
        }

        revenue = _quarter_series_to_ttm(quarterly_revenue) or safe_float(income_value(data_context, REVENUE_KEYS))
        net_income = _quarter_series_to_ttm(quarterly_net_income) or safe_float(income_value(data_context, NET_INCOME_KEYS))
        operating_cash_flow = _quarter_series_to_ttm(quarterly_ocf) or safe_float(cashflow_value(data_context, OPERATING_CASH_FLOW_KEYS))
        ebitda = _quarter_series_to_ttm(quarterly_ebitda) or safe_float(info.get("ebitda"))
        debt = safe_float(total_debt_value(data_context))
        equity = safe_float(balance_value(data_context, EQUITY_KEYS))
        interest_expense = safe_float(income_value(data_context, INTEREST_EXPENSE_KEYS))
        intangibles = safe_float(balance_value(data_context, INTANGIBLE_KEYS))
        amortization = safe_float(cashflow_value(data_context, AMORTIZATION_KEYS))
        shares_outstanding = safe_float(info.get("sharesOutstanding") or info.get("impliedSharesOutstanding"))
        pe_ratio = safe_float(info.get("trailingPE") or info.get("forwardPE"))
        current_price = safe_float(info.get("currentPrice") or info.get("regularMarketPrice"))
        recent_high = safe_float(info.get("fiftyTwoWeekHigh"))
        revenue_growth = normalize_ratio(info.get("revenueGrowth"))

        close_column = None
        if history is not None and not history.empty:
            if "Adj Close" in history.columns:
                close_column = "Adj Close"
            elif "Close" in history.columns:
                close_column = "Close"
        price_series = history[close_column].dropna().astype(float).tolist() if close_column else []
        if current_price is None and price_series:
            current_price = float(price_series[-1])
        if recent_high is None and price_series:
            recent_high = max(price_series[-252:] or price_series)
        rsi = compute_rsi(price_series[-100:]) if price_series else None

        metrics = {
            "revenue": revenue,
            "revenue_growth": revenue_growth,
            "net_income": net_income,
            "net_profit_margin": (net_income / revenue) if revenue not in (None, 0) and net_income is not None else None,
            "operating_cash_flow": operating_cash_flow,
            "ebitda": ebitda,
            "debt": debt,
            "debt_to_equity": (debt / equity) if equity not in (None, 0) and debt is not None else None,
            "interest_expense": interest_expense,
            "intangibles": intangibles,
            "amortization": amortization,
            "shares_outstanding": shares_outstanding,
            "pe_ratio": pe_ratio,
            "current_price": current_price,
            "recent_high": recent_high,
            "rsi": rsi,
            "pullback_percentage": ((recent_high - current_price) / recent_high)
            if recent_high not in (None, 0) and current_price is not None
            else None,
            "quarterly_revenue": quarterly_revenue,
            "quarterly_net_income": quarterly_net_income,
            "quarterly_operating_cash_flow": quarterly_ocf,
            "quarterly_ebitda": quarterly_ebitda,
            "quarterly_net_profit_margin": self._margin_series(quarterly_net_income, quarterly_revenue),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
        }
        return {
            "source": self.name,
            "collected_at": utc_now_iso(),
            "metrics": metrics,
            "warnings": [],
        }

    def _margin_series(
        self,
        income_series: List[Dict[str, Any]],
        revenue_series: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        revenue_map = {item["period"]: item["value"] for item in revenue_series}
        margins = []
        for item in income_series:
            revenue = revenue_map.get(item["period"])
            if revenue in (None, 0):
                continue
            margins.append({"period": item["period"], "value": item["value"] / revenue})
        return margins


class FinvizCollector:
    name = "finviz"

    def __init__(self, session: requests.Session):
        self.session = session

    def collect(self, ticker: str) -> Dict[str, Any]:
        url = f"https://finviz.com/quote.ashx?t={ticker}"
        response = self.session.get(url, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        snapshot: Dict[str, Any] = {}
        table = soup.find("table", class_="snapshot-table2")
        if table is None:
            raise ValueError("Finviz snapshot table not found")

        cells = [cell.get_text(strip=True) for cell in table.find_all("td")]
        for index in range(0, len(cells) - 1, 2):
            snapshot[cells[index]] = cells[index + 1]

        price = safe_float(snapshot.get("Price"))
        pct_from_high = normalize_ratio(snapshot.get("52W High"))
        recent_high = None
        if price is not None and pct_from_high is not None:
            divisor = 1 + pct_from_high
            if divisor != 0:
                recent_high = price / divisor

        metrics = {
            "revenue": safe_float(snapshot.get("Sales")),
            "net_income": safe_float(snapshot.get("Income")),
            "net_profit_margin": normalize_ratio(snapshot.get("Profit Margin")),
            "debt_to_equity": normalize_ratio(snapshot.get("Debt/Eq")),
            "shares_outstanding": safe_float(snapshot.get("Shs Outstand")),
            "pe_ratio": safe_float(snapshot.get("P/E")),
            "current_price": price,
            "recent_high": recent_high,
            "rsi": safe_float(snapshot.get("RSI (14)")),
            "pullback_percentage": ((recent_high - price) / recent_high)
            if recent_high not in (None, 0) and price is not None
            else None,
        }
        return {
            "source": self.name,
            "collected_at": utc_now_iso(),
            "metrics": metrics,
            "warnings": [],
        }


class SecCompanyFactsCollector:
    name = "sec_companyfacts"
    company_ticker_url = "https://www.sec.gov/files/company_tickers.json"

    fact_candidates = {
        "revenue": ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"),
        "net_income": ("NetIncomeLoss",),
        "operating_cash_flow": (
            "NetCashProvidedByUsedInOperatingActivities",
            "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
        ),
        "interest_expense": ("InterestExpenseAndDebtExpense", "InterestExpense"),
        "amortization": (
            "AmortizationOfIntangibleAssets",
            "FiniteLivedIntangibleAssetsAmortizationExpense",
            "DepreciationDepletionAndAmortization",
        ),
        "intangibles": (
            "GoodwillAndIntangibleAssetsNet",
            "IntangibleAssetsNetExcludingGoodwill",
            "FiniteLivedIntangibleAssetsNet",
        ),
        "equity": (
            "StockholdersEquity",
            "StockholdersEquityIncludingPortionAttributedToNoncontrollingInterest",
        ),
        "debt_total": (
            "LongTermDebtAndCapitalLeaseObligations",
            "LongTermDebtAndFinanceLeaseObligations",
        ),
        "debt_current": (
            "LongTermDebtAndCapitalLeaseObligationsCurrent",
            "LongTermDebtAndFinanceLeaseObligationsCurrent",
            "LongTermDebtCurrent",
            "ShortTermBorrowings",
        ),
        "debt_noncurrent": (
            "LongTermDebtAndCapitalLeaseObligationsNoncurrent",
            "LongTermDebtAndFinanceLeaseObligationsNoncurrent",
            "LongTermDebtNoncurrent",
        ),
        "shares_outstanding": ("EntityCommonStockSharesOutstanding",),
        "operating_income": ("OperatingIncomeLoss",),
        "depreciation": ("DepreciationDepletionAndAmortization",),
    }

    def __init__(self, session: requests.Session):
        self.session = session

    def collect(self, ticker: str) -> Dict[str, Any]:
        cik = self._lookup_cik(ticker)
        if cik is None:
            raise ValueError(f"Unable to resolve SEC CIK for {ticker}")

        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
        response = self.session.get(url, headers=SEC_HEADERS, timeout=20)
        response.raise_for_status()
        payload = response.json()

        quarterly_revenue = self._quarter_series(payload, "revenue")
        quarterly_net_income = self._quarter_series(payload, "net_income")
        quarterly_ocf = self._quarter_series(payload, "operating_cash_flow")
        operating_income_ttm = self._ttm_value(payload, "operating_income")
        depreciation_ttm = self._ttm_value(payload, "depreciation")

        quarterly_ebitda = []
        operating_income_series = self._quarter_series(payload, "operating_income")
        depreciation_series = self._quarter_series(payload, "depreciation")
        depreciation_map = {item["period"]: item["value"] for item in depreciation_series}
        for item in operating_income_series:
            depreciation = depreciation_map.get(item["period"])
            if depreciation is None:
                continue
            quarterly_ebitda.append({"period": item["period"], "value": item["value"] + abs(depreciation)})

        debt = self._latest_value(payload, "debt_total")
        if debt is None:
            current = self._latest_value(payload, "debt_current") or 0.0
            noncurrent = self._latest_value(payload, "debt_noncurrent") or 0.0
            debt = current + noncurrent if current or noncurrent else None
        equity = self._latest_value(payload, "equity")
        revenue = self._ttm_from_series(quarterly_revenue) or self._latest_annual_value(payload, "revenue")
        net_income = self._ttm_from_series(quarterly_net_income) or self._latest_annual_value(payload, "net_income")
        operating_cash_flow = self._ttm_from_series(quarterly_ocf) or self._latest_annual_value(payload, "operating_cash_flow")

        metrics = {
            "revenue": revenue,
            "net_income": net_income,
            "net_profit_margin": (net_income / revenue) if revenue not in (None, 0) and net_income is not None else None,
            "operating_cash_flow": operating_cash_flow,
            "ebitda": (operating_income_ttm + abs(depreciation_ttm))
            if operating_income_ttm is not None and depreciation_ttm is not None
            else None,
            "debt": debt,
            "debt_to_equity": (debt / equity) if debt is not None and equity not in (None, 0) else None,
            "interest_expense": self._ttm_value(payload, "interest_expense") or self._latest_annual_value(payload, "interest_expense"),
            "intangibles": self._latest_value(payload, "intangibles"),
            "amortization": self._ttm_value(payload, "amortization") or self._latest_annual_value(payload, "amortization"),
            "shares_outstanding": self._latest_value(payload, "shares_outstanding", namespaces=("dei",)),
            "quarterly_revenue": quarterly_revenue,
            "quarterly_net_income": quarterly_net_income,
            "quarterly_operating_cash_flow": quarterly_ocf,
            "quarterly_ebitda": quarterly_ebitda,
            "quarterly_net_profit_margin": self._margin_series(quarterly_net_income, quarterly_revenue),
        }
        return {
            "source": self.name,
            "collected_at": utc_now_iso(),
            "metrics": metrics,
            "warnings": [],
        }

    def _lookup_cik(self, ticker: str) -> Optional[int]:
        response = self.session.get(self.company_ticker_url, headers=SEC_HEADERS, timeout=20)
        response.raise_for_status()
        payload = response.json()
        for entry in payload.values():
            if str(entry.get("ticker", "")).upper() == ticker.upper():
                return int(entry["cik_str"])
        return None

    def _units_for(
        self,
        payload: Dict[str, Any],
        metric_key: str,
        namespaces: Iterable[str] = ("us-gaap",),
    ) -> List[Dict[str, Any]]:
        facts = payload.get("facts", {})
        for namespace in namespaces:
            namespace_facts = facts.get(namespace, {}) or {}
            for tag in self.fact_candidates[metric_key]:
                fact = namespace_facts.get(tag)
                if not fact:
                    continue
                units = fact.get("units", {})
                for unit_name in ("USD", "USD/shares", "shares"):
                    if unit_name in units:
                        return units[unit_name]
        return []

    def _filter_quarters(self, facts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        filtered = []
        for fact in facts:
            form = str(fact.get("form", ""))
            fp = str(fact.get("fp", ""))
            if form not in {"10-Q", "10-Q/A", "10-K", "10-K/A"}:
                continue
            if fp and fp not in {"Q1", "Q2", "Q3", "Q4", "FY"}:
                continue
            period = normalize_period_label(fact.get("end"))
            value = safe_float(fact.get("val"))
            if period is None or value is None:
                continue
            filtered.append({"period": period, "value": value, "form": form, "fp": fp})
        filtered.sort(key=lambda item: item["period"], reverse=True)
        deduped: Dict[str, Dict[str, Any]] = {}
        for item in filtered:
            deduped.setdefault(item["period"], item)
        return list(deduped.values())

    def _quarter_series(self, payload: Dict[str, Any], metric_key: str) -> List[Dict[str, Any]]:
        units = self._units_for(payload, metric_key)
        facts = self._filter_quarters(units)
        quarters = [item for item in facts if item["fp"].startswith("Q")][:8]
        return [{"period": item["period"], "value": item["value"]} for item in quarters]

    def _latest_annual_value(self, payload: Dict[str, Any], metric_key: str) -> Optional[float]:
        units = self._units_for(payload, metric_key)
        annuals = [item for item in self._filter_quarters(units) if item["fp"] in {"FY", "Q4"}]
        return annuals[0]["value"] if annuals else None

    def _ttm_from_series(self, series: List[Dict[str, Any]]) -> Optional[float]:
        if len(series) < 4:
            return None
        return sum(item["value"] for item in series[:4])

    def _ttm_value(self, payload: Dict[str, Any], metric_key: str) -> Optional[float]:
        return self._ttm_from_series(self._quarter_series(payload, metric_key))

    def _latest_value(
        self,
        payload: Dict[str, Any],
        metric_key: str,
        namespaces: Iterable[str] = ("us-gaap",),
    ) -> Optional[float]:
        units = self._units_for(payload, metric_key, namespaces=namespaces)
        facts = self._filter_quarters(units)
        return facts[0]["value"] if facts else None

    def _margin_series(
        self,
        income_series: List[Dict[str, Any]],
        revenue_series: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        revenue_map = {item["period"]: item["value"] for item in revenue_series}
        margins = []
        for item in income_series:
            revenue = revenue_map.get(item["period"])
            if revenue in (None, 0):
                continue
            margins.append({"period": item["period"], "value": item["value"] / revenue})
        return margins


class MultiSourceWebScraper:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})
        self.collectors = [
            YahooFinanceCollector(),
            FinvizCollector(self.session),
            SecCompanyFactsCollector(self.session),
        ]

    def scrape(self, ticker: str, peers: Optional[List[str]] = None) -> Dict[str, Any]:
        source_payloads: Dict[str, Any] = {}
        warnings: List[str] = []
        for collector in self.collectors:
            try:
                source_payloads[collector.name] = collector.collect(ticker)
            except Exception as exc:  # noqa: BLE001
                warning = f"{collector.name} scrape failed: {exc}"
                logger.warning(warning)
                warnings.append(warning)

        peer_context = self._derive_peer_context(ticker, peers)
        return {
            "ticker": ticker,
            "scraped_at": utc_now_iso(),
            "sources": source_payloads,
            "warnings": warnings,
            "peer_context": peer_context,
        }

    def _derive_peer_context(self, ticker: str, peers: Optional[List[str]]) -> Dict[str, Any]:
        peer_list = list(peers or [])
        if not peer_list:
            try:
                peer_list = get_top_peers(ticker, top_n=8) or []
            except Exception as exc:  # noqa: BLE001
                logger.warning("Peer discovery failed for %s: %s", ticker, exc)
                peer_list = []

        pe_values = []
        for peer in peer_list[:8]:
            try:
                peer_info = yf.Ticker(peer).info or {}
                pe = safe_float(peer_info.get("trailingPE") or peer_info.get("forwardPE"))
                if pe is not None and pe > 0:
                    pe_values.append(pe)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Peer P/E fetch failed for %s: %s", peer, exc)

        return {
            "peers": sorted({str(peer).upper() for peer in peer_list}),
            "industry_average_pe": (sum(pe_values) / len(pe_values)) if pe_values else None,
        }
