from __future__ import annotations
from typing import Any


def score_fund_health(performance: dict[str, Any], risk: dict[str, Any], compliance: dict[str, Any]) -> dict[str, Any]:
    score = 70.0
    score += min(15, float(performance.get('ytd_return') or 0) * 100)
    score += min(10, max(0, float(performance.get('sharpe') or 0) * 5))
    score -= min(20, abs(float(performance.get('max_drawdown') or 0)) * 100)
    if compliance.get('status') != 'Compliant':
        score -= 15
    score = max(0, min(100, score))
    return {'fund_health_score': round(score, 1), 'status': 'Healthy' if score >= 75 else 'Watch' if score >= 55 else 'At Risk'}
