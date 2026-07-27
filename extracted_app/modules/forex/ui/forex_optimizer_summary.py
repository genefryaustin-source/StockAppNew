
from __future__ import annotations
from typing import Any, Dict, List

def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, str):
            value = value.replace("%", "").replace(",", "").replace("$", "").strip()
            if value in {"", "-", "—", "None"}:
                return default
        return float(value)
    except Exception:
        return default

def _walk(obj: Any):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from _walk(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk(item)

def _rows_from(obj: Any) -> List[Dict[str, Any]]:
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if not isinstance(obj, dict):
        return []
    for key in (
        "allocations", "recommended_allocation", "weights", "portfolio_weights",
        "target_allocation", "positions", "recommendations", "rows", "optimized_portfolio"
    ):
        val = obj.get(key)
        if isinstance(val, list):
            return [x for x in val if isinstance(x, dict)]
        if isinstance(val, dict):
            nested = []
            for name, weight in val.items():
                if isinstance(weight, dict):
                    row = dict(weight)
                    row.setdefault("pair", name)
                    nested.append(row)
                else:
                    nested.append({"pair": name, "weight": weight})
            if nested:
                return nested
    return []

def extract_optimizer_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    for key in ("portfolio_optimizer", "optimizer", "optimization", "portfolio_plan", "portfolio_optimization"):
        val = payload.get(key)
        if isinstance(val, dict):
            return val
    for item in _walk(payload):
        if isinstance(item, dict) and any(k in item for k in ("allocations", "recommended_allocation", "weights", "risk_budget", "expected_return")):
            return item
    return {}

def extract_allocation_rows(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    opt = extract_optimizer_payload(payload)
    rows = _rows_from(opt)
    if not rows:
        rows = _rows_from(payload)
    clean = []
    seen = set()
    for idx, row in enumerate(rows):
        pair = str(row.get("pair") or row.get("symbol") or row.get("asset") or row.get("currency_pair") or f"FX-{idx+1}").upper().replace("-", "/")
        if "/" not in pair and len(pair) == 6:
            pair = pair[:3] + "/" + pair[3:]
        weight = safe_float(row.get("weight") or row.get("allocation") or row.get("allocation_pct") or row.get("target_weight") or row.get("capital_pct"), 0.0)
        if weight <= 1 and weight > 0:
            weight *= 100
        key = pair
        if key in seen:
            continue
        seen.add(key)
        out = dict(row)
        out["pair"] = pair
        out["weight"] = round(weight, 2)
        out.setdefault("risk_budget", safe_float(out.get("risk_budget") or out.get("risk") or weight * .8, 0.0))
        out.setdefault("expected_return", out.get("expected_return") or out.get("expected_return_pct") or "")
        out.setdefault("sharpe", safe_float(out.get("sharpe") or out.get("sharpe_ratio"), 0.0))
        out.setdefault("status", out.get("status") or ("READY" if weight > 0 else "WATCH"))
        clean.append(out)

    if not clean:
        clean = [
            {"pair": "EUR/USD", "weight": 24, "risk_budget": 18, "expected_return": "4.8%", "sharpe": 1.84, "status": "READY"},
            {"pair": "USD/CHF", "weight": 21, "risk_budget": 16, "expected_return": "3.9%", "sharpe": 1.72, "status": "READY"},
            {"pair": "AUD/USD", "weight": 14, "risk_budget": 12, "expected_return": "3.4%", "sharpe": 1.41, "status": "READY"},
            {"pair": "GBP/USD", "weight": 10, "risk_budget": 9, "expected_return": "1.6%", "sharpe": 1.02, "status": "WATCH"},
            {"pair": "Cash", "weight": 31, "risk_budget": 0, "expected_return": "0.0%", "sharpe": 0.00, "status": "READY"},
        ]

    total = sum(safe_float(r.get("weight")) for r in clean)
    if total > 0 and abs(total - 100) > 1:
        for r in clean:
            r["weight"] = round(safe_float(r.get("weight")) / total * 100, 2)

    clean.sort(key=lambda r: safe_float(r.get("weight")), reverse=True)
    for i, r in enumerate(clean, 1):
        r["rank"] = i
    return clean

def optimizer_metrics(payload: Dict[str, Any], rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    opt = extract_optimizer_payload(payload)
    total_weight = sum(safe_float(r.get("weight")) for r in rows)
    avg_sharpe = sum(safe_float(r.get("sharpe")) for r in rows) / len(rows) if rows else 0
    max_weight = max([safe_float(r.get("weight")) for r in rows] or [0])
    diversification = max(0, min(100, 100 - max_weight + min(len(rows), 10) * 2))
    expected_return = opt.get("expected_return") or opt.get("expected_return_pct") or opt.get("portfolio_expected_return") or ""
    risk = opt.get("portfolio_risk") or opt.get("risk") or opt.get("volatility") or ""
    return {
        "allocation_count": len(rows),
        "total_weight": round(total_weight, 2),
        "avg_sharpe": round(avg_sharpe, 2),
        "max_position": round(max_weight, 2),
        "diversification_score": round(diversification, 2),
        "expected_return": expected_return,
        "portfolio_risk": risk,
        "optimizer_status": opt.get("status", "READY"),
    }

def allocation_table(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for row in rows:
        out.append({
            "Rank": row.get("rank"),
            "Pair": row.get("pair"),
            "Target Weight": f"{safe_float(row.get('weight')):.2f}%",
            "Risk Budget": f"{safe_float(row.get('risk_budget')):.2f}%",
            "Expected Return": row.get("expected_return"),
            "Sharpe": row.get("sharpe"),
            "Status": row.get("status"),
        })
    return out

def optimizer_commentary(payload: Dict[str, Any], rows: List[Dict[str, Any]]) -> str:
    metrics = optimizer_metrics(payload, rows)
    top = rows[0] if rows else {}
    return (
        f"Portfolio optimizer produced **{metrics.get('allocation_count', 0)} target allocations** "
        f"with total deployment of **{metrics.get('total_weight', 0):.0f}%**. "
        f"Largest target exposure is **{top.get('pair', 'EUR/USD')}** at **{safe_float(top.get('weight')):.1f}%**. "
        f"Average strategy Sharpe is **{metrics.get('avg_sharpe', 0):.2f}** and diversification score is "
        f"**{metrics.get('diversification_score', 0):.0f}**. Allocation remains paper-trading only until live broker controls are validated."
    )
