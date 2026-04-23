print("RUNNING UPDATED MAIN FILE")
import json
import logging
import sys
import os
from venv import logger
from services.ingestion.fetch_data import FinancialPipeline
from services.enrichment.peg_scraper import PEGScraper

from auto_peers_web import get_top_peers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

def run_pipeline(ticker):
    logging.info(f"Starting pipeline for {ticker}")

    # ✅ Peer safety
    try:
        peers = get_top_peers(ticker, top_n=10) or []
    except Exception as e:
        logging.warning(f"Peer fetch failed for {ticker}: {e}")
        peers = []

    pipeline = FinancialPipeline(ticker)
    output = pipeline.run(peers=peers)

    # ✅ PEG enrichment
    peg_scraper = PEGScraper(logger)
    peg, source = peg_scraper.get(ticker)
    output["valuation"] = output.get("valuation", {})
    output["valuation"]["PEG"] = peg
    output["valuation"].setdefault("_meta", {})
    output["valuation"]["_meta"]["peg_source"] = source

    # ✅ Optional metadata (useful for debugging)
    output["meta"] = {
        "ticker": ticker,
        "peer_count": len(peers),
        "peers": peers,
    }

    return output


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <TICKER>")
        sys.exit(1)

    ticker = sys.argv[1].upper()

    try:
        output = run_pipeline(ticker)

        os.makedirs("outputs", exist_ok=True)

        file_path = f"outputs/{ticker}.json"

        with open(file_path, "w") as f:
            json.dump(output, f, indent=4)

        print(f"{ticker} saved successfully")

    except Exception as e:
        logging.error(f"Pipeline failed for {ticker}: {e}")

        os.makedirs("failed", exist_ok=True)
        with open(f"failed/{ticker}.txt", "w") as f:
            f.write(str(e))
