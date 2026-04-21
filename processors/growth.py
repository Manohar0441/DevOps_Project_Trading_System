def compute_growth(data):
    income = data["income"]

    if income.shape[1] < 2:
        return {}

    latest = income.iloc[:, 0]
    prev = income.iloc[:, 1]

    return {
        "Revenue_Growth": (latest["Total Revenue"] - prev["Total Revenue"]) / prev["Total Revenue"],
        "EPS_Growth": (latest["Net Income"] - prev["Net Income"]) / prev["Net Income"]
    }