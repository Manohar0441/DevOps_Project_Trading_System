import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

MAX_WORKERS = 10  # ← tune this to how many you want running at once

with open("stocks.txt") as f:
    stocks = [line.strip() for line in f if line.strip()]

print(f"Processing {len(stocks)} stocks with {MAX_WORKERS} workers...\n")

def run_stock(args):
    i, ticker = args
    start = time.time()
    try:
        result = subprocess.run(
            ["python", "main.py", ticker],
            capture_output=True,
            text=True,
            check=True
        )
        duration = time.time() - start
        return (ticker, i, True, result.stdout, duration)
    except subprocess.CalledProcessError as e:
        duration = time.time() - start
        return (ticker, i, False, e.stderr or str(e), duration)

results = {"success": [], "failed": []}

with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    futures = {executor.submit(run_stock, (i, t)): t for i, t in enumerate(stocks, 1)}

    for future in as_completed(futures):
        ticker, i, success, output, duration = future.result()

        if success:
            print(f"✅ [{i}/{len(stocks)}] {ticker} — done in {duration:.1f}s")
            if output.strip():
                print(f"   └─ {output.strip()[:200]}")  # print first 200 chars of output
            results["success"].append(ticker)
        else:
            print(f"❌ [{i}/{len(stocks)}] {ticker} — FAILED in {duration:.1f}s")
            print(f"   └─ {output.strip()[:200]}")
            results["failed"].append(ticker)

print(f"\n{'='*40}")
print(f"Done. ✅ {len(results['success'])} succeeded, ❌ {len(results['failed'])} failed.")
if results["failed"]:
    print(f"Failed tickers: {', '.join(results['failed'])}")