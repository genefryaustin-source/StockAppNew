"""
modules/forex/forex_data_quality_monitor.py

Phase 16A — Forex market-data quality monitor.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class ForexDataQualityMonitor:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def score_quote(self, quote: Dict[str, Any]) -> Dict[str, Any]:
        providers = quote.get("providers") or []
        provider_count = quote.get("provider_count") or len(providers)
        spread = float(quote.get("spread") or 0)
        latency = sum(float(p.get("latency_ms") or 0) for p in providers) / max(len(providers), 1)
        score = 100.0
        if provider_count < 2:
            score -= 25
        if spread <= 0:
            score -= 25
        if latency > 500:
            score -= 20
        elif latency > 250:
            score -= 10
        return {
            "quality_score": round(max(0, score), 2),
            "provider_count": provider_count,
            "avg_latency_ms": round(latency, 2),
            "spread": spread,
            "status": "GOOD" if score >= 80 else "DEGRADED" if score >= 60 else "POOR",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def dashboard(self, quotes: List[Dict[str, Any]]) -> Dict[str, Any]:
        rows = [self.score_quote(q) | {"pair": q.get("pair")} for q in quotes]
        avg = sum(r["quality_score"] for r in rows) / max(len(rows), 1)
        return {
            "status": "READY",
            "average_quality": round(avg, 2),
            "rows": rows,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


_MON = None


def get_forex_data_quality_monitor(db: Optional[Any] = None) -> ForexDataQualityMonitor:
    global _MON
    if _MON is None or (db is not None and _MON.db is None):
        _MON = ForexDataQualityMonitor(db=db)
    return _MON
