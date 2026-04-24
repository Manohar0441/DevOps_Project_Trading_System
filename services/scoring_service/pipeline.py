from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.common.configuration import get_metric_definitions
from services.scoring_service.errors import InputValidationError
from services.scoring_service.engine import ManualScoringEngine
from services.scoring_service.output_writer import OutputWriter


logger = logging.getLogger(__name__)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ManualInputParser:
    def __init__(self) -> None:
        self.metric_keys = set(get_metric_definitions())

    def parse(
        self,
        ticker: str | None = None,
        input_path: str | None = None,
        user_inputs_path: str | None = None,
        inline_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        base_payload = self._read_json(input_path) if input_path else {}
        override_payload = self._read_json(user_inputs_path) if user_inputs_path else {}
        inline_payload = inline_payload or {}

        logger.debug(
            "Parsing manual input payloads | ticker=%s | input_path=%s | user_inputs_path=%s | inline_keys=%s",
            ticker,
            input_path,
            user_inputs_path,
            sorted(inline_payload.keys()),
        )

        combined_payload = self._merge_payloads(base_payload, override_payload, inline_payload)
        resolved_ticker = (
            ticker
            or combined_payload.get("ticker")
            or combined_payload.get("symbol")
            or combined_payload.get("meta", {}).get("ticker")
            or combined_payload.get("metadata", {}).get("ticker")
        )
        if resolved_ticker:
            resolved_ticker = str(resolved_ticker).upper()

        metrics, parser_debug = self._extract_metrics(combined_payload)
        metadata = {
            key: value
            for key, value in combined_payload.items()
            if key not in self.metric_keys and key not in {"ticker", "symbol", "metrics"}
        }

        logger.debug(
            "Completed payload parse | ticker=%s | extracted_metrics=%s | derived_metrics=%s | unresolved=%s",
            resolved_ticker,
            len(parser_debug["extracted_metrics"]),
            len(parser_debug["derived_metrics"]),
            parser_debug["unresolved_metrics"],
        )

        return {
            "ticker": resolved_ticker,
            "metrics": metrics,
            "metadata": metadata,
            "raw_input": combined_payload,
            "parser_debug": parser_debug,
        }

    def _read_json(self, path: str) -> dict[str, Any]:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Expected a JSON object in {path}")
        return payload

    def _merge_payloads(
        self,
        base_payload: dict[str, Any],
        override_payload: dict[str, Any],
        inline_payload: dict[str, Any],
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        payload.update(base_payload)
        payload.update({key: value for key, value in override_payload.items() if key != "metrics"})
        payload.update({key: value for key, value in inline_payload.items() if key != "metrics"})

        for candidate in (base_payload, override_payload, inline_payload):
            candidate_metrics = candidate.get("metrics")
            if isinstance(candidate_metrics, dict):
                existing_metrics = payload.get("metrics", {})
                if not isinstance(existing_metrics, dict):
                    existing_metrics = {}
                payload["metrics"] = self._deep_merge_dicts(existing_metrics, candidate_metrics)
        return payload

    def _deep_merge_dicts(self, base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
        merged = dict(base)
        for key, value in incoming.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = self._deep_merge_dicts(merged[key], value)
            else:
                merged[key] = value
        return merged

    def _extract_metrics(self, payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        metrics: dict[str, Any] = {}
        extracted_metrics: list[dict[str, Any]] = []
        derived_metrics: list[dict[str, Any]] = []

        self._collect_metric_candidates(payload, "", metrics, extracted_metrics)
        self._apply_derived_metrics(payload, metrics, derived_metrics)

        parser_debug = {
            "input_shape": {
                "top_level_keys": sorted(payload.keys()),
                "metrics_container_keys": sorted(payload.get("metrics", {}).keys())
                if isinstance(payload.get("metrics"), dict)
                else [],
            },
            "extracted_metrics": extracted_metrics,
            "derived_metrics": derived_metrics,
            "unresolved_metrics": sorted(self.metric_keys.difference(metrics)),
        }
        return metrics, parser_debug

    def _collect_metric_candidates(
        self,
        node: Any,
        path: str,
        metrics: dict[str, Any],
        extracted_metrics: list[dict[str, Any]],
    ) -> None:
        if not isinstance(node, dict):
            return

        for key, value in node.items():
            current_path = f"{path}.{key}" if path else key

            if key in self.metric_keys:
                extracted = self._extract_metric_value(key, value, current_path)
                if extracted is not None:
                    previous_value = metrics.get(key)
                    metrics[key] = extracted["value"]
                    extracted_metrics.append(
                        {
                            "metric_key": key,
                            "source_path": extracted["source_path"],
                            "value": extracted["value"],
                            "mode": extracted["mode"],
                            "overrode_previous_value": previous_value is not None,
                        }
                    )

            if isinstance(value, dict):
                self._collect_metric_candidates(value, current_path, metrics, extracted_metrics)

    def _extract_metric_value(
        self,
        metric_key: str,
        value: Any,
        current_path: str,
    ) -> dict[str, Any] | None:
        if isinstance(value, dict):
            for field_name in ("status", "value", "label", "category", "signal"):
                candidate = value.get(field_name)
                if candidate not in (None, ""):
                    return {
                        "value": candidate,
                        "source_path": f"{current_path}.{field_name}",
                        "mode": "object-field",
                    }
            return None

        if value in (None, ""):
            return None

        return {
            "value": value,
            "source_path": current_path,
            "mode": "direct",
        }

    def _apply_derived_metrics(
        self,
        payload: dict[str, Any],
        metrics: dict[str, Any],
        derived_metrics: list[dict[str, Any]],
    ) -> None:
        if "pe_ratio_relative" not in metrics:
            pe_ratio = self._find_first_value(payload, {"pe_ratio"})
            industry_average = self._find_first_value(
                payload,
                {"pe_ratio_industry_avg", "industry_average_pe", "industry_avg_pe"},
            )
            if pe_ratio is not None and industry_average is not None:
                pe_ratio_value = self._as_float(pe_ratio["value"])
                industry_average_value = self._as_float(industry_average["value"])
                if pe_ratio_value is not None and industry_average_value not in (None, 0):
                    metrics["pe_ratio_relative"] = pe_ratio_value / industry_average_value
                    derived_metrics.append(
                        {
                            "metric_key": "pe_ratio_relative",
                            "value": metrics["pe_ratio_relative"],
                            "formula": "pe_ratio / pe_ratio_industry_avg",
                            "sources": [
                                {
                                    "path": pe_ratio["path"],
                                    "value": pe_ratio_value,
                                },
                                {
                                    "path": industry_average["path"],
                                    "value": industry_average_value,
                                },
                            ],
                        }
                    )

        if "analyst_sentiment" not in metrics:
            upgrades = self._find_first_value(payload, {"upgrades"})
            downgrades = self._find_first_value(payload, {"downgrades"})
            if upgrades is not None and downgrades is not None:
                upgrades_value = self._as_float(upgrades["value"])
                downgrades_value = self._as_float(downgrades["value"])
                if upgrades_value is not None and downgrades_value is not None:
                    metrics["analyst_sentiment"] = self._derive_analyst_sentiment(
                        upgrades_value,
                        downgrades_value,
                    )
                    derived_metrics.append(
                        {
                            "metric_key": "analyst_sentiment",
                            "value": metrics["analyst_sentiment"],
                            "formula": "derived from analyst_actions upgrades/downgrades",
                            "sources": [
                                {
                                    "path": upgrades["path"],
                                    "value": upgrades_value,
                                },
                                {
                                    "path": downgrades["path"],
                                    "value": downgrades_value,
                                },
                            ],
                        }
                    )
            else:
                sentiment_shift = self._find_first_value(payload, {"analyst_sentiment_shift"})
                if sentiment_shift is not None and isinstance(sentiment_shift["value"], str):
                    shift_value = sentiment_shift["value"].strip().lower()
                    shift_map = {
                        "positive": "more_upgrades",
                        "raised": "more_upgrades",
                        "negative": "more_downgrades",
                        "downgraded": "more_downgrades",
                        "neutral": "neutral",
                    }
                    if shift_value in shift_map:
                        metrics["analyst_sentiment"] = shift_map[shift_value]
                        derived_metrics.append(
                            {
                                "metric_key": "analyst_sentiment",
                                "value": metrics["analyst_sentiment"],
                                "formula": "mapped from analyst_sentiment_shift",
                                "sources": [
                                    {
                                        "path": sentiment_shift["path"],
                                        "value": sentiment_shift["value"],
                                    }
                                ],
                            }
                        )

    def _find_first_value(self, node: Any, target_keys: set[str], path: str = "") -> dict[str, Any] | None:
        if not isinstance(node, dict):
            return None

        for key, value in node.items():
            current_path = f"{path}.{key}" if path else key
            if key in target_keys:
                return {"path": current_path, "value": value}
            if isinstance(value, dict):
                nested_result = self._find_first_value(value, target_keys, current_path)
                if nested_result is not None:
                    return nested_result
        return None

    def _derive_analyst_sentiment(self, upgrades: float, downgrades: float) -> str:
        if upgrades > downgrades:
            if downgrades == 0 or (upgrades >= downgrades * 2 and upgrades - downgrades >= 5):
                return "strong_upgrades"
            return "more_upgrades"
        if downgrades > upgrades:
            return "more_downgrades"
        return "neutral"

    def _as_float(self, value: Any) -> float | None:
        if value is None or isinstance(value, bool):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


class ManualScoringPipeline:
    def __init__(self, ticker: str) -> None:
        self.ticker = ticker.upper()
        self.input_parser = ManualInputParser()
        self.engine = ManualScoringEngine()
        self.output_writer = OutputWriter()

    def run(
        self,
        input_path: str | None = None,
        user_inputs_path: str | None = None,
        inline_payload: dict[str, Any] | None = None,
        output_dir: str | None = None,
        write_outputs: bool = False,
    ) -> dict[str, Any]:
        logger.info(
            "Starting manual scoring pipeline | ticker=%s | input_path=%s | user_inputs_path=%s | write_outputs=%s",
            self.ticker,
            input_path,
            user_inputs_path,
            write_outputs,
        )
        parsed = self.input_parser.parse(
            ticker=self.ticker,
            input_path=input_path,
            user_inputs_path=user_inputs_path,
            inline_payload=inline_payload,
        )
        if parsed["ticker"]:
            self.ticker = parsed["ticker"]

        try:
            scoring_result = self.engine.evaluate(self.ticker, parsed["metrics"])
        except InputValidationError as exc:
            logger.warning(
                "Validation failed for %s | details=%s",
                self.ticker,
                exc.errors,
            )
            failure_bundle = {
                "ticker": self.ticker,
                "generated_at": utc_now_iso(),
                "error": str(exc),
                "details": exc.errors,
                "metadata": parsed["metadata"],
                "parsed_metrics": parsed["metrics"],
                "parser_debug": parsed["parser_debug"],
                "raw_input": parsed["raw_input"],
            }
            if write_outputs:
                exc.failure_output_files = self.output_writer.write_failure(
                    ticker=self.ticker,
                    bundle=failure_bundle,
                    output_dir=output_dir or "outputs",
                )
            raise

        standardized_output = {
            "ticker": self.ticker,
            "generated_at": utc_now_iso(),
            "total_score": scoring_result["total_score"],
            "max_score": scoring_result["max_score"],
            "pass_threshold": scoring_result["pass_threshold"],
            "decision": scoring_result["decision"],
            "sections": scoring_result["sections"],
            "score_breakdown": scoring_result["score_breakdown"],
            "rejection_reasons": scoring_result["rejection_reasons"],
        }
        audit_log = {
            "ticker": self.ticker,
            "generated_at": utc_now_iso(),
            "metadata": parsed["metadata"],
            "parser_debug": parsed["parser_debug"],
            "normalized_metrics": scoring_result["normalized_metrics"],
            "evaluation_trace": scoring_result["sections"],
        }
        input_payload = {
            "ticker": self.ticker,
            "generated_at": utc_now_iso(),
            "payload": parsed["raw_input"],
        }
        bundle = {
            "standardized_output": standardized_output,
            "audit_log": audit_log,
            "input_payload": input_payload,
        }
        if write_outputs:
            bundle["output_files"] = self.output_writer.write(
                ticker=self.ticker,
                bundle=bundle,
                output_dir=output_dir or "outputs",
            )
        logger.info(
            "Completed manual scoring pipeline | ticker=%s | total_score=%.2f | decision=%s",
            self.ticker,
            standardized_output["total_score"],
            standardized_output["decision"],
        )
        return bundle
