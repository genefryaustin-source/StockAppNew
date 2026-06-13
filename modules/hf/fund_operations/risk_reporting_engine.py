from __future__ import annotations
from typing import Any


def build_risk_report(positions: list[dict[str, Any]], nav: float) -> dict[str, Any]:
    nav = max(float(nav or 1), 1)
    weights = [float(p.get('market_value') or 0) / nav for p in positions or []]
    max_weight = max(weights, default=0)
    gross = sum(abs(w) for w in weights)
    concentration = 'High' if max_weight > 0.15 else 'Moderate' if max_weight > 0.08 else 'Low'
    return {
        'gross_exposure': round(gross, 4),
        'net_exposure': round(sum(weights), 4),
        'largest_position_weight': round(max_weight, 4),
        'concentration_risk': concentration,
        'liquidity_risk': 'Moderate',
        'var_95_estimate': round(nav * 0.025, 2),
        'stress_loss_10pct': round(nav * gross * -0.10, 2),
    }
