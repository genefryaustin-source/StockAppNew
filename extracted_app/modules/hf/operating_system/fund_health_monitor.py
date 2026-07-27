from __future__ import annotations
from typing import Any


def monitor_fund_health(kpis: dict[str, Any]) -> dict[str, Any]:
    score = float(kpis.get('fund_health_score') or 70)
    alerts = []
    if float(kpis.get('gross_exposure') or 0) > 1.25: alerts.append('Gross exposure above policy threshold')
    if abs(float(kpis.get('max_drawdown') or 0)) > 0.10: alerts.append('Drawdown requires review')
    if float(kpis.get('risk_utilization') or 0) > 0.85: alerts.append('Risk utilization elevated')
    return {'score': round(score, 1), 'status': 'Healthy' if score >= 75 else 'Watch' if score >= 55 else 'At Risk', 'alerts': alerts}
