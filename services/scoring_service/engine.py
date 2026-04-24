from __future__ import annotations

import logging
import math
import re
from typing import Any

from services.common.configuration import get_metric_definitions, load_scoring_model
from services.scoring_service.errors import InputValidationError


logger = logging.getLogger(__name__)

BAND_ORDER = ("excellent", "good", "poor", "bad")
NUMERIC_PATTERN = re.compile(r"-?\d+(?:\.\d+)?")


def _slugify(value: Any) -> str:
    token = re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower())
    return token.strip("_")


def _parse_numeric_input(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if math.isfinite(float(value)):
            return float(value)
        return None
    if isinstance(value, str):
        cleaned = value.replace(",", "").strip().lower()
        if not cleaned:
            return None
        match = NUMERIC_PATTERN.search(cleaned)
        if not match:
            return None
        numeric = float(match.group())
        if math.isfinite(numeric):
            return numeric
    return None


def _normalize_numeric_value(value: Any, value_type: str) -> float | None:
    numeric = _parse_numeric_input(value)
    if numeric is None:
        return None
    if value_type == "percentage" and abs(numeric) <= 1:
        return numeric * 100
    return numeric


def _clean_rule_expression(expression: str) -> str:
    return (
        expression.lower()
        .replace("industry", "")
        .replace("x", "")
        .replace("%", "")
        .strip()
    )


def _matches_numeric_rule(value: float, expression: str) -> bool:
    cleaned = _clean_rule_expression(expression)
    if cleaned.startswith(">="):
        return value >= float(cleaned[2:].strip())
    if cleaned.startswith("<="):
        return value <= float(cleaned[2:].strip())
    if cleaned.startswith(">"):
        return value > float(cleaned[1:].strip())
    if cleaned.startswith("<"):
        return value < float(cleaned[1:].strip())

    range_match = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)\s*-\s*(-?\d+(?:\.\d+)?)\s*", cleaned)
    if range_match:
        lower_bound = float(range_match.group(1))
        upper_bound = float(range_match.group(2))
        return lower_bound <= value <= upper_bound

    numeric = _parse_numeric_input(cleaned)
    return numeric is not None and value == numeric


