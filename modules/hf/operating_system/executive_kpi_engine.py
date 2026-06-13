from __future__ import annotations
from typing import Any


def build_executive_kpis(hf5_packet: dict[str, Any] | None = None) -> dict[str, Any]:
    hf5_packet = hf5_packet or {}
    nav = hf5_packet.get('nav', {})
    perf = hf5_packet.get('performance', {})
    risk = hf5_packet.get('risk', {})
    health = hf5_packet.get('health', {})
    return {
        'fund_aum': nav.get('net_assets', 1_000_000),
        'fund_nav_per_share': nav.get('nav_per_share', 1.0),
        'ytd_return': perf.get('ytd_return', 0.0),
        'sharpe': perf.get('sharpe', 0.0),
        'max_drawdown': perf.get('max_drawdown', 0.0),
        'gross_exposure': risk.get('gross_exposure', 0.0),
        'largest_position': risk.get('largest_position_weight', 0.0),
        'fund_health_score': health.get('fund_health_score', 70),
        'fund_health_status': health.get('status', 'Watch'),
        'research_pipeline': 12,
        'committee_activity': 5,
        'risk_utilization': 0.62,
        'capital_deployment': 0.78,
    }
