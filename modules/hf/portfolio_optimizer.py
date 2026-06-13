from __future__ import annotations
from typing import Any
import pandas as pd

def optimize_weights(candidates: list[dict[str, Any]], max_weight: float = 0.08) -> list[dict[str, Any]]:
    if not candidates:
        return []
    rows = []
    total_score = 0.0
    for c in candidates:
        score = float(c.get("alpha_score") or c.get("composite_score") or 50)
        score = max(1.0, score)
        total_score += score
        rows.append((c, score))
    out = []
    for c, score in rows:
        weight = min(max_weight, score / total_score)
        new_row = dict(c)
        new_row["optimized_weight"] = round(weight, 4)
        out.append(new_row)
    return out

def rebalance_plan(current: list[dict[str, Any]], target: list[dict[str, Any]]) -> pd.DataFrame:
    cur = {str(x.get("symbol")).upper(): float(x.get("current_weight") or x.get("weight") or 0) for x in current or []}
    rows = []
    for t in target or []:
        sym = str(t.get("symbol")).upper()
        target_w = float(t.get("target_weight") or t.get("optimized_weight") or 0)
        cur_w = cur.get(sym, 0.0)
        delta = target_w - cur_w
        rows.append({"symbol": sym, "current_weight": round(cur_w, 4), "target_weight": round(target_w, 4), "delta": round(delta, 4), "action": "Buy/Add" if delta > 0.01 else "Sell/Trim" if delta < -0.01 else "Hold"})
    return pd.DataFrame(rows)
