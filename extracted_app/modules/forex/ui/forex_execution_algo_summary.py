
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
        "algorithms", "execution_algorithms", "algo_orders", "orders",
        "twap_orders", "vwap_orders", "iceberg_orders", "smart_routes",
        "routes", "executions", "rows", "recommendations"
    ):
        val = obj.get(key)
        if isinstance(val, list):
            return [x for x in val if isinstance(x, dict)]
        if isinstance(val, dict):
            nested = _rows_from(val)
            if nested:
                return nested
    return []

def extract_execution_algo_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    for key in (
        "execution_algorithms", "execution_algo", "smart_order_router",
        "twap", "vwap", "iceberg", "execution", "execution_center"
    ):
        val = payload.get(key)
        if isinstance(val, dict):
            return val
    for item in _walk(payload):
        if isinstance(item, dict) and any(k in item for k in ("algorithms", "routes", "twap_orders", "vwap_orders", "slippage", "fill_rate")):
            return item
    return {}

def extract_execution_rows(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    algo = extract_execution_algo_payload(payload)
    rows = []
    for source in [algo, payload]:
        rows.extend(_rows_from(source))

    clean = []
    seen = set()
    for idx, row in enumerate(rows):
        pair = str(row.get("pair") or row.get("symbol") or row.get("currency_pair") or f"FX-{idx+1}").upper().replace("-", "/")
        if "/" not in pair and len(pair) == 6:
            pair = pair[:3] + "/" + pair[3:]
        algo_name = str(row.get("algorithm") or row.get("algo") or row.get("route_type") or row.get("type") or "SMART").upper()
        status = str(row.get("status") or row.get("state") or "READY").upper()
        key = (pair, algo_name, idx)
        if key in seen:
            continue
        seen.add(key)
        out = dict(row)
        out["pair"] = pair
        out["algorithm"] = algo_name
        out["status"] = status
        out.setdefault("target_units", safe_float(out.get("target_units") or out.get("units") or out.get("qty") or out.get("quantity"), 100000))
        out.setdefault("filled_units", safe_float(out.get("filled_units") or out.get("filled_qty") or out.get("filled") or 0))
        out.setdefault("fill_rate", safe_float(out.get("fill_rate") or out.get("completion_pct") or 0))
        if safe_float(out.get("fill_rate")) <= 1 and safe_float(out.get("fill_rate")) > 0:
            out["fill_rate"] = round(safe_float(out.get("fill_rate")) * 100, 2)
        if safe_float(out.get("fill_rate")) <= 0 and safe_float(out.get("target_units")) > 0:
            out["fill_rate"] = round(safe_float(out.get("filled_units")) / safe_float(out.get("target_units")) * 100, 2)
        out.setdefault("slippage_bps", safe_float(out.get("slippage_bps") or out.get("slippage") or 0))
        out.setdefault("latency_ms", safe_float(out.get("latency_ms") or out.get("latency") or 80))
        out.setdefault("venue", out.get("venue") or out.get("provider") or "PAPER")
        clean.append(out)

    if not clean:
        clean = [
            {"pair": "EUR/USD", "algorithm": "TWAP", "status": "READY", "target_units": 180000, "filled_units": 0, "fill_rate": 0, "slippage_bps": 0.4, "latency_ms": 82, "venue": "PAPER"},
            {"pair": "USD/CHF", "algorithm": "VWAP", "status": "READY", "target_units": 160000, "filled_units": 0, "fill_rate": 0, "slippage_bps": 0.5, "latency_ms": 91, "venue": "PAPER"},
            {"pair": "AUD/USD", "algorithm": "ICEBERG", "status": "WATCH", "target_units": 120000, "filled_units": 0, "fill_rate": 0, "slippage_bps": 0.7, "latency_ms": 104, "venue": "PAPER"},
            {"pair": "GBP/USD", "algorithm": "SMART", "status": "READY", "target_units": 90000, "filled_units": 0, "fill_rate": 0, "slippage_bps": 0.6, "latency_ms": 96, "venue": "PAPER"},
        ]

    return clean

def execution_metrics(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(rows or [])
    active = len([r for r in rows if str(r.get("status")).upper() in {"ACTIVE", "RUNNING", "WORKING"}])
    ready = len([r for r in rows if str(r.get("status")).upper() in {"READY", "QUEUED", "WATCH"}])
    completed = len([r for r in rows if str(r.get("status")).upper() in {"FILLED", "COMPLETE", "COMPLETED"}])
    avg_slippage = sum(safe_float(r.get("slippage_bps")) for r in rows) / total if total else 0
    avg_latency = sum(safe_float(r.get("latency_ms")) for r in rows) / total if total else 0
    avg_fill = sum(safe_float(r.get("fill_rate")) for r in rows) / total if total else 0
    target_units = sum(safe_float(r.get("target_units")) for r in rows)
    filled_units = sum(safe_float(r.get("filled_units")) for r in rows)
    return {
        "total_algos": total,
        "active": active,
        "ready": ready,
        "completed": completed,
        "avg_slippage_bps": round(avg_slippage, 3),
        "avg_latency_ms": round(avg_latency, 1),
        "avg_fill_rate": round(avg_fill, 2),
        "target_units": round(target_units, 2),
        "filled_units": round(filled_units, 2),
        "execution_mode": "PAPER",
    }

def execution_table(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for row in rows:
        out.append({
            "Pair": row.get("pair"),
            "Algorithm": row.get("algorithm"),
            "Status": row.get("status"),
            "Target Units": row.get("target_units"),
            "Filled Units": row.get("filled_units"),
            "Fill Rate": f"{safe_float(row.get('fill_rate')):.1f}%",
            "Slippage": f"{safe_float(row.get('slippage_bps')):.2f} bps",
            "Latency": f"{safe_float(row.get('latency_ms')):.0f} ms",
            "Venue": row.get("venue"),
        })
    return out

def execution_commentary(rows: List[Dict[str, Any]]) -> str:
    metrics = execution_metrics(rows)
    return (
        f"Execution algorithm workstation is monitoring **{metrics.get('total_algos', 0)} algorithmic routes** "
        f"in **{metrics.get('execution_mode')} mode**. Average latency is **{metrics.get('avg_latency_ms', 0):.0f} ms** "
        f"and expected slippage is **{metrics.get('avg_slippage_bps', 0):.2f} bps**. "
        "TWAP, VWAP, Iceberg, and Smart Order Router controls are available for paper-trading validation before live routing."
    )
