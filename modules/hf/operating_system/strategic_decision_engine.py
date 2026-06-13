from __future__ import annotations
from typing import Any


def build_strategic_decisions(kpis: dict[str, Any]) -> list[dict[str, Any]]:
    decisions = []
    if float(kpis.get('capital_deployment') or 0) < 0.70:
        decisions.append({'decision': 'Increase Deployment Review', 'priority': 'Medium', 'rationale': 'Capital deployment is below target.'})
    if float(kpis.get('risk_utilization') or 0) > 0.80:
        decisions.append({'decision': 'Risk Reduction Review', 'priority': 'High', 'rationale': 'Risk utilization is elevated.'})
    decisions.append({'decision': 'Continue Research Pipeline Buildout', 'priority': 'Medium', 'rationale': 'Maintain idea generation and committee throughput.'})
    return decisions
