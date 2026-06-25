from __future__ import annotations
from typing import Any, Dict, Optional
try:
    from modules.forex._forex_runtime_common import iso, safe_float
    from modules.forex.forex_persistence_engine import ForexPersistenceEngine
except Exception:
    from _forex_runtime_common import iso, safe_float
    from forex_persistence_engine import ForexPersistenceEngine

class ForexSnapshotEngine:
    def __init__(self, persistence: Optional[ForexPersistenceEngine] = None): self.persistence = persistence or ForexPersistenceEngine()
    def capture_runtime_snapshot(self, runtime_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        s = runtime_state or {}
        snap = {'captured_at': iso(), 'runtime_status': s.get('runtime_status','unknown'), 'active_jobs': int(s.get('active_jobs',0)), 'queued_jobs': int(s.get('queued_jobs',0)), 'failed_jobs': int(s.get('failed_jobs',0)), 'throughput_per_minute': safe_float(s.get('throughput_per_minute')), 'provider_health': s.get('provider_health',{}), 'risk_flags': s.get('risk_flags', [])}
        snap['snapshot_id'] = self.persistence.save_snapshot('runtime', snap); return snap
    def capture_strategy_snapshot(self, strategy_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        s = strategy_state or {}; strategies = s.get('strategies', [])
        snap = {'captured_at': iso(), 'strategy_count': len(strategies), 'enabled_strategy_count': len([x for x in strategies if x.get('enabled', True)]), 'top_pairs': s.get('top_pairs', ['EURUSD','GBPUSD','USDJPY','AUDUSD']), 'signals': s.get('signals', []), 'portfolio_exposure': s.get('portfolio_exposure', {})}
        snap['snapshot_id'] = self.persistence.save_snapshot('strategy', snap); return snap
    def latest_dashboard_payload(self) -> Dict[str, Any]:
        r = self.persistence.list_snapshots('runtime', 1); s = self.persistence.list_snapshots('strategy', 1)
        return {'runtime': r[0]['payload'] if r else {}, 'strategy': s[0]['payload'] if s else {}, 'events': self.persistence.list_events(limit=25), 'generated_at': iso()}
