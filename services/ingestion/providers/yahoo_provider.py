import yfinance as yf


class YahooProvider:
    def __init__(self, ticker):
        self.ticker = yf.Ticker(ticker)

    def fetch_all(self):
        return {
            "info": self.ticker.info,
            "income": self.ticker.financials,
            "quarterly_income": getattr(self.ticker, "quarterly_financials", None),
            "balance": self.ticker.balance_sheet,
            "quarterly_balance": getattr(self.ticker, "quarterly_balance_sheet", None),
            "cashflow": self.ticker.cashflow,
            "quarterly_cashflow": getattr(self.ticker, "quarterly_cashflow", None),
            "price": self.ticker.history(period="5y"),
            "dividends": self.ticker.dividends,
            "institutional": self.ticker.institutional_holders,
            "insider": self.ticker.insider_transactions
        }
