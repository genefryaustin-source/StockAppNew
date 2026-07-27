from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Iterable
import json, math

def utc_now() -> str: return datetime.now(timezone.utc).isoformat()
def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or (isinstance(value, float) and math.isnan(value)): return default
        return float(value)
    except Exception: return default
def clamp(value: Any, low: float = 0.0, high: float = 100.0) -> float: return max(low, min(high, safe_float(value)))
def rating_to_score(rating: str) -> float:
    return {'strong buy':100,'buy':80,'hold':55,'reduce':35,'sell':20,'strong sell':0,'approve':80,'approve small':65,'watchlist':55,'reject':25}.get(str(rating or 'hold').lower(),55)
def score_to_rating(score: Any) -> str:
    s=clamp(score)
    return 'Strong Buy' if s>=87 else 'Buy' if s>=68 else 'Hold' if s>=45 else 'Reduce' if s>=28 else 'Sell' if s>=10 else 'Strong Sell'
def normalize_weights(items: dict[str,float]) -> dict[str,float]:
    total=sum(max(0.0,safe_float(v)) for v in items.values())
    return {k:(max(0.0,safe_float(v))/total if total else 1/max(1,len(items))) for k,v in items.items()}
def to_json(data: Any) -> str: return json.dumps(data, default=str, indent=2)
def from_json(text: str|None, default: Any=None) -> Any:
    try: return json.loads(text) if text else default
    except Exception: return default
def rows_to_dicts(rows: Iterable[Any]) -> list[dict[str,Any]]:
    out=[]
    for r in rows or []:
        out.append(dict(r._mapping) if hasattr(r,'_mapping') else dict(r) if isinstance(r,dict) else {'value':r})
    return out
