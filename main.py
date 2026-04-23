import argparse
import logging
from pathlib import Path

from services.ingestion.fetch_data import FinancialPipeline


logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit-ready stock screening pipeline")
    parser.add_argument("ticker", nargs="?", help="US stock ticker")
    parser.add_argument("--input-json", dest="input_json", help="Path to the input stock JSON")
    parser.add_argument("--user-inputs", dest="user_inputs", help="Path to user trade inputs JSON")
    parser.add_argument("--output-dir", dest="output_dir", default="outputs", help="Base output directory")
    return parser


def run_pipeline(args: argparse.Namespace) -> dict:
    if not args.ticker and not args.input_json:
        raise ValueError("Provide either a ticker or an input JSON file.")

    pipeline = FinancialPipeline((args.ticker or "").upper() or "UNKNOWN")
    return pipeline.run(
        input_path=args.input_json,
        user_inputs_path=args.user_inputs,
        output_dir=args.output_dir,
        write_outputs=True,
    )


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()

    try:
        bundle = run_pipeline(args)
        ticker = bundle["standardized_output"]["ticker"]
        output_dir = Path(args.output_dir) / ticker
        print(f"{ticker} screening completed")
        print(f"Outputs written to {output_dir}")
    except Exception as exc:  # noqa: BLE001
        logging.exception("Pipeline failed: %s", exc)
        failed_dir = Path("failed")
        failed_dir.mkdir(exist_ok=True)
        failed_ticker = (args.ticker or "UNKNOWN").upper()
        (failed_dir / f"{failed_ticker}.txt").write_text(str(exc), encoding="utf-8")
        raise
