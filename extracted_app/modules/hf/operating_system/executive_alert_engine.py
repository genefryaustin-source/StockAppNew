from __future__ import annotations
from typing import Any


def build_executive_alerts(kpis: dict[str, Any], health: dict[str, Any]) -> list[dict[str, Any]]:
    alerts = []
    for item in health.get('alerts', []):
        alerts.append({'severity': 'HIGH', 'category': 'Fund Health', 'message': item})
    if float(kpis.get('ytd_return') or 0) < -0.05:
        alerts.append({'severity': 'MEDIUM', 'category': 'Performance', 'message': 'YTD performance below -5%.'})
    if not alerts:
        alerts.append({'severity': 'INFO', 'category': 'System', 'message': 'No executive exceptions currently detected.'})
    return alerts
