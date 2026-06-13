from __future__ import annotations
from typing import Any
from .research_utils import _clamp


def build_research_scorecard(components: dict[str, Any]) -> dict[str, Any]:
    fundamental = components.get("fundamental", {}).get("fundamental_score", 50)
    analyst = components.get("analyst", {}).get("analyst_score", 50)
    revisions = components.get("revisions", {}).get("revision_score", 50)
    earnings = components.get("earnings", {}).get("earnings_score", 50)
    ownership = components.get("ownership", {}).get("institutional_score", 50)
    macro = components.get("macro", {}).get("macro_score", 50)
    sector = components.get("sector", {}).get("sector_score", 50)
    catalysts = components.get("catalysts", {}).get("catalyst_score", 50)
    composite = round(_clamp(fundamental*.18 + analyst*.12 + revisions*.13 + earnings*.12 + ownership*.15 + macro*.10 + sector*.10 + catalysts*.10), 1)
    label = "High Conviction" if composite >= 72 else "Constructive" if composite >= 58 else "Neutral" if composite >= 42 else "Avoid / Watch"
    return {"composite_research_score": composite, "research_label": label,
            "fundamental_score": fundamental, "analyst_score": analyst, "revision_score": revisions, "earnings_score": earnings,
            "institutional_score": ownership, "macro_score": macro, "sector_score": sector, "catalyst_score": catalysts}
