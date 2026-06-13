from __future__ import annotations
from typing import Any

def _num(v: Any, default: float = 0.0) -> float:
    try:
        return float(v or default)
    except Exception:
        return default

def portfolio_heat_report(positions: list[dict[str, Any]]) -> dict[str, Any]:
    total_weight = sum(_num(p.get("target_weight")) for p in positions or [])
    max_position = max((_num(p.get("target_weight")) for p in positions or []), default=0.0)
    sector_map = {}
    for p in positions or []:
        sector = str(p.get("sector") or "Unknown")
        sector_map[sector] = sector_map.get(sector, 0.0) + _num(p.get("target_weight"))
    max_sector = max(sector_map.values(), default=0.0)
    warnings = []
    if max_position > 0.10:
        warnings.append("Single-name concentration above 10%.")
    if max_sector > 0.35:
        warnings.append("Sector concentration above 35%.")
    if total_weight > 1.05:
        warnings.append("Gross exposure above 105%.")
    if total_weight < 0.50:
        warnings.append("Portfolio materially under-invested.")
    return {"gross_exposure": round(total_weight, 4), "max_position_weight": round(max_position, 4), "max_sector_weight": round(max_sector, 4), "sector_weights": {k: round(v, 4) for k, v in sector_map.items()}, "heat_level": "High" if warnings else "Normal", "warnings": warnings}
