from datetime import datetime, timezone
class ForexRiskAlerts:
    def __init__(self, db=None): self.db=db
    def alerts(self, snapshot=None):
        snapshot=snapshot or {}
        alerts=[]
        risk=(snapshot.get("risk") or {}).get("risk_score",100)
        try: risk=float(risk)
        except Exception: risk=100
        if risk<60: alerts.append({"type":"risk","severity":"high","message":"Portfolio risk score below threshold"})
        return {"status":"READY","alerts":alerts,"generated_at":datetime.now(timezone.utc).isoformat()}
_ENGINE=None
def get_forex_risk_alerts(db=None):
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None): _ENGINE=ForexRiskAlerts(db=db)
    return _ENGINE
