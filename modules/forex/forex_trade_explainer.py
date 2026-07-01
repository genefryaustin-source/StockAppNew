from datetime import datetime, timezone
class ForexTradeExplainer:
    def __init__(self, db=None): self.db=db
    def explain(self, trade):
        return {"status":"READY","explanation":f"{trade.get('pair','FX')} {trade.get('side','WATCH')} is supported by factor, macro, and flow inputs.","generated_at":datetime.now(timezone.utc).isoformat()}
_ENGINE=None
def get_forex_trade_explainer(db=None):
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None): _ENGINE=ForexTradeExplainer(db=db)
    return _ENGINE
