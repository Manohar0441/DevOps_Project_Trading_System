# Batch Input Files

`batchrunner.py` always reads tickers from `stocks.txt`.

For each ticker, you can optionally provide:

- stock input JSON in `inputs/stock_data/<TICKER>.json`
- user trade input JSON in `inputs/user_inputs/<TICKER>.json`

Example:

- `inputs/stock_data/MSFT.json`
- `inputs/user_inputs/MSFT.json`

The runner also accepts these fallback names:

- `inputs/<TICKER>.stock.json`
- `inputs/<TICKER>.user.json`
- `inputs/<TICKER>.json` for stock data

## Stock Input Shape

```json
{
  "ticker": "MSFT",
  "valuation": {
    "PE": 28.1
  },
  "growth": {
    "Revenue_Growth": 0.12
  },
  "profitability": {
    "Net_Margin": 0.31
  },
  "cashflow": {
    "OCF": 120000000000
  },
  "technical": {
    "Current_Price": 432.92,
    "Recent_High": 470.0,
    "RSI": 61.2
  },
  "quarterly_revenue": {
    "2025-12-31": 69632000000,
    "2025-09-30": 65585000000
  },
  "quarterly_net_income": {
    "2025-12-31": 24108000000,
    "2025-09-30": 24667000000
  }
}
```

## User Input Shape

```json
{
  "entry_price": 410.0,
  "stop_loss": 385.4,
  "target_price": 460.0,
  "exit_logic": "Exit if RSI > 75 or price reaches target.",
  "risk_level": "medium"
}
```
