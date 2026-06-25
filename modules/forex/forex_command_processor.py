from __future__ import annotations
from typing import Any, Dict, Optional
import traceback
try:
    from modules.forex.forex_system_monitor import ForexSystemMonitor
    from modules.forex.forex_snapshot_engine import ForexSnapshotEngine
    from modules.forex.forex_history_engine import ForexHistoryEngine
    from modules.forex.forex_persistence_engine import ForexPersistenceEngine
except Exception:
    from forex_system_monitor import ForexSystemMonitor
    from forex_snapshot_engine import ForexSnapshotEngine
    from forex_history_engine import ForexHistoryEngine
    from forex_persistence_engine import ForexPersistenceEngine
class ForexCommandProcessor:
    def __init__(self):
        self.persistence = ForexPersistenceEngine(); self.monitor = ForexSystemMonitor(); self.snapshots = ForexSnapshotEngine(self.persistence); self.history = ForexHistoryEngine(self.persistence)
    def execute(self, command: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        cmd = (command or '').strip().lower().replace('-', '_').replace(' ', '_'); payload = payload or {}
        try:
            if cmd in {'status','runtime_status'}: return {'status':'ok','payload':self.snapshots.latest_dashboard_payload()}
            if cmd in {'tick','monitor_tick'}: return self.monitor.tick(payload.get('state'))
            if cmd in {'snapshot','capture_snapshot'}: return {'status':'ok','snapshot':self.snapshots.capture_runtime_snapshot(payload)}
            if cmd in {'strategy_snapshot','capture_strategy_snapshot'}: return {'status':'ok','snapshot':self.snapshots.capture_strategy_snapshot(payload)}
            if cmd in {'history','runtime_history'}: return {'status':'ok','history':self.history.runtime_history(int(payload.get('limit',100)))}
            if cmd in {'trend','runtime_trend'}: return {'status':'ok','trend':self.history.summarize_runtime_trend(int(payload.get('limit',100)))}
            if cmd in {'events','event_history'}: return {'status':'ok','events':self.history.event_history(int(payload.get('limit',100)))}
            if cmd in {'pause_runtime','pause'}:
                self.persistence.set_value('runtime_enabled', False); self.persistence.log_event('runtime_command','Forex runtime paused','warning',payload); return {'status':'ok','message':'Forex runtime paused.'}
            if cmd in {'resume_runtime','resume'}:
                self.persistence.set_value('runtime_enabled', True); self.persistence.log_event('runtime_command','Forex runtime resumed','info',payload); return {'status':'ok','message':'Forex runtime resumed.'}
            if cmd in {'health_check','diagnostics'}: return self._health_check()
            return {'status':'error','message':f'Unknown Forex command: {command}'}
        except Exception as exc:
            self.persistence.log_event('runtime_command_error', str(exc), 'critical', {'traceback':traceback.format_exc()})
            return {'status':'error','message':str(exc),'traceback':traceback.format_exc()}
    def _health_check(self) -> Dict[str, Any]:
        return {'status':'ok','runtime_enabled':self.persistence.get_value('runtime_enabled', True),'trend':self.history.summarize_runtime_trend(25)}
