from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT_DIR / "config"
DEFAULT_INPUT_DIR = ROOT_DIR / "inputs"
MANUAL_METRICS_DIR = DEFAULT_INPUT_DIR / "manual_metrics"
STOCKS_FILE = ROOT_DIR / "stocks.txt"
DEFAULT_OUTPUT_DIR = ROOT_DIR / "outputs"
DEFAULT_LOG_DIR = ROOT_DIR / "logs"


@lru_cache(maxsize=1)
def load_scoring_model() -> dict[str, Any]:
    model_path = CONFIG_DIR / "scoring_model.json"
    return json.loads(model_path.read_text(encoding="utf-8"))


def get_metric_definitions() -> dict[str, dict[str, Any]]:
    model = load_scoring_model()
    definitions: dict[str, dict[str, Any]] = {}
    for section_key, section_definition in model["sections"].items():
        for metric_key, metric_definition in section_definition["metrics"].items():
            definitions[metric_key] = {
                **metric_definition,
                "section_key": section_key,
                "section_label": section_definition.get("label", section_key.replace("_", " ").title()),
                "section_weight": section_definition["weight"],
            }
    return definitions
