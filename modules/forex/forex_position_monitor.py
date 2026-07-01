from datetime import datetime, timezone
class ForexPositionMonitor:
    def __init__(self, db=None): self.db=db
    def monitor(self, snapshot=None):
        snapshot=snapshot or {}
        positions=snapshot.get("positions") or []
        return {"status":"READY","position_count":len(positions),"alerts":[],"generated_at":datetime.now(timezone.utc).isoformat()}
_ENGINE=None
def get_forex_position_monitor(db=None):
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None): _ENGINE=ForexPositionMonitor(db=db)
    return _ENGINE
