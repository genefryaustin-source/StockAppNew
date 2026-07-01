"""
modules/forex/forex_alert_manager_v2.py

Phase 16E — Institutional alert manager.
"""
from datetime import datetime, timezone
class ForexAlertManagerV2:
    def __init__(self, db=None): self.db=db
    def dashboard(self, snapshot=None):
        from modules.forex.forex_event_detector import get_forex_event_detector
        from modules.forex.forex_breakout_detector import get_forex_breakout_detector
        from modules.forex.forex_risk_alerts import get_forex_risk_alerts
        events=get_forex_event_detector(db=self.db).events()["events"]
        breakouts=get_forex_breakout_detector(db=self.db).breakouts()["breakouts"]
        risk=get_forex_risk_alerts(db=self.db).alerts(snapshot=snapshot)["alerts"]
        alerts=events+breakouts+risk
        return {"status":"READY","alert_count":len(alerts),"alerts":alerts,"generated_at":datetime.now(timezone.utc).isoformat()}
_ENGINE=None
def get_forex_alert_manager_v2(db=None):
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None): _ENGINE=ForexAlertManagerV2(db=db)
    return _ENGINE
