from datetime import datetime, timezone
class ForexMarketCommentaryEngine:
    def __init__(self, db=None): self.db=db
    def commentary(self):
        return {"status":"READY","commentary":"Markets are trading with a defensive FX tone. USD and CHF are leading, while high-beta currencies remain under pressure.","generated_at":datetime.now(timezone.utc).isoformat()}
_ENGINE=None
def get_forex_market_commentary_engine(db=None):
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None): _ENGINE=ForexMarketCommentaryEngine(db=db)
    return _ENGINE
