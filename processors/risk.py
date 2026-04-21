import numpy as np

def compute_risk(data):
    price = data["price"]

    returns = price["Close"].pct_change().dropna()

    return {
        "Volatility": returns.std(),
        "Sharpe": returns.mean() / returns.std()
    }