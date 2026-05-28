from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from services.scoring_service.errors import InputValidationError
from services.scoring_service.pipeline import ManualScoringPipeline


logger = logging.getLogger(__name__)


class BatchScoringService:
    def __init__(self, max_workers: int = 10) -> None:
        self.max_workers = max_workers

    def run_jobs(
        self,
        jobs: list[dict[str, Any]],
        output_dir: str = "outputs",
        write_outputs: bool = True,
    ) -> dict[str, Any]:
        ordered_results: list[dict[str, Any] | None] = [None] * len(jobs)

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._run_single_job, job, output_dir, write_outputs): index
                for index, job in enumerate(jobs)
            }
            for future in as_completed(futures):
                index = futures[future]
                ordered_results[index] = future.result()

        results = [result for result in ordered_results if result is not None]
        success_count = sum(1 for result in results if result["status"] == "success")
        failure_count = len(results) - success_count
        return {
            "results": results,
            "summary": {
                "total": len(results),
                "success": success_count,
                "failed": failure_count,
            },
        }

    def _run_single_job(
        self,
        job: dict[str, Any],
        output_dir: str,
        write_outputs: bool,
    ) -> dict[str, Any]:
        ticker = str(job.get("ticker") or "UNKNOWN").upper()
        logger.info(
            "Scoring batch job | ticker=%s | input_path=%s | user_inputs_path=%s",
            ticker,
            job.get("input_path"),
            job.get("user_inputs_path"),
        )

        try:
            pipeline = ManualScoringPipeline(ticker)
            bundle = pipeline.run(
                input_path=job.get("input_path"),
                user_inputs_path=job.get("user_inputs_path"),
                inline_payload=job.get("payload"),
                output_dir=output_dir,
                write_outputs=write_outputs,
            )
            standardized_output = bundle["standardized_output"]
            return {
                "ticker": standardized_output["ticker"],
                "score": standardized_output["total_score"],
                "decision": standardized_output["decision"],
                "status": "success",
            }
        except InputValidationError as exc:
            failure_output_files = getattr(exc, "failure_output_files", None)
            logger.warning(
                "Validation failed for %s: %s | details=%s | failure_output_files=%s",
                ticker,
                exc,
                exc.errors,
                failure_output_files,
            )
            return {
                "ticker": ticker,
                "status": "failed",
                "error": str(exc),
                "details": exc.errors,
                "failure_output_files": failure_output_files,
            }
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unhandled batch failure for %s: %s", ticker, exc)
            return {
                "ticker": ticker,
                "status": "failed",
                "error": str(exc),
                "details": [],
            }
