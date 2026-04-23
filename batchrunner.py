import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


MAX_WORKERS = 10
BASE_DIR = Path(__file__).resolve().parent
STOCKS_FILE = BASE_DIR / "stocks.txt"
OUTPUT_DIR = BASE_DIR / "outputs"

STOCK_INPUT_CANDIDATES = (
    lambda ticker: BASE_DIR / "inputs" / "stock_data" / f"{ticker}.json",
    lambda ticker: BASE_DIR / "inputs" / f"{ticker}.stock.json",
    lambda ticker: BASE_DIR / "inputs" / f"{ticker}.json",
)

USER_INPUT_CANDIDATES = (
    lambda ticker: BASE_DIR / "inputs" / "user_inputs" / f"{ticker}.json",
    lambda ticker: BASE_DIR / "inputs" / f"{ticker}.user.json",
)


def load_tickers(path: Path) -> list[str]:
    with path.open(encoding="utf-8") as handle:
        return [line.strip().upper() for line in handle if line.strip()]


def resolve_optional_input(ticker: str, candidates) -> Path | None:
    for candidate in candidates:
        path = candidate(ticker)
        if path.exists() and path.is_file():
            return path
    return None


def build_command(ticker: str) -> list[str]:
    command = [sys.executable, "main.py", ticker, "--output-dir", str(OUTPUT_DIR)]

    stock_input = resolve_optional_input(ticker, STOCK_INPUT_CANDIDATES)
    user_input = resolve_optional_input(ticker, USER_INPUT_CANDIDATES)

    if stock_input is not None:
        command.extend(["--input-json", str(stock_input)])
    if user_input is not None:
        command.extend(["--user-inputs", str(user_input)])

    return command


def describe_inputs(ticker: str) -> str:
    stock_input = resolve_optional_input(ticker, STOCK_INPUT_CANDIDATES)
    user_input = resolve_optional_input(ticker, USER_INPUT_CANDIDATES)
    parts = []
    if stock_input is not None:
        parts.append(f"stock={stock_input.relative_to(BASE_DIR)}")
    if user_input is not None:
        parts.append(f"user={user_input.relative_to(BASE_DIR)}")
    return ", ".join(parts) if parts else "no extra inputs"


def run_stock(args):
    index, ticker = args
    start = time.time()
    command = build_command(ticker)
    input_description = describe_inputs(ticker)

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            cwd=BASE_DIR,
        )
        duration = time.time() - start
        return ticker, index, True, result.stdout, duration, input_description
    except subprocess.CalledProcessError as exc:
        duration = time.time() - start
        return ticker, index, False, exc.stderr or str(exc), duration, input_description


stocks = load_tickers(STOCKS_FILE)
print(f"Processing {len(stocks)} stocks with {MAX_WORKERS} workers...\n")

results = {"success": [], "failed": []}

with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    futures = {executor.submit(run_stock, (index, ticker)): ticker for index, ticker in enumerate(stocks, 1)}
    for future in as_completed(futures):
        ticker, index, success, output, duration, input_description = future.result()
        if success:
            print(f"[{index}/{len(stocks)}] {ticker} done in {duration:.1f}s")
            print(f"  inputs: {input_description}")
            if output.strip():
                print(f"  {output.strip()[:200]}")
            results["success"].append(ticker)
        else:
            print(f"[{index}/{len(stocks)}] {ticker} FAILED in {duration:.1f}s")
            print(f"  inputs: {input_description}")
            print(f"  {output.strip()[:200]}")
            results["failed"].append(ticker)

print("\n" + "=" * 40)
print(f"Done. {len(results['success'])} succeeded, {len(results['failed'])} failed.")
if results["failed"]:
    print(f"Failed tickers: {', '.join(results['failed'])}")
