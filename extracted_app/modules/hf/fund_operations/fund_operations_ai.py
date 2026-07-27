from __future__ import annotations
from typing import Any


def explain_fund_operations(packet: dict[str, Any]) -> str:
    health = packet.get('health', {})
    performance = packet.get('performance', {})
    risk = packet.get('risk', {})
    compliance = packet.get('compliance', {})
    return f"""### Fund Operations Copilot

- Fund health: **{health.get('status')}** ({health.get('fund_health_score')}/100).
- YTD return: **{performance.get('ytd_return', 0):.2%}** with Sharpe **{performance.get('sharpe', 0)}**.
- Gross exposure: **{risk.get('gross_exposure', 0):.1%}**.
- Compliance status: **{compliance.get('status')}**.

Recommended next steps: review exposure concentration, verify NAV inputs, and generate investor/LP reports after PM approval.
"""
