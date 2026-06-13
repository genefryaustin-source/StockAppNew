"""Trade routing layer. It queues/simulates trades; it does not place live orders unless explicitly extended."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
import uuid


def route_trade(candidate: dict[str, Any], paper: bool = True, approved: bool = False) -> dict[str, Any]:
    route = "paper_queue" if paper else "live_approval_queue"
    if not paper and not approved:
        status = "approval_required"
    elif candidate.get("guardrail_status") == "blocked":
        status = "blocked"
    else:
        status = "queued"
    return {
        "route_id": str(uuid.uuid4()),
        "ticker": candidate.get("ticker"),
        "strategy": candidate.get("strategy"),
        "route": route,
        "status": status,
        "paper": paper,
        "approved": approved,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "candidate": candidate,
    }


def route_trade_queue(candidates: list[dict[str, Any]], paper: bool = True) -> list[dict[str, Any]]:
    return [route_trade(c, paper=paper) for c in candidates or []]
