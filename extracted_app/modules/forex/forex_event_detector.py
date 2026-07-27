from datetime import datetime, timezone
class ForexEventDetector:
    def __init__(self, db=None): self.db=db
    def events(self):
        return {"status":"READY","events":[{"type":"macro","severity":"high","message":"USD Core PCE upcoming"}],"generated_at":datetime.now(timezone.utc).isoformat()}
_ENGINE=None
def get_forex_event_detector(db=None):
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None): _ENGINE=ForexEventDetector(db=db)
    return _ENGINE
