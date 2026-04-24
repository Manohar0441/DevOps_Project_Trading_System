from __future__ import annotations

import unittest

from services.scoring_service.engine import ManualScoringEngine
from services.scoring_service.errors import InputValidationError


VALID_METRICS = {
    "eps_growth_yoy": 24.5,
    "revenue_growth_yoy": 14.2,
    "ocf_growth_yoy": 17.3,
    "ocf_to_net_income": 1.24,
    "operating_margin": 31.8,
    "net_profit_margin": 27.9,
    "roic": 19.4,
    "roe": 31.2,
    "debt_to_equity": 0.34,
    "current_ratio": 1.92,
    "interest_coverage": 12.4,
    "pe_ratio_relative": 0.95,
    "peg_ratio": 1.18,
    "ev_ebitda": 14.1,
    "relative_strength": "strong_outperformance",
    "analyst_sentiment": "more_upgrades",
    "volume_trend": "stable",
}


class ManualScoringEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = ManualScoringEngine()

    def test_scores_expected_sample_payload(self) -> None:
        result = self.engine.evaluate("MSFT", VALID_METRICS)
        self.assertEqual(result["decision"], "ACCEPT")
        self.assertAlmostEqual(result["total_score"], 89.17, places=2)

    def test_accepts_decimal_percentages(self) -> None:
        metrics = dict(VALID_METRICS)
        metrics["eps_growth_yoy"] = 0.245
        metrics["revenue_growth_yoy"] = 0.142
        metrics["ocf_growth_yoy"] = 0.173
        metrics["operating_margin"] = 0.318
        metrics["net_profit_margin"] = 0.279
        metrics["roic"] = 0.194
        metrics["roe"] = 0.312

        result = self.engine.evaluate("MSFT", metrics)
        self.assertEqual(result["decision"], "ACCEPT")
        self.assertAlmostEqual(result["total_score"], 89.17, places=2)

    def test_missing_metric_raises_validation_error(self) -> None:
        metrics = dict(VALID_METRICS)
        metrics.pop("roe")

        with self.assertRaises(InputValidationError) as context:
            self.engine.evaluate("MSFT", metrics)

        self.assertIn("Missing required metric: roe", context.exception.errors)


if __name__ == "__main__":
    unittest.main()
