from datetime import datetime

def track_metrics(metrics):
    return {
        "timestamp": datetime.now().isoformat(),
        "PE": metrics["valuation"].get("PE"),
        "ROE": metrics["profitability"].get("ROE"),
        "FCF": metrics["cashflow"].get("FCF")
    }


def rebalance_signal(metrics):
    if metrics["valuation"].get("PE", 100) > 40:
        return "OVERVALUED - SELL"
    elif metrics["valuation"].get("PE", 0) < 15:
        return "UNDERVALUED - BUY"
    else:
        return "HOLD"