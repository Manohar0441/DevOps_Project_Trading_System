import json
import logging

from services.ingestion.fetch_data import FinancialPipeline
from auto_peers_web import get_top_peers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

if __name__ == "__main__":
    ticker = "AAPL"
    peers = get_top_peers("AAPL", top_n=5)

    pipeline = FinancialPipeline(ticker)
    output = pipeline.run(peers=peers)

    # ✅ SAVE TO FILE
    with open("output.json", "w") as f:
        json.dump(output, f, indent=4)

    print("Saved to output.json")