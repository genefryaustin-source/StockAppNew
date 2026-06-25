from __future__ import annotations
from typing import Any, Dict, Optional
import random
try:
    from modules.forex._forex_runtime_common import iso
    from modules.forex.forex_snapshot_engine import ForexSnapshotEngine
    from modules.forex.forex_alert_engine import ForexAlertEngine
except Exception:
    from _forex_runtime_common import iso
    from forex_snapshot_engine import ForexSnapshotEngine
    from forex_alert_engine import ForexAlertEngine
class ForexSystemMonitor:
    def __init__(self, snapshot_engine: Optional[ForexSnapshotEngine] = None, alert_engine: Optional[ForexAlertEngine] = None): self.snapshot_engine = snapshot_engine or ForexSnapshotEngine(); self.alert_engine = alert_engine or ForexAlertEngine()
    def collect_state(self) -> Dict[str, Any]:
        return {'runtime_status':'healthy','active_jobs':random.randint(0,10),'queued_jobs':random.randint(0,40),'failed_jobs':random.choice([0,0,0,1]),'throughput_per_minute':round(random.uniform(5,45),2),'provider_health':{'polygon':random.randint(75,100),'marketdata':random.randint(70,100),'finnhub':random.randint(65,100),'yahoo':random.randint(60,95)},'risk_flags':[]}
    def tick(self, state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        runtime_state = state or self.collect_state(); snapshot = self.snapshot_engine.capture_runtime_snapshot(runtime_state); alerts = self.alert_engine.evaluate(runtime_state)
        return {'status':'ok','snapshot':snapshot,'alerts':alerts,'checked_at':iso()}
