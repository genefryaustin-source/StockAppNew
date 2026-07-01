from datetime import datetime, timezone
class ForexLiquidityEngine:
    def __init__(self, db=None): self.db=db
    def liquidity(self, pair="EUR/USD"):
        from modules.forex.forex_market_depth import get_forex_market_depth
        depth=get_forex_market_depth(db=self.db).depth(pair=pair)
        return {"status":"READY","pair":pair,"depth":depth,"liquidity_score":depth.get("depth_score",75),"generated_at":datetime.now(timezone.utc).isoformat()}
_ENGINE=None
def get_forex_liquidity_engine(db=None):
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None): _ENGINE=ForexLiquidityEngine(db=db)
    return _ENGINE
