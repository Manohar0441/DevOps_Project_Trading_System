from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from services.common.serialization import to_json_safe


class OutputWriter:
    def write(self, ticker: str, bundle: dict[str, Any], output_dir: str = "outputs") -> dict[str, str]:
        target_dir = Path(output_dir) / ticker.upper()
        target_dir.mkdir(parents=True, exist_ok=True)

        standardized_output_path = target_dir / "standardized_output.json"
        audit_log_path = target_dir / "audit_log.json"
        input_payload_path = target_dir / "input_payload.json"
        score_path = target_dir / "score.txt"

        standardized_output_path.write_text(
            json.dumps(to_json_safe(bundle["standardized_output"]), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        audit_log_path.write_text(
            json.dumps(to_json_safe(bundle["audit_log"]), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        input_payload_path.write_text(
            json.dumps(to_json_safe(bundle["input_payload"]), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        score_path.write_text(f"{bundle['standardized_output']['total_score']:.2f}\n", encoding="utf-8")

        return {
            "standardized_output": str(standardized_output_path),
            "audit_log": str(audit_log_path),
            "input_payload": str(input_payload_path),
            "score": str(score_path),
        }

    def write_failure(self, ticker: str, bundle: dict[str, Any], output_dir: str = "outputs") -> dict[str, str]:
        target_dir = Path(output_dir) / ticker.upper()
        target_dir.mkdir(parents=True, exist_ok=True)

        failure_debug_path = target_dir / "failure_debug.json"
        failure_debug_path.write_text(
            json.dumps(to_json_safe(bundle), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return {
            "failure_debug": str(failure_debug_path),
        }
