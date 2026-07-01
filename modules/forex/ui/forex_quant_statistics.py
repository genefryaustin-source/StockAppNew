
from __future__ import annotations
import math
from typing import Any, Dict, Iterable, List

def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, str):
            value = value.replace("%", "").replace(",", "").replace("$", "").strip()
            if value in {"", "-", "—", "None"}:
                return default
        result = float(value)
        return default if math.isnan(result) or math.isinf(result) else result
    except Exception:
        return default

def numeric_series(rows: Iterable[Dict[str, Any]], keys: Iterable[str]) -> List[float]:
    vals = []
    for row in rows or []:
        if isinstance(row, dict):
            for key in keys:
                if row.get(key) is not None:
                    vals.append(safe_float(row.get(key)))
                    break
    return vals

def mean(v): return sum(v) / len(v) if v else 0.0
def median(v):
    if not v: return 0.0
    s=sorted(v); n=len(s); m=n//2
    return s[m] if n%2 else (s[m-1]+s[m])/2
def stdev(v):
    if len(v)<2: return 0.0
    m=mean(v); return math.sqrt(sum((x-m)**2 for x in v)/(len(v)-1))
def win_rate(v): return len([x for x in v if x>0])/len(v)*100 if v else 0.0
def sharpe(v):
    sd=stdev(v); return mean(v)/sd if sd>0 else 0.0
def sortino(v):
    downside=[x for x in v if x<0]
    if not downside: return sharpe(v)
    dd=math.sqrt(sum(x*x for x in downside)/len(downside))
    return mean(v)/dd if dd>0 else 0.0

def summarize_quant_rows(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    alpha = numeric_series(rows, ["alpha_score", "alpha", "composite_score", "score"])
    confidence = numeric_series(rows, ["confidence", "confidence_score", "signal_confidence"])
    returns = numeric_series(rows, ["expected_return", "expected_return_pct", "return", "pnl", "alpha_return"])
    base = returns or alpha
    return {
        "row_count": len(rows or []),
        "mean_alpha": round(mean(alpha), 2),
        "median_alpha": round(median(alpha), 2),
        "alpha_stdev": round(stdev(alpha), 2),
        "confidence_mean": round(mean(confidence), 2),
        "confidence_median": round(median(confidence), 2),
        "win_rate": round(win_rate(base), 2),
        "sharpe": round(sharpe(base), 4),
        "sortino": round(sortino(base), 4),
    }
