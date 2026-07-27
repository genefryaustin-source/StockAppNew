"""Portfolio optimization suggestions for options portfolios."""
from __future__ import annotations
from typing import Any


def generate_portfolio_optimization_suggestions(summary: dict[str, Any], risk: dict[str, Any], exposure: dict[str, Any]) -> list[dict[str, Any]]:
    suggestions = []
    if abs(float(exposure.get("net_delta") or 0)) > 500:
        suggestions.append({"priority": "High", "action": "Add directional hedge", "detail": "Net delta is elevated. Consider SPY put spread or reducing directional single-leg exposure."})
    if abs(float(exposure.get("net_vega") or 0)) > 1000:
        suggestions.append({"priority": "Medium", "action": "Reduce vega concentration", "detail": "Portfolio is highly volatility-sensitive. Consider closing long premium after IV expansion or hedging with short vega spreads."})
    if float(exposure.get("net_theta") or 0) < -500:
        suggestions.append({"priority": "Medium", "action": "Improve theta profile", "detail": "Negative theta is material. Consider calendars, diagonals, or reducing long premium exposure."})
    if risk.get("label") in {"High", "Critical"}:
        suggestions.append({"priority": "High", "action": "Reduce portfolio heat", "detail": "Risk score is elevated. Reduce largest risk position or lower gross contracts."})
    if not suggestions:
        suggestions.append({"priority": "Info", "action": "Maintain balanced exposure", "detail": "No major optimization need detected from available data."})
    return suggestions
