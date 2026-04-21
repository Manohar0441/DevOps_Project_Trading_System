from services.ingestion.providers.yahoo_provider import YahooProvider

from processors.valuation import compute_valuation
from processors.profitability import compute_profitability
from processors.financial_health import compute_financial_health
from processors.cashflow import compute_cashflow
from processors.growth import compute_growth
from processors.risk import compute_risk
from processors.ownership import compute_ownership
from processors.valuation_models import compute_dcf, compute_wacc, graham_number
from processors.screening import screening_framework
from processors.benchmarking import compare_with_peers
from processors.integrated_analysis import integrated_analysis
from processors.tracking import track_metrics, rebalance_signal
from processors.competitive import competitive_analysis

class FinancialPipeline:
    def __init__(self, ticker):
        self.ticker = ticker
        self.provider = YahooProvider(ticker)

    def run(self, peers=None):
        raw = self.provider.fetch_all()

        metrics = {}

        # --- Core Metrics ---
        metrics["valuation"] = compute_valuation(raw)
        metrics["profitability"] = compute_profitability(raw)
        metrics["financial_health"] = compute_financial_health(raw)
        metrics["cashflow"] = compute_cashflow(raw)
        metrics["growth"] = compute_growth(raw)
        metrics["risk"] = compute_risk(raw)

        # --- Ownership ---
        metrics["ownership"] = compute_ownership(raw)

        # --- Competitive ---
        metrics["competitive"] = competitive_analysis(metrics, raw)

        # --- Valuation Models ---
        metrics["valuation_models"] = {
            "DCF": compute_dcf(raw),
            "WACC": compute_wacc(raw),
            "Graham_Number": graham_number(raw)
        }

        # --- Screening ---
        metrics["screening"] = screening_framework(metrics)

        # --- Benchmarking ---
        if peers:
            peer_data = []
            for p in peers:
                peer_pipeline = FinancialPipeline(p)
                peer_metrics = peer_pipeline.run(peers=None)
                peer_data.append(peer_metrics)

            metrics["benchmarking"] = compare_with_peers(metrics, peer_data)

        # --- Integrated Analysis ---
        metrics["integrated"] = integrated_analysis(metrics)

        # --- Tracking ---
        metrics["tracking"] = track_metrics(metrics)
        metrics["rebalance"] = rebalance_signal(metrics)

        return metrics