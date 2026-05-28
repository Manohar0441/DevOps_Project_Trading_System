from __future__ import annotations

from collections import defaultdict
from typing import Any


def rank_by_sector(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sectors: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        sector = str(candidate.get("sector") or "Unclassified")
        sectors[sector].append(candidate)

    ranked: list[dict[str, Any]] = []
    for sector, members in sectors.items():
        members.sort(key=lambda item: float(item.get("quality_score", 0)), reverse=True)
        average_score = sum(float(item.get("quality_score", 0)) for item in members) / len(members)
        ranked.append(
            {
                "sector": sector,
                "candidate_count": len(members),
                "average_quality_score": round(average_score, 2),
                "top_candidates": members[:5],
            }
        )

    ranked.sort(key=lambda item: item["average_quality_score"], reverse=True)
    return ranked
