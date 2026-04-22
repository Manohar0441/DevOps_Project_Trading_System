import subprocess
import time

with open("stocks.txt") as f:
    stocks = [line.strip() for line in f if line.strip()]

for i, ticker in enumerate(stocks, 1):
    print(f"[{i}/{len(stocks)}] Running {ticker}")

    try:
        subprocess.run(
            ["python", "main.py", ticker],
            check=True
        )
    except Exception as e:
        print(f"Error with {ticker}: {e}")

    time.sleep(1)

print("All stocks processed.")