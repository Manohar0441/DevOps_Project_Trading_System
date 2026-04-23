from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.screening.constants import CRITICAL_METRICS, METRIC_DEFINITIONS, PERCENT_METRICS, SERIES_METRICS
from services.screening.helpers import consensus, normalize_ratio, percent_difference, safe_float


class ReconciliationEngine:
    def reconcile(
        self,
        input_metrics: Dict[str, Any],
        scrape_bundle: Dict[str, Any],
    ) -> Dict[str, Any]:
        reconciled: Dict[str, Any] = {}
        audit_entries: Dict[str, Any] = {}
        requires_review = False

        for key in METRIC_DEFINITIONS:
            if key in SERIES_METRICS:
                record = self._reconcile_series(key, input_metrics.get(key), scrape_bundle)
            else:
                record = self._reconcile_scalar(key, input_metrics.get(key), scrape_bundle)
            reconciled[key] = record
            audit_entries[key] = {
                "input_value": record["input_value"],
                "scraped_values": record["scraped_values"],
                "scraped_consensus": record["scraped_consensus"],
                "final_value": record["final_value"],
                "reconciliation_method": record["source"],
                "confidence": record["confidence"],
                "data_conflict": record["data_conflict"],
                "requires_review": record["requires_review"],
                "percentage_difference": record.get("percentage_difference"),
            }
            requires_review = requires_review or bool(record["requires_review"])

        peer_pe = safe_float(scrape_bundle.get("peer_context", {}).get("industry_average_pe"))
        industry_record = reconciled.get("industry_average_pe", {})
        if peer_pe is not None and industry_record.get("final_value") is None:
            industry_record["final_value"] = peer_pe
            industry_record["scraped_consensus"] = peer_pe
            industry_record["source"] = "scraped_only"

        return {
            "metrics": reconciled,
            "audit_entries": audit_entries,
            "requires_review": requires_review,
        }

    def _reconcile_scalar(
        self,
        key: str,
        input_value: Any,
        scrape_bundle: Dict[str, Any],
    ) -> Dict[str, Any]:
        normalized_input = normalize_ratio(input_value) if key in PERCENT_METRICS else safe_float(input_value)
        scraped_values = self._collect_scraped_scalar_values(key, scrape_bundle)
        scraped_numeric_values = [item["value"] for item in scraped_values if item["value"] is not None]
        scraped_consensus = consensus(scraped_numeric_values)
        scraped_conflict = self._scraped_conflict(scraped_numeric_values, scraped_consensus)
        pct_diff = percent_difference(normalized_input, scraped_consensus)

        record = {
            "input_value": normalized_input,
            "scraped_values": scraped_values,
            "scraped_consensus": scraped_consensus,
            "final_value": None,
            "source": "missing",
            "confidence": "low",
            "data_conflict": scraped_conflict,
            "requires_review": False,
            "data_status": "verified" if scraped_values else "missing",
            "percentage_difference": pct_diff,
        }

        if normalized_input is not None and scraped_consensus is not None:
            if pct_diff is not None and pct_diff <= 0.05:
                record["final_value"] = (normalized_input + scraped_consensus) / 2.0
                record["source"] = "blended"
                record["confidence"] = "high"
            elif pct_diff is not None and pct_diff <= 0.15:
                record["final_value"] = scraped_consensus
                record["source"] = "scraped_priority"
                record["confidence"] = "medium"
            else:
                record["final_value"] = scraped_consensus
                record["source"] = "scraped_priority"
                record["confidence"] = "low"
                record["data_conflict"] = True
                record["requires_review"] = True
        elif normalized_input is None and scraped_consensus is not None:
            record["final_value"] = scraped_consensus
            record["source"] = "scraped_only"
            record["confidence"] = "medium" if len(scraped_numeric_values) >= 2 else "low"
        elif normalized_input is not None and scraped_consensus is None:
            record["final_value"] = normalized_input
            record["source"] = "input_fallback"
            record["confidence"] = "low"
            record["data_status"] = "unverified"
            record["requires_review"] = key in CRITICAL_METRICS
        else:
            record["source"] = "missing"
            record["data_status"] = "missing"
            record["requires_review"] = key in CRITICAL_METRICS

        if scraped_conflict and scraped_consensus is not None:
            record["source"] = "scraped_priority"
            record["confidence"] = "low"
            record["data_conflict"] = True
            record["requires_review"] = True
            if record["final_value"] is None:
                record["final_value"] = scraped_consensus

        return record

    def _reconcile_series(
        self,
        key: str,
        input_value: Any,
        scrape_bundle: Dict[str, Any],
    ) -> Dict[str, Any]:
        input_series = self._normalize_series(input_value)
        scraped_values = self._collect_scraped_series_values(key, scrape_bundle)
        source_series = {item["source"]: self._normalize_series(item["values"]) for item in scraped_values}

        periods = sorted(
            {entry["period"] for entry in input_series}.union(
                {entry["period"] for values in source_series.values() for entry in values}
            ),
            reverse=True,
        )[:8]

        final_series: List[Dict[str, Any]] = []
        consensus_series: List[Dict[str, Any]] = []
        review = False
        conflict = False
        input_map = {item["period"]: item["value"] for item in input_series}
        source_maps = {source: {item["period"]: item["value"] for item in values} for source, values in source_series.items()}

        for period in periods:
            period_scraped = []
            for source_name, series_map in source_maps.items():
                value = series_map.get(period)
                if value is not None:
                    period_scraped.append({"source": source_name, "value": value})
            scraped_consensus = consensus([item["value"] for item in period_scraped])
            input_period_value = input_map.get(period)
            pct_diff = percent_difference(input_period_value, scraped_consensus)
            period_conflict = self._scraped_conflict([item["value"] for item in period_scraped], scraped_consensus)

            if input_period_value is not None and scraped_consensus is not None and pct_diff is not None and pct_diff <= 0.05:
                final_value = (input_period_value + scraped_consensus) / 2.0
            elif scraped_consensus is not None:
                final_value = scraped_consensus
            else:
                final_value = input_period_value

            if period_conflict:
                review = True
                conflict = True

            if final_value is not None:
                final_series.append({"period": period, "value": final_value})
            if scraped_consensus is not None:
                consensus_series.append({"period": period, "value": scraped_consensus})

        if not final_series and key in CRITICAL_METRICS:
            review = True

        return {
            "input_value": input_series,
            "scraped_values": scraped_values,
            "scraped_consensus": consensus_series,
            "final_value": final_series,
            "source": "series_reconciliation",
            "confidence": "high" if final_series and not conflict else "low",
            "data_conflict": conflict,
            "requires_review": review,
            "data_status": "verified" if final_series else "missing",
        }

    def _collect_scraped_scalar_values(self, key: str, scrape_bundle: Dict[str, Any]) -> List[Dict[str, Any]]:
        values = []
        for source_name, payload in sorted(scrape_bundle.get("sources", {}).items()):
            metric_value = payload.get("metrics", {}).get(key)
            numeric = normalize_ratio(metric_value) if key in PERCENT_METRICS else safe_float(metric_value)
            if numeric is not None:
                values.append({"source": source_name, "value": numeric, "collected_at": payload.get("collected_at")})
        if not values and key == "industry_average_pe":
            peer_pe = safe_float(scrape_bundle.get("peer_context", {}).get("industry_average_pe"))
            if peer_pe is not None:
                values.append({"source": "peer_group", "value": peer_pe, "collected_at": scrape_bundle.get("scraped_at")})
        return values

    def _collect_scraped_series_values(self, key: str, scrape_bundle: Dict[str, Any]) -> List[Dict[str, Any]]:
        values = []
        for source_name, payload in sorted(scrape_bundle.get("sources", {}).items()):
            metric_values = payload.get("metrics", {}).get(key) or []
            normalized = self._normalize_series(metric_values)
            if normalized:
                values.append({"source": source_name, "values": normalized, "collected_at": payload.get("collected_at")})
        return values

    def _normalize_series(self, values: Any) -> List[Dict[str, Any]]:
        if not isinstance(values, list):
            return []
        items = []
        for item in values:
            if not isinstance(item, dict):
                continue
            period = item.get("period")
            value = safe_float(item.get("value"))
            if period is None or value is None:
                continue
            items.append({"period": str(period), "value": value})
        return sorted(items, key=lambda entry: entry["period"], reverse=True)[:8]

    def _scraped_conflict(self, values: List[float], reference: Optional[float]) -> bool:
        if reference in (None, 0) or len(values) < 2:
            return False
        for value in values:
            delta = percent_difference(value, reference)
            if delta is not None and delta > 0.15:
                return True
        return False
