"""Autonomous optimizer for ranking execution candidates."""
from __future__ import annotations
from typing import Any


def optimize_trade_queue(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for c in candidates or []:
        score = float(c.get("confidence") or c.get("score") or 50)
        ev = float(c.get("expected_value") or 0)
        risk = float(c.get("max_loss") or c.get("risk") or 1)
        risk_adj = score + min(20, ev / max(1, risk) * 25) - min(15, risk / 10000)
        row = dict(c)
        row["optimizer_score"] = round(max(0, min(100, risk_adj)), 1)
        rows.append(row)
    return sorted(rows, key=lambda x: x.get("optimizer_score", 0), reverse=True)
