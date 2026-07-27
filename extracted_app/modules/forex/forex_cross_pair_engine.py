from datetime import datetime, timezone
class ForexCrossPairEngine:
    def __init__(self, db=None): self.db=db
    def crosses(self):
        return {"status":"READY","rows":[
            {"cross":"EUR/GBP","bias":"WATCH","rationale":"Mixed EUR/GBP ranking"},
            {"cross":"AUD/JPY","bias":"SELL","rationale":"Risk-off cross pressure"},
            {"cross":"CHF/JPY","bias":"BUY","rationale":"CHF safe-haven leadership"},
        ],"generated_at":datetime.now(timezone.utc).isoformat()}
_ENGINE=None
def get_forex_cross_pair_engine(db=None):
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None): _ENGINE=ForexCrossPairEngine(db=db)
    return _ENGINE
