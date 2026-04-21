def compute_ownership(data):
    info = data["info"]

    institutional = data["institutional"]
    insider = data["insider"]

    return {
        "institutional_ownership_pct": info.get("heldPercentInstitutions"),
        "insider_ownership_pct": info.get("heldPercentInsiders"),
        "top_institutions": institutional.to_dict() if institutional is not None else None,
        "insider_transactions": insider.to_dict() if insider is not None else None,
        "public_float": info.get("floatShares")
    }