from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from services.scoring_service.workflow_store import normalize_tickers, register_tickers, save_manual_metrics_payload


class WorkflowStoreTests(unittest.TestCase):
    def test_normalize_tickers_accepts_comma_separated_input(self) -> None:
        tickers = normalize_tickers("msft, mu, nvda, MU")
        self.assertEqual(tickers, ["MSFT", "MU", "NVDA"])

    def test_register_tickers_appends_uniquely(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            stocks_file = Path(temp_dir) / "stocks.txt"
            stocks_file.write_text("MSFT\n", encoding="utf-8")

            result = register_tickers("MSFT, MU, NVDA", expected_count=3, stocks_file=stocks_file)

            self.assertEqual(result["added_tickers"], ["MU", "NVDA"])
            self.assertEqual(
                stocks_file.read_text(encoding="utf-8").splitlines(),
                ["MSFT", "MU", "NVDA"],
            )

    def test_save_manual_metrics_payload_writes_ticker_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manual_dir = Path(temp_dir) / "manual_metrics"
            payload = {
                "ticker": "MU",
                "metrics": {
                    "growth_quality": {
                        "eps_growth_yoy": 180.0,
                    }
                },
            }

            target_path = save_manual_metrics_payload(payload=payload, ticker="MU", manual_metrics_dir=manual_dir)

            self.assertTrue(target_path.exists())
            written_payload = json.loads(target_path.read_text(encoding="utf-8"))
            self.assertEqual(written_payload["ticker"], "MU")


if __name__ == "__main__":
    unittest.main()
