from __future__ import annotations

import argparse
import logging
from pathlib import Path

from services.common.logging_utils import configure_logging
from services.scoring_service.pipeline import ManualScoringPipeline


logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manual-input stock scoring pipeline")
    parser.add_argument("ticker", nargs="?", help="US stock ticker")
    parser.add_argument("--input-json", dest="input_json", help="Path to the primary stock scoring JSON")
    parser.add_argument(
        "--user-inputs",
        dest="user_inputs",
        help="Optional path to an override JSON containing metrics or metadata",
    )
    parser.add_argument("--output-dir", dest="output_dir", default="outputs", help="Base output directory")
    return parser


def run_pipeline(args: argparse.Namespace) -> dict:
    if not args.ticker and not args.input_json and not args.user_inputs:
        raise ValueError("Provide a ticker and at least one input payload path.")

    pipeline = ManualScoringPipeline((args.ticker or "").upper() or "UNKNOWN")
    return pipeline.run(
        input_path=args.input_json,
        user_inputs_path=args.user_inputs,
        output_dir=args.output_dir,
        write_outputs=True,
    )


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    configure_logging("main-cli", log_dir=Path(args.output_dir) / "_logs", level=logging.DEBUG, console=False)

    try:
        bundle = run_pipeline(args)
        score = bundle["standardized_output"]["total_score"]
        print(f"{score:.2f}")
    except Exception as exc:  # noqa: BLE001
        logger.exception("Pipeline failed: %s", exc)
        failed_dir = Path("failed")
        failed_dir.mkdir(exist_ok=True)
        failed_ticker = (args.ticker or "UNKNOWN").upper()
        (failed_dir / f"{failed_ticker}.txt").write_text(str(exc), encoding="utf-8")
        raise
