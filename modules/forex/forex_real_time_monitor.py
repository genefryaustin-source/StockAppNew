"""
modules/forex/forex_real_time_monitor.py

Phase 18E — Institutional real-time monitor.
"""
from datetime import datetime, timezone
class ForexRealTimeMonitor:
    def __init__(self, db=None): self.db=db
    def dashboard(self, snapshot=None, trades=None):
        from modules.forex.forex_position_monitor import get_forex_position_monitor
        from modules.forex.forex_risk_monitor_v2 import get_forex_risk_monitor_v2
        from modules.forex.forex_trade_monitor import get_forex_trade_monitor
        return {
            "status":"READY",
            "positions":get_forex_position_monitor(db=self.db).monitor(snapshot),
            "risk":get_forex_risk_monitor_v2(db=self.db).monitor(snapshot),
            "trades":get_forex_trade_monitor(db=self.db).monitor(trades),
            "generated_at":datetime.now(timezone.utc).isoformat(),
        }
_ENGINE=None
def get_forex_real_time_monitor(db=None):
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None): _ENGINE=ForexRealTimeMonitor(db=db)
    return _ENGINE
