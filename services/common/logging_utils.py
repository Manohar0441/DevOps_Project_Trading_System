from __future__ import annotations

import logging
from pathlib import Path

from services.common.configuration import DEFAULT_LOG_DIR


def configure_logging(
    service_name: str,
    log_dir: Path | None = None,
    level: int = logging.INFO,
    console: bool = False,
) -> Path:
    target_dir = log_dir or DEFAULT_LOG_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    log_path = target_dir / f"{service_name}.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    resolved_target = log_path.resolve()
    for handler in root_logger.handlers:
        if isinstance(handler, logging.FileHandler):
            existing = Path(handler.baseFilename).resolve()
            if existing == resolved_target:
                break
    else:
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    if console:
        has_console_handler = any(
            isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler)
            for handler in root_logger.handlers
        )
        if not has_console_handler:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            root_logger.addHandler(console_handler)

    return log_path

