import json
from services.ingestion.fetch_data import FinancialPipeline

if __name__ == "__main__":
    print("Starting pipeline...")

    ticker = "META"  # You can change this to any ticker you want to test with

    try:
        pipeline = FinancialPipeline(ticker)

        # IMPORTANT: disable peers for now
        data = pipeline.run(peers=None)

        print("Pipeline executed successfully")

        with open("output.json", "w") as f:
            json.dump(data, f, indent=4, default=str)

        print("Output saved to output.json")

    except Exception as e:
        print("ERROR OCCURRED:")
        print(e)