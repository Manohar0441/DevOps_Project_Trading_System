from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from services.scoring_service.errors import InputValidationError
from services.scoring_service.pipeline import ManualInputParser, ManualScoringPipeline


class ManualScoringPipelineTests(unittest.TestCase):
    def test_parser_accepts_nested_metric_sections_and_derivations(self) -> None:
        payload = {
            "ticker": "MU",
            "as_of_date": "2026-04-24",
            "metrics": {
                "growth_quality": {
                    "eps_growth_yoy": 180.0,
                    "revenue_growth_yoy": 52.0,
                    "ocf_growth_yoy": 95.0,
                    "ocf_to_net_income": 1.35,
                },
                "profitability": {
                    "operating_margin": 28.5,
                    "net_profit_margin": 22.0,
                    "roic": 16.5,
                    "roe": 18.2,
                },
                "financial_health": {
                    "debt_to_equity": 0.32,
                    "current_ratio": 2.6,
                    "interest_coverage": 9.5,
                },
                "valuation_sanity": {
                    "pe_ratio": 18.5,
                    "pe_ratio_industry_avg": 22.0,
                    "peg_ratio": 0.9,
                    "ev_ebitda": 9.8,
                },
                "monitoring": {
                    "relative_strength": {
                        "status": "strong_outperformance",
                        "outperformance_percent": 18.0,
                    },
                    "analyst_actions": {
                        "upgrades": 18,
                        "downgrades": 5,
                    },
                    "volume_trend": "increasing",
                },
            },
        }

        parser = ManualInputParser()
        parsed = parser.parse(inline_payload=payload)

        self.assertEqual(parsed["metrics"]["eps_growth_yoy"], 180.0)
        self.assertEqual(parsed["metrics"]["relative_strength"], "strong_outperformance")
        self.assertEqual(parsed["metrics"]["analyst_sentiment"], "strong_upgrades")
        self.assertAlmostEqual(parsed["metrics"]["pe_ratio_relative"], 18.5 / 22.0, places=6)
        self.assertEqual(parsed["parser_debug"]["unresolved_metrics"], [])

    def test_pipeline_writes_expected_output_files(self) -> None:
        payload = {
            "ticker": "MSFT",
            "metrics": {
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
            },
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_path = temp_path / "MSFT.json"
            input_path.write_text(json.dumps(payload), encoding="utf-8")

            pipeline = ManualScoringPipeline("MSFT")
            bundle = pipeline.run(
                input_path=str(input_path),
                output_dir=str(temp_path / "outputs"),
                write_outputs=True,
            )

            self.assertEqual(bundle["standardized_output"]["decision"], "ACCEPT")
            output_files = bundle["output_files"]
            for key in ("standardized_output", "audit_log", "input_payload", "score"):
                self.assertTrue(Path(output_files[key]).exists())

    def test_pipeline_writes_failure_debug_file_for_invalid_payload(self) -> None:
        payload = {
            "ticker": "MU",
            "metrics": {
                "growth_quality": {
                    "eps_growth_yoy": 180.0,
                }
            },
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_path = temp_path / "MU.json"
            output_dir = temp_path / "outputs"
            input_path.write_text(json.dumps(payload), encoding="utf-8")

            pipeline = ManualScoringPipeline("MU")
            with self.assertRaises(InputValidationError) as context:
                pipeline.run(
                    input_path=str(input_path),
                    output_dir=str(output_dir),
                    write_outputs=True,
                )

            failure_output_files = getattr(context.exception, "failure_output_files", {})
            self.assertIn("failure_debug", failure_output_files)
            self.assertTrue(Path(failure_output_files["failure_debug"]).exists())


if __name__ == "__main__":
    unittest.main()