class ManualScoringEngine:
    def __init__(self) -> None:
        self.model = load_scoring_model()
        self.metric_definitions = get_metric_definitions()
        self.pass_threshold = float(self.model["pass_threshold"])
        self.total_score = float(self.model["total_score"])
        self.band_scores = {band: float(score) for band, score in self.model["band_scores"].items()}

    def evaluate(self, ticker: str, metrics: dict[str, Any]) -> dict[str, Any]:
        if not ticker:
            raise InputValidationError("Ticker is required.", ["Missing required field: ticker"])

        logger.debug(
            "Evaluating scoring model | ticker=%s | metric_count=%s",
            ticker,
            len(metrics),
        )
        errors: list[str] = []
        section_results: list[dict[str, Any]] = []
        section_score_map: dict[str, float] = {}
        normalized_metrics: dict[str, Any] = {}
        failing_metrics: list[dict[str, Any]] = []

        for section_key, section_definition in self.model["sections"].items():
            section_label = section_definition.get("label", section_key.replace("_", " ").title())
            metrics_in_section = section_definition["metrics"]
            metric_weight = float(section_definition["weight"]) / len(metrics_in_section)
            section_score = 0.0
            metric_results: list[dict[str, Any]] = []

            for metric_key, metric_definition in metrics_in_section.items():
                raw_value = metrics.get(metric_key)
                result = self._evaluate_metric(metric_key, metric_definition, raw_value, metric_weight)
                metric_results.append(result)

                if result["status"] == "error":
                    logger.debug(
                        "Metric validation error | ticker=%s | section=%s | metric=%s | message=%s",
                        ticker,
                        section_key,
                        metric_key,
                        result["message"],
                    )
                    errors.append(result["message"])
                    continue

                normalized_metrics[metric_key] = result["normalized_value"]
                section_score += result["weighted_score"]
                logger.debug(
                    "Metric scored | ticker=%s | section=%s | metric=%s | raw=%r | normalized=%r | band=%s | weighted_score=%.4f",
                    ticker,
                    section_key,
                    metric_key,
                    raw_value,
                    result["normalized_value"],
                    result["band"],
                    result["weighted_score"],
                )
                if result["band"] in {"poor", "bad"}:
                    failing_metrics.append(
                        {
                            "metric_key": metric_key,
                            "label": metric_definition.get("label", metric_key),
                            "band": result["band"],
                            "weighted_score": result["weighted_score"],
                            "matched_rule": result["matched_rule"],
                        }
                    )

            section_score = round(section_score, 4)
            section_score_map[section_key] = section_score
            section_results.append(
                {
                    "section_key": section_key,
                    "label": section_label,
                    "weight": float(section_definition["weight"]),
                    "score": section_score,
                    "metrics": metric_results,
                }
            )
            logger.debug(
                "Section complete | ticker=%s | section=%s | section_score=%.4f",
                ticker,
                section_key,
                section_score,
            )

        if errors:
            logger.warning(
                "Scoring validation failed | ticker=%s | issue_count=%s | issues=%s",
                ticker,
                len(errors),
                errors,
            )
            raise InputValidationError("Input validation failed.", errors)

        total_score = round(sum(section_score_map.values()), 2)
        decision = "ACCEPT" if total_score >= self.pass_threshold else "REJECT"

        if decision == "REJECT":
            rejection_reasons = [
                f"Total score {total_score:.2f} is below the minimum threshold of {self.pass_threshold:.2f}."
            ]
            for metric in failing_metrics:
                rejection_reasons.append(
                    f"{metric['label']} was rated {metric['band']} using rule {metric['matched_rule']}."
                )
        else:
            rejection_reasons = []

        logger.info(
            "Scoring complete | ticker=%s | total_score=%.2f | decision=%s",
            ticker,
            total_score,
            decision,
        )
        return {
            "ticker": ticker.upper(),
            "total_score": total_score,
            "max_score": self.total_score,
            "pass_threshold": self.pass_threshold,
            "decision": decision,
            "sections": section_results,
            "score_breakdown": section_score_map,
            "normalized_metrics": normalized_metrics,
            "rejection_reasons": rejection_reasons,
        }

    def _evaluate_metric(
        self,
        metric_key: str,
        metric_definition: dict[str, Any],
        raw_value: Any,
        metric_weight: float,
    ) -> dict[str, Any]:
        label = metric_definition.get("label", metric_key.replace("_", " ").title())
        rule_type = metric_definition["rule_type"]
        value_type = metric_definition.get("value_type", "ratio")

        if raw_value is None or raw_value == "":
            return {
                "metric_key": metric_key,
                "label": label,
                "status": "error",
                "message": f"Missing required metric: {metric_key}",
            }

        if rule_type == "categorical":
            normalized_value = _slugify(raw_value)
            matched_band = None
            matched_rule = None
            for band in BAND_ORDER:
                candidate = _slugify(metric_definition[band])
                if normalized_value == candidate:
                    matched_band = band
                    matched_rule = metric_definition[band]
                    break
            if matched_band is None:
                allowed = ", ".join(metric_definition[band] for band in BAND_ORDER)
                return {
                    "metric_key": metric_key,
                    "label": label,
                    "status": "error",
                    "message": f"Invalid categorical value for {metric_key}. Allowed values: {allowed}",
                }
        else:
            normalized_value = _normalize_numeric_value(raw_value, value_type)
            if normalized_value is None:
                return {
                    "metric_key": metric_key,
                    "label": label,
                    "status": "error",
                    "message": f"Metric {metric_key} must be numeric.",
                }

            matched_band = None
            matched_rule = None
            for band in BAND_ORDER:
                candidate_rule = metric_definition[band]
                if _matches_numeric_rule(normalized_value, candidate_rule):
                    matched_band = band
                    matched_rule = candidate_rule
                    break

            if matched_band is None:
                return {
                    "metric_key": metric_key,
                    "label": label,
                    "status": "error",
                    "message": f"Metric {metric_key} with value {normalized_value} did not match any scoring band.",
                }

        weighted_score = round(metric_weight * self.band_scores[matched_band], 4)
        max_metric_score = round(metric_weight, 4)
        explanation = (
            f"{label} matched the {matched_band} band using rule {matched_rule}. "
            f"Weighted score awarded: {weighted_score:.4f} out of {max_metric_score:.4f}."
        )

        return {
            "metric_key": metric_key,
            "label": label,
            "raw_value": raw_value,
            "normalized_value": normalized_value,
            "band": matched_band,
            "matched_rule": matched_rule,
            "weight": max_metric_score,
            "weighted_score": weighted_score,
            "status": "scored",
            "explanation": explanation,
        }
