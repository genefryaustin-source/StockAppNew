from __future__ import annotations
from typing import Any, Dict, List, Optional
try:
    from modules.forex._forex_runtime_common import safe_float
    from modules.forex.forex_persistence_engine import ForexPersistenceEngine
except Exception:
    from _forex_runtime_common import safe_float
    from forex_persistence_engine import ForexPersistenceEngine
class ForexHistoryEngine:
    def __init__(self, persistence: Optional[ForexPersistenceEngine] = None): self.persistence = persistence or ForexPersistenceEngine()
    def runtime_history(self, limit: int = 250) -> List[Dict[str, Any]]: return self.persistence.list_snapshots('runtime', limit)
    def event_history(self, limit: int = 250) -> List[Dict[str, Any]]: return self.persistence.list_events(limit=limit)
    def summarize_runtime_trend(self, limit: int = 100) -> Dict[str, Any]:
        rows = self.runtime_history(limit); payloads = [r.get('payload', {}) for r in rows]
        if not payloads: return {'status':'empty','message':'No runtime history available.'}
        n = len(payloads); latest = payloads[0]
        return {'status':'ok','samples':n,'latest_status':latest.get('runtime_status','unknown'),'average_queued_jobs':round(sum(safe_float(p.get('queued_jobs')) for p in payloads)/n,2),'average_failed_jobs':round(sum(safe_float(p.get('failed_jobs')) for p in payloads)/n,2),'average_throughput_per_minute':round(sum(safe_float(p.get('throughput_per_minute')) for p in payloads)/n,2),'latest_captured_at':latest.get('captured_at')}
