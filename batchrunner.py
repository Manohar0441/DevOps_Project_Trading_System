from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from services.batch_service.runner import BatchScoringService
from services.common.logging_utils import configure_logging


MAX_WORKERS = int(os.environ.get("BATCH_MAX_WORKERS", "10"))
BASE_DIR = Path(__file__).resolve().parent
STOCKS_FILE = BASE_DIR / "stocks.txt"
OUTPUT_DIR = Path(os.environ.get("BATCH_OUTPUT_DIR", str(BASE_DIR / "outputs")))
SUMMARY_PATH = OUTPUT_DIR / "_batch" / "summary.json"

STOCK_INPUT_CANDIDATES = (
    lambda ticker: BASE_DIR / "inputs" / "manual_metrics" / f"{ticker}.json",
    lambda ticker: BASE_DIR / "inputs" / "stock_data" / f"{ticker}.json",
    lambda ticker: BASE_DIR / "inputs" / f"{ticker}.stock.json",
    lambda ticker: BASE_DIR / "inputs" / f"{ticker}.json",
)

USER_INPUT_CANDIDATES = (
    lambda ticker: BASE_DIR / "inputs" / "user_inputs" / f"{ticker}.json",
    lambda ticker: BASE_DIR / "inputs" / f"{ticker}.user.json",
)

logger = logging.getLogger(__name__)


def load_tickers(path: Path) -> list[str]:
    with path.open(encoding="utf-8") as handle:
        return [line.strip().upper() for line in handle if line.strip()]


def resolve_optional_input(ticker: str, candidates) -> Path | None:
    for candidate in candidates:
        path = candidate(ticker)
        if path.exists() and path.is_file():
            return path
    return None


def build_jobs(tickers: list[str]) -> list[dict[str, str | None]]:
    jobs = []
    for ticker in tickers:
        jobs.append(
            {
                "ticker": ticker,
                "input_path": str(resolve_optional_input(ticker, STOCK_INPUT_CANDIDATES) or ""),
                "user_inputs_path": str(resolve_optional_input(ticker, USER_INPUT_CANDIDATES) or ""),
            }
        )
    return jobs


def normalize_job_paths(jobs: list[dict[str, str | None]]) -> list[dict[str, str | None]]:
    normalized: list[dict[str, str | None]] = []
    for job in jobs:
        normalized.append(
            {
                "ticker": job["ticker"],
                "input_path": job["input_path"] or None,
                "user_inputs_path": job["user_inputs_path"] or None,
            }
        )
    return normalized


def main() -> None:
    (OUTPUT_DIR / "_batch").mkdir(parents=True, exist_ok=True)
    configure_logging("batchrunner", log_dir=OUTPUT_DIR / "_batch", level=logging.DEBUG, console=False)

    tickers = load_tickers(STOCKS_FILE)
    jobs = normalize_job_paths(build_jobs(tickers))
    logger.debug("Prepared batch jobs: %s", jobs)
    service = BatchScoringService(max_workers=MAX_WORKERS)
    result = service.run_jobs(jobs=jobs, output_dir=str(OUTPUT_DIR), write_outputs=True)

    SUMMARY_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")
    for stock_result in result["results"]:
        if stock_result["status"] == "success":
            print(f"{stock_result['ticker']}: {stock_result['score']:.2f}")
        else:
            logger.error(
                "Batch scoring failed for %s: %s | details=%s | failure_output_files=%s",
                stock_result["ticker"],
                stock_result.get("error"),
                stock_result.get("details"),
                stock_result.get("failure_output_files"),
            )
            print(f"{stock_result['ticker']}: ERROR")


if __name__ == "__main__":
    main()
