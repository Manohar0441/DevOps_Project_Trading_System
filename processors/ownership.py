def compute_ownership(data):
    info = data.get("info", {})
    institutional_df = data.get("institutional")
    insider_df = data.get("insider")

    # --- Institutional Ownership ---
    institutional_ownership = info.get("heldPercentInstitutions")

    # --- Insider Ownership ---
    insider_ownership = info.get("heldPercentInsiders")

    # --- Insider Trading Activity ---
    insider_activity = None
    if insider_df is not None and not insider_df.empty:
        try:
            # Normalize column names
            cols = [c.lower() for c in insider_df.columns]

            # Identify key columns dynamically
            shares_col = next((c for c in insider_df.columns if "share" in c.lower()), None)
            type_col = next((c for c in insider_df.columns if "type" in c.lower()), None)

            if shares_col and type_col:
                buys = insider_df[insider_df[type_col].str.contains("buy", case=False, na=False)][shares_col].sum()
                sells = insider_df[insider_df[type_col].str.contains("sell", case=False, na=False)][shares_col].sum()

                insider_activity = {
                    "Total_Buy_Shares": buys,
                    "Total_Sell_Shares": sells,
                    "Net_Activity": buys - sells
                }
        except:
            insider_activity = None

    # --- Insider Ownership Concentration ---
    insider_concentration = None
    if insider_df is not None and not insider_df.empty:
        try:
            shares_col = next((c for c in insider_df.columns if "share" in c.lower()), None)
            if shares_col:
                total_shares = insider_df[shares_col].sum()
                if total_shares != 0:
                    top_holders = insider_df.nlargest(5, shares_col)
                    insider_concentration = (
                        top_holders[shares_col].sum() / total_shares
                    )
        except:
            insider_concentration = None

    # --- Public Float ---
    public_float = info.get("floatShares")

    return {
        "Institutional Ownership": institutional_ownership,
        "Insider Trading Activity": insider_activity,
        "Insider Ownership Concentration": insider_concentration,
        "Public Float": public_float
    }