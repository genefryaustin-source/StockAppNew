from __future__ import annotations
from typing import Any


def explain_hedge_fund_os(packet: dict[str, Any]) -> str:
    k = packet.get('kpis', {}); h = packet.get('health', {})
    return f"""### Hedge Fund OS Copilot

- Fund health: **{h.get('status')}** ({h.get('score')}/100).
- AUM: **${k.get('fund_aum', 0):,.0f}**.
- YTD return: **{k.get('ytd_return', 0):.2%}**.
- Gross exposure: **{k.get('gross_exposure', 0):.1%}**.
- Risk utilization: **{k.get('risk_utilization', 0):.1%}**.

Executive focus: review risk alerts, monitor committee throughput, and validate capital deployment against PM conviction.
"""
