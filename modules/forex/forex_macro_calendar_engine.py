from datetime import datetime, timezone
class ForexMacroCalendarEngine:
    def __init__(self, db=None): self.db=db
    def calendar(self):
        return {"status":"READY","events":[
            {"time":"08:30","currency":"USD","event":"Core PCE","impact":"High"},
            {"time":"09:00","currency":"EUR","event":"ECB Speaker","impact":"High"},
            {"time":"19:50","currency":"JPY","event":"Tankan Survey","impact":"Medium"},
        ],"generated_at":datetime.now(timezone.utc).isoformat()}
_ENGINE=None
def get_forex_macro_calendar_engine(db=None):
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None): _ENGINE=ForexMacroCalendarEngine(db=db)
    return _ENGINE
