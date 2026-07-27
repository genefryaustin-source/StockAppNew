from __future__ import annotations
from typing import Any


def build_hedge_fund_os_packet(db: Any = None, user: dict | None = None) -> dict[str, Any]:
    try:
        from modules.hf.fund_operations.fund_operations_dashboard import build_fund_operations_packet
        hf5 = build_fund_operations_packet(db=db, user=user)
    except Exception:
        hf5 = {}
    from modules.hf.operating_system.executive_kpi_engine import build_executive_kpis
    from modules.hf.operating_system.fund_health_monitor import monitor_fund_health
    from modules.hf.operating_system.executive_alert_engine import build_executive_alerts
    from modules.hf.operating_system.strategic_decision_engine import build_strategic_decisions
    from modules.hf.operating_system.organizational_intelligence_engine import build_org_intelligence
    kpis = build_executive_kpis(hf5)
    health = monitor_fund_health(kpis)
    alerts = build_executive_alerts(kpis, health)
    decisions = build_strategic_decisions(kpis)
    org = build_org_intelligence()
    return {'hf5': hf5, 'kpis': kpis, 'health': health, 'alerts': alerts, 'strategic_decisions': decisions, 'organization': org}
