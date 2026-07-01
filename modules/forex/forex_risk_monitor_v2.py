from datetime import datetime, timezone
class ForexRiskMonitorV2:
    def __init__(self, db=None): self.db=db
    def monitor(self, snapshot=None):
        snapshot=snapshot or {}
        risk=snapshot.get("risk") or {}
        score=float(risk.get("risk_score") or 75)
        alerts=[] if score>=60 else [{"severity":"high","message":"Risk score below threshold"}]
        return {"status":"READY","risk_score":score,"alerts":alerts,"generated_at":datetime.now(timezone.utc).isoformat()}
_ENGINE=None
def get_forex_risk_monitor_v2(db=None):
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None): _ENGINE=ForexRiskMonitorV2(db=db)
    return _ENGINE
