import yfinance as yf
import pandas as pd


# -----------------------------------
# 1. Get Sector
# -----------------------------------
def get_sector(ticker):
    stock = yf.Ticker(ticker)
    return stock.info.get("sector")


# -----------------------------------
# 2. Sector ETFs (Universe Source)
# -----------------------------------
SECTOR_ETF = {
    "Technology": "XLK",
    "Healthcare": "XLV",
    "Financial Services": "XLF",
    "Energy": "XLE",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Industrials": "XLI",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Basic Materials": "XLB"
}


# -----------------------------------
# 3. Get Holdings from ETF
# -----------------------------------
def get_sector_stocks(sector):
    etf = SECTOR_ETF.get(sector)

    if not etf:
        return []

    etf_data = yf.Ticker(etf)

    try:
        holdings = etf_data.get_holdings()
        return holdings["symbol"].tolist()
    except:
        # fallback
        return ["AAPL", "MSFT", "NVDA", "AMD", "INTC"]


# -----------------------------------
# 4. Rank by Performance
# -----------------------------------
def get_return(symbol):
    try:
        data = yf.Ticker(symbol).history(period="1y")

        if data.empty:
            return None

        return (data["Close"].iloc[-1] / data["Close"].iloc[0]) - 1
    except:
        return None


# -----------------------------------
# 5. Main Function
# -----------------------------------
def get_top_peers(ticker, top_n=10):
    print(f"Fetching peers for {ticker}...")

    sector = get_sector(ticker)

    if not sector:
        print("Sector not found")
        return []

    print("Sector:", sector)

    stocks = get_sector_stocks(sector)

    print(f"Found {len(stocks)} stocks")

    performance = []

    for s in stocks:
        ret = get_return(s)

        if ret is not None:
            performance.append((s, ret))

    performance.sort(key=lambda x: x[1], reverse=True)

    top = [x[0] for x in performance[:top_n]]

    print("Top peers:", top)

    return top