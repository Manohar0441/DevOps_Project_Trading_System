from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from services.screening.helpers import utc_now_iso
from services.screening.input_parser import InputParser
from services.screening.output_writer import OutputWriter
from services.screening.reconciliation import ReconciliationEngine
from services.screening.screening_engine import ScreeningEngine
from services.screening.validation import UserInputValidator
from services.screening.web_scraper import MultiSourceWebScraper


logger = logging.getLogger(__name__)


class ScreeningPipeline:
    def __init__(self, ticker: str):
        self.ticker = ticker.upper()
        self.input_parser = InputParser()
        self.scraper = MultiSourceWebScraper()
        self.reconciliation = ReconciliationEngine()
        self.user_input_validator = UserInputValidator()
        self.screening_engine = ScreeningEngine()
        self.output_writer = OutputWriter()

    def run(
        self,
        peers: Optional[List[str]] = None,
        industry_metrics: Optional[Dict[str, Dict[str, Any]]] = None,
        input_path: Optional[str] = None,
        user_inputs_path: Optional[str] = None,
        user_inputs: Optional[Dict[str, Any]] = None,
        output_dir: Optional[str] = None,
        write_outputs: bool = False,
    ) -> Dict[str, Any]:
        _ = industry_metrics
        parsed = self.input_parser.parse(
            ticker=self.ticker,
            input_path=input_path,
            user_inputs_path=user_inputs_path,
            inline_user_inputs=user_inputs,
        )
        if parsed.get("ticker"):
            self.ticker = parsed["ticker"]

        scrape_bundle = self.scraper.scrape(self.ticker, peers=peers)
        reconciled = self.reconciliation.reconcile(parsed["input_metrics"], scrape_bundle)

        peer_context = dict(scrape_bundle.get("peer_context", {}))
        first_source = next(iter(scrape_bundle.get("sources", {}).values()), {})
        first_metrics = first_source.get("metrics", {}) if isinstance(first_source, dict) else {}
        peer_context.setdefault("sector", first_metrics.get("sector"))
        peer_context.setdefault("industry", first_metrics.get("industry"))

        current_price = reconciled["metrics"].get("current_price", {}).get("final_value")
        user_input_validation = self.user_input_validator.validate(
            {**parsed["user_inputs"], **parsed["additional_user_inputs"]},
            current_price=current_price,
        )
        screening = self.screening_engine.evaluate(
            self.ticker,
            reconciled["metrics"],
            user_input_validation,
            peer_context,
        )

        standardized_output = {
            "ticker": self.ticker,
            "generated_at": utc_now_iso(),
            "peer_context": peer_context,
            "final_reconciled_metrics": reconciled["metrics"],
            "screening_checks": screening["screening_checks"],
            "confidence_levels": {
                key: value.get("confidence")
                for key, value in reconciled["metrics"].items()
                if isinstance(value, dict)
            },
            "data_conflicts": {
                key: value.get("data_conflict")
                for key, value in reconciled["metrics"].items()
                if isinstance(value, dict) and value.get("data_conflict")
            },
            "final_decision": screening["final_decision"],
            "failed_rules": screening["failed_rules"],
            "review_required_metrics": screening["review_required_metrics"],
            "reasons_for_decision": screening["reasons_for_decision"],
        }
        user_inputs_output = {
            "ticker": self.ticker,
            "provided_inputs": {**parsed["user_inputs"], **parsed["additional_user_inputs"]},
            "validation": user_input_validation,
        }
        audit_log = {
            "ticker": self.ticker,
            "generated_at": utc_now_iso(),
            "input_payload": parsed["raw_input"],
            "scraped_sources": scrape_bundle,
            "reconciliation": reconciled["audit_entries"],
            "warnings": scrape_bundle.get("warnings", []),
        }

        bundle = {
            "standardized_output": standardized_output,
            "user_inputs_output": user_inputs_output,
            "audit_log": audit_log,
        }
        if write_outputs:
            bundle["output_files"] = self.output_writer.write(
                ticker=self.ticker,
                bundle=bundle,
                output_dir=output_dir or "outputs",
            )
        return bundle


class FinancialPipeline(ScreeningPipeline):
    pass
