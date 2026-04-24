# Manual Input Files

`batchrunner.py` reads tickers from `stocks.txt` and then looks for manual scoring payloads.

## Preferred Location

- `inputs/manual_metrics/<TICKER>.json`

Example:

- `inputs/manual_metrics/MSFT.json`

## Backward-Compatible Fallbacks

Primary stock payload:

- `inputs/stock_data/<TICKER>.json`
- `inputs/<TICKER>.stock.json`
- `inputs/<TICKER>.json`

Optional overrides:

- `inputs/user_inputs/<TICKER>.json`
- `inputs/<TICKER>.user.json`

If an override file contains a `metrics` object or metric keys at the top level, those values replace the primary payload.

## Canonical Payload Shape

```json
{
  "ticker": "",
  "as_of_date": "",
  "metrics": {
    
    "growth_quality": {
      "eps_growth_yoy": null,
      "revenue_growth_yoy": null,
      "ocf_growth_yoy": null,
      "ocf_to_net_income": null
    },

    "profitability": {
      "operating_margin": null,
      "net_profit_margin": null,
      "roic": null,
      "roe": null
    },

    "financial_health": {
      "debt_to_equity": null,
      "current_ratio": null,
      "interest_coverage": null
    },

    "valuation_sanity": {
      "pe_ratio": null,
      "pe_ratio_industry_avg": null,
      "peg_ratio": null,
      "ev_ebitda": null
    },

    "monitoring": {
      "relative_strength": {
        "status": "", 
        "outperformance_percent": null
      },
      "earnings_vs_guidance": "",
      "analyst_actions": {
        "upgrades": null,
        "downgrades": null
      },
      "volume_trend": "",
      "gross_margin_trend": "",
      "ocf_vs_net_income_trend": "",
      "capex_percent_sales": null,
      "customer_concentration_trend": ""
    },

    "risk_exit_signals": {
      "margin_compression_bps": null,
      "ocf_less_than_net_income": false,
      "analyst_sentiment_shift": "",
      "guidance_change": "",
      "sector_momentum": "",
      "relative_underperformance_percent": null
    }
  },

  "metadata": {
    "source": "",
    "analyst": ""
  }
}
```

## Value Handling

- Percentage metrics accept either percentage units like `24.5` or decimal form like `0.245`.
- Ratio metrics should be entered as raw numeric ratios.
- Categorical metrics must match one of the configured band values in `config/scoring_model.json`.
- Every scoring metric is required for a valid final score.
- The parser derives `pe_ratio_relative` from `pe_ratio / pe_ratio_industry_avg`.
- The parser derives `analyst_sentiment` from `analyst_actions.upgrades` and `analyst_actions.downgrades` when available.
- If a run fails validation, `outputs/<TICKER>/failure_debug.json` is written with the parser trace and validation issues.
