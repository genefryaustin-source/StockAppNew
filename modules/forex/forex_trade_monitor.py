from datetime import datetime, timezone
class ForexTradeMonitor:
    def __init__(self, db=None): self.db=db
    def monitor(self, trades=None):
        trades=trades or []
        return {"status":"READY","trade_count":len(trades),"recommendations":[],"generated_at":datetime.now(timezone.utc).isoformat()}
_ENGINE=None
def get_forex_trade_monitor(db=None):
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None): _ENGINE=ForexTradeMonitor(db=db)
    return _ENGINE
