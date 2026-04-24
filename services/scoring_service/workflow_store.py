from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from services.common.configuration import MANUAL_METRICS_DIR, STOCKS_FILE


TICKER_PATTERN = re.compile(r"^[A-Z][A-Z0-9.\-]{0,14}$")


def normalize_tickers(raw_tickers: str | list[str]) -> list[str]:
    if isinstance(raw_tickers, str):
        candidates = [token.strip().upper() for token in raw_tickers.replace("\n", ",").split(",")]
    else:
        candidates = [str(token).strip().upper() for token in raw_tickers]

    tickers: list[str] = []
    for candidate in candidates:
        if not candidate:
            continue
        if candidate not in tickers:
            tickers.append(candidate)

    if not tickers:
        raise ValueError("Provide at least one ticker.")

    invalid = [ticker for ticker in tickers if not TICKER_PATTERN.fullmatch(ticker)]
    if invalid:
        raise ValueError(f"Invalid ticker values: {', '.join(invalid)}")

    return tickers


def register_tickers(
    raw_tickers: str | list[str],
    expected_count: int | None = None,
    stocks_file: Path = STOCKS_FILE,
) -> dict[str, Any]:
    tickers = normalize_tickers(raw_tickers)
    if expected_count is not None and expected_count != len(tickers):
        raise ValueError(
            f"Ticker count mismatch. Expected {expected_count}, received {len(tickers)} ticker values."
        )

    stocks_file.parent.mkdir(parents=True, exist_ok=True)
    existing_tickers = []
    if stocks_file.exists():
        existing_tickers = [line.strip().upper() for line in stocks_file.read_text(encoding="utf-8").splitlines() if line.strip()]

    updated_tickers = list(existing_tickers)
    added_tickers: list[str] = []
    for ticker in tickers:
        if ticker not in updated_tickers:
            updated_tickers.append(ticker)
            added_tickers.append(ticker)

    stocks_file.write_text("".join(f"{ticker}\n" for ticker in updated_tickers), encoding="utf-8")
    return {
        "requested_tickers": tickers,
        "added_tickers": added_tickers,
        "all_tickers": updated_tickers,
        "stocks_file": str(stocks_file),
    }


def save_manual_metrics_payload(
    payload: dict[str, Any],
    ticker: str,
    manual_metrics_dir: Path = MANUAL_METRICS_DIR,
) -> Path:
    normalized_ticker = ticker.strip().upper()
    if not TICKER_PATTERN.fullmatch(normalized_ticker):
        raise ValueError(f"Invalid ticker value: {normalized_ticker}")

    manual_metrics_dir.mkdir(parents=True, exist_ok=True)
    target_path = manual_metrics_dir / f"{normalized_ticker}.json"

    payload_to_write = dict(payload)
    payload_to_write["ticker"] = normalized_ticker
    target_path.write_text(json.dumps(payload_to_write, indent=2), encoding="utf-8")
    return target_path
