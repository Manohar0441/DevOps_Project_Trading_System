import logging
from typing import Any, Dict, List, Optional

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
from processors.benchmarking import compare_with_peers, comparative_analysis
from processors.integrated_analysis import integrated_analysis
from processors.tracking import track_metrics, rebalance_signal
from processors.competitive import competitive_analysis

logger = logging.getLogger(__name__)


def _is_numeric(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _average_numeric_sections(peer_data: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Build a lightweight industry proxy from peer averages.
    This is used when no external industry dataset is available.
    """
    sections = [
        "valuation",
        "profitability",
        "growth",
        "financial_health",
        "cashflow",
        "risk",
        "ownership",
    ]

    industry_metrics: Dict[str, Dict[str, Any]] = {}

    for section in sections:
        collected: Dict[str, List[float]] = {}

        for peer in peer_data:
            section_data = peer.get(section, {}) or {}
            for key, value in section_data.items():
                if _is_numeric(value):
                    collected.setdefault(key, []).append(float(value))

        averaged_section: Dict[str, Any] = {}
        for key, values in collected.items():
            if values:
                averaged_section[key] = sum(values) / len(values)

        if averaged_section:
            industry_metrics[section] = averaged_section

    return industry_metrics


def _log_section_summary(name: str, section_data: Any) -> None:
    if isinstance(section_data, dict):
        keys = list(section_data.keys())
        logger.info("%s completed with %d keys: %s", name, len(keys), keys[:8])
    else:
        logger.info("%s completed.", name)


class FinancialPipeline:
    def __init__(self, ticker: str):
        self.ticker = ticker
        self.provider = YahooProvider(ticker)

    def run(
        self,
        peers: Optional[List[str]] = None,
        industry_metrics: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        logger.info("Starting pipeline for ticker: %s", self.ticker)

        raw = self.provider.fetch_all()
        logger.info("Raw data fetched for %s", self.ticker)

        metrics: Dict[str, Any] = {}

        # Core Metrics
        metrics["valuation"] = compute_valuation(raw)
        _log_section_summary("valuation", metrics["valuation"])

        metrics["profitability"] = compute_profitability(raw)
        _log_section_summary("profitability", metrics["profitability"])

        metrics["financial_health"] = compute_financial_health(raw)
        _log_section_summary("financial_health", metrics["financial_health"])

        metrics["cashflow"] = compute_cashflow(raw)
        _log_section_summary("cashflow", metrics["cashflow"])

        metrics["growth"] = compute_growth(raw)
        _log_section_summary("growth", metrics["growth"])

        metrics["risk"] = compute_risk(raw)
        _log_section_summary("risk", metrics["risk"])

        # Ownership
        metrics["ownership"] = compute_ownership(raw)
        _log_section_summary("ownership", metrics["ownership"])

        # Competitive
        metrics["competitive"] = competitive_analysis(metrics, raw)
        _log_section_summary("competitive", metrics["competitive"])

        # Valuation Models
        metrics["valuation_models"] = {
            "DCF": compute_dcf(raw),
            "WACC": compute_wacc(raw),
            "Graham_Number": graham_number(raw),
        }
        _log_section_summary("valuation_models", metrics["valuation_models"])

        # Screening
        metrics["screening"] = screening_framework(metrics)
        _log_section_summary("screening", metrics["screening"])

        # Peer Pipeline
        peer_data: List[Dict[str, Any]] = []
        if peers:
            logger.info("Fetching and computing peer metrics for %d peers.", len(peers))
            for peer_ticker in peers:
                logger.info("Processing peer: %s", peer_ticker)
                peer_pipeline = FinancialPipeline(peer_ticker)
                peer_metrics = peer_pipeline.run(peers=None, industry_metrics=None)
                peer_data.append(peer_metrics)
            logger.info("Peer processing completed. Total peers collected: %d", len(peer_data))
        else:
            logger.info("No peers provided.")

        # Industry proxy from peer data if not provided
        if industry_metrics is None:
            industry_metrics = _average_numeric_sections(peer_data) if peer_data else {}
            if industry_metrics:
                logger.info("Industry proxy built from peer averages.")
            else:
                logger.info("No industry proxy available. Industry benchmarking may be partial.")

        # Benchmarking
        if peer_data:
            metrics["benchmarking"] = compare_with_peers(metrics, peer_data)
            _log_section_summary("benchmarking", metrics["benchmarking"])
        else:
            metrics["benchmarking"] = {}
            logger.info("benchmarking skipped due to no peer data.")

        # Comparative Analysis
        metrics["comparative_analysis"] = comparative_analysis(
            company_metrics=metrics,
            peer_metrics_list=peer_data,
            price_data=raw.get("price"),
            industry_metrics=industry_metrics or {},
        )
        _log_section_summary("comparative_analysis", metrics["comparative_analysis"])

        # Integrated Analysis
        metrics["integrated"] = integrated_analysis(metrics)
        _log_section_summary("integrated", metrics["integrated"])

        # Tracking
        metrics["tracking"] = track_metrics(metrics)
        _log_section_summary("tracking", metrics["tracking"])

        metrics["rebalance"] = rebalance_signal(metrics)
        logger.info("Rebalance signal generated: %s", metrics["rebalance"])

        logger.info("Pipeline completed for ticker: %s", self.ticker)
        return metrics