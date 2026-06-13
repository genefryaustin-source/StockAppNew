from __future__ import annotations
from typing import Any


def build_ai_committee_view(packet: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {'role':'CIO','view':'Maintain disciplined capital deployment and monitor risk utilization.'},
        {'role':'PM','view':'Prioritize highest conviction names and trim drift.'},
        {'role':'Risk Officer','view':'Review concentration and drawdown alerts.'},
        {'role':'COO','view':'Ensure NAV, reporting, compliance, and audit packages are current.'},
    ]
