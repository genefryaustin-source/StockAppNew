from __future__ import annotations
from typing import Any


def summarize_capital_flows(subscriptions: float = 0.0, redemptions: float = 0.0) -> dict[str, Any]:
    net = float(subscriptions or 0) - float(redemptions or 0)
    return {'subscriptions': round(subscriptions, 2), 'redemptions': round(redemptions, 2), 'net_flow': round(net, 2), 'flow_status': 'Inflow' if net > 0 else 'Outflow' if net < 0 else 'Flat'}
