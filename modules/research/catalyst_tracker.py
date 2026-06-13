from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Any
from .research_utils import _stable_score

CATALYSTS = ["Earnings", "Investor Day", "Product Launch", "Regulatory Event", "Economic Release", "Corporate Action"]


def build_catalyst_tracker(ticker: str) -> dict[str, Any]:
    base = datetime.now(timezone.utc)
    rows = []
    for i, name in enumerate(CATALYSTS):
        impact = _stable_score(ticker + name, 90+i, 50, 30)
        rows.append({"Catalyst": name, "Date": (base + timedelta(days=7+i*12)).date().isoformat(), "Impact Score": impact,
                     "Read": "High Impact" if impact >= 65 else "Moderate" if impact >= 40 else "Low"})
    rows = sorted(rows, key=lambda r: r["Impact Score"], reverse=True)
    return {"ticker": ticker.upper(), "catalyst_score": rows[0]["Impact Score"], "top_catalyst": rows[0], "catalysts": rows}
