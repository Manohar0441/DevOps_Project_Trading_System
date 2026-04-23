import requests
from bs4 import BeautifulSoup


class PEGScraper:
    def __init__(self, logger=None):
        self.logger = logger

    def _clean(self, value):
        if value in ["N/A", "-", None]:
            return None
        try:
            val = float(str(value).replace("x", "").strip())
            return None if val == 0 else val
        except:
            return None

    def _yahoo(self, ticker):
        try:
            url = f"https://finance.yahoo.com/quote/{ticker}/key-statistics"
            headers = {"User-Agent": "Mozilla/5.0"}

            res = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(res.text, "html.parser")

            rows = soup.find_all("tr")

            for row in rows:
                if "PEG Ratio (5 yr expected)" in row.text:
                    value = row.find_all("td")[1].text.strip()
                    return self._clean(value), "yahoo"

        except Exception as e:
            if self.logger:
                self.logger.warning(f"Yahoo PEG failed: {e}")

        return None, None

    def _finviz(self, ticker):
        try:
            url = f"https://finviz.com/quote.ashx?t={ticker}"
            headers = {"User-Agent": "Mozilla/5.0"}

            res = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(res.text, "html.parser")

            cells = soup.find_all("td")

            for i in range(len(cells)):
                if cells[i].text == "PEG":
                    return self._clean(cells[i + 1].text), "finviz"

        except Exception as e:
            if self.logger:
                self.logger.warning(f"Finviz PEG failed: {e}")

        return None, None

    def get(self, ticker):
        peg, source = self._yahoo(ticker)

        if peg is None:
            peg, source = self._finviz(ticker)

        return peg, source