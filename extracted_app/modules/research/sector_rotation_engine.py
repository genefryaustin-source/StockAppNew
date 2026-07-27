from __future__ import annotations
from typing import Any
from .research_utils import _stable_score

SECTORS = ["Technology", "Healthcare", "Financials", "Industrials", "Consumer", "Energy", "Utilities", "Real Estate", "Materials", "Communication"]


def build_sector_rotation(ticker: str) -> dict[str, Any]:
    rows = []
    for i, s in enumerate(SECTORS):
        score = _stable_score(ticker + s, 70+i, 50, 30)
        rows.append({"Sector": s, "Momentum": score, "Read": "Leading" if score >= 62 else "Lagging" if score <= 38 else "Neutral"})
    rows = sorted(rows, key=lambda r: r["Momentum"], reverse=True)
    return {
        "ticker": ticker.upper(),
        "sector_score": rows[0]["Momentum"],
        "leading_sector": rows[0]["Sector"],
        "lagging_sector": rows[-1]["Sector"],
        "rotation_read": f"Leadership favors {rows[0]['Sector']}",
        "sectors": rows,
    }
