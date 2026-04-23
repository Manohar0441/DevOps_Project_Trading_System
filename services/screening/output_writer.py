from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from services.screening.helpers import to_json_safe


class OutputWriter:
    def write(self, ticker: str, bundle: Dict[str, Any], output_dir: str = "outputs") -> Dict[str, str]:
        target_dir = Path(output_dir) / ticker.upper()
        target_dir.mkdir(parents=True, exist_ok=True)

        files = {
            "standardized_output": target_dir / "standardized_output.json",
            "rejected_stocks": target_dir / "rejected_stocks.json",
            "user_inputs": target_dir / "user_inputs.json",
            "audit_log": target_dir / "audit_log.json",
        }

        standardized_output = bundle["standardized_output"]
        rejection_payload = []
        if standardized_output["final_decision"] == "REJECT":
            rejection_payload.append(
                {
                    "ticker": ticker.upper(),
                    "failed_rules": standardized_output["failed_rules"],
                    "reason_for_rejection": standardized_output["reasons_for_decision"],
                    "metrics_causing_failure": standardized_output["failed_rules"],
                }
            )

        files["standardized_output"].write_text(
            json.dumps(to_json_safe(standardized_output), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        files["rejected_stocks"].write_text(
            json.dumps(to_json_safe(rejection_payload), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        files["user_inputs"].write_text(
            json.dumps(to_json_safe(bundle["user_inputs_output"]), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        files["audit_log"].write_text(
            json.dumps(to_json_safe(bundle["audit_log"]), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return {key: str(path) for key, path in files.items()}
