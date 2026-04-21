
from utils.helpers import safe_div

def compute_wacc(data):
    info = data["info"]

    market_cap = info.get("marketCap")
    debt = info.get("totalDebt", 0)

    cost_of_equity = 0.10  # assumed (can improve later with CAPM)
    cost_of_debt = 0.05

    total = market_cap + debt
    if not total:
        return None

    return ((market_cap / total) * cost_of_equity) + ((debt / total) * cost_of_debt)


def compute_dcf(data, growth_rate=0.05, discount_rate=0.1, years=5):
    cash = data["cashflow"].iloc[:, 0]
    fcf = cash.get("Total Cash From Operating Activities")

    if not fcf:
        return None

    value = 0
    for i in range(1, years + 1):
        value += fcf * ((1 + growth_rate) ** i) / ((1 + discount_rate) ** i)

    return value


def graham_number(data):
    income = data["income"].iloc[:, 0]
    balance = data["balance"].iloc[:, 0]

    eps = income.get("Net Income")
    book = balance.get("Total Stockholder Equity")

    if not eps or not book:
        return None

    return (22.5 * eps * book) ** 0.5