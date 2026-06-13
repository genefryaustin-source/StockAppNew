from __future__ import annotations
from typing import Any


def process_subscription_redemption(investor: str, amount: float, flow_type: str) -> dict[str, Any]:
    flow_type = flow_type.lower().strip()
    return {'investor': investor, 'amount': round(float(amount or 0), 2), 'flow_type': flow_type, 'approved': flow_type in {'subscription', 'redemption'}}
