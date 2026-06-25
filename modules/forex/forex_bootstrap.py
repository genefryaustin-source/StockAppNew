from __future__ import annotations
from typing import Any, Dict
try:
    from modules.forex._forex_runtime_common import DEFAULT_DB_PATH, iso
    from modules.forex.forex_persistence_engine import ForexPersistenceEngine
    from modules.forex.forex_snapshot_engine import ForexSnapshotEngine
except Exception:
    from _forex_runtime_common import DEFAULT_DB_PATH, iso
    from forex_persistence_engine import ForexPersistenceEngine
    from forex_snapshot_engine import ForexSnapshotEngine
class ForexBootstrap:
    def __init__(self, db_path: str = DEFAULT_DB_PATH): self.persistence = ForexPersistenceEngine(db_path)
    def initialize(self, seed_snapshots: bool = True) -> Dict[str, Any]:
        self.persistence.set_value('runtime_enabled', True); self.persistence.set_value('bootstrap_completed_at', iso()); self.persistence.log_event('bootstrap','Forex runtime bootstrap completed.','info',{})
        snapshots = []
        if seed_snapshots:
            se = ForexSnapshotEngine(self.persistence)
            snapshots.append(se.capture_runtime_snapshot({'runtime_status':'initialized','active_jobs':0,'queued_jobs':0,'failed_jobs':0,'throughput_per_minute':0,'provider_health':{},'risk_flags':[]}))
            snapshots.append(se.capture_strategy_snapshot({'strategies':[],'signals':[],'portfolio_exposure':{}}))
        return {'status':'ok','db_path':self.persistence.db_path,'snapshots':snapshots,'initialized_at':iso()}
def bootstrap_forex_runtime(db_path: str = DEFAULT_DB_PATH) -> Dict[str, Any]: return ForexBootstrap(db_path).initialize()
