from __future__ import annotations


def rule_for_holding_days(holding_days: int) -> dict[str, object]:
    if holding_days <= 7:
        return {"phase": "week_1", "max_loss_pct": 8.0, "action": "Respect initial stop loss"}
    if holding_days <= 21:
        return {"phase": "weeks_2_3", "max_loss_pct": 5.0, "action": "Tighten risk if momentum fades"}
    if holding_days <= 45:
        return {"phase": "weeks_4_6", "max_loss_pct": 3.0, "action": "Protect winners and review thesis"}
    return {"phase": "late_cycle", "max_loss_pct": 2.0, "action": "Prepare exit unless thesis is refreshed"}
