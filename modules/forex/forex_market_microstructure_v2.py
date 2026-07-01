from datetime import datetime, timezone
class ForexMarketMicrostructureV2:
    def __init__(self, db=None): self.db=db
    def dashboard(self, pair="EUR/USD"):
        from modules.forex.forex_liquidity_engine import get_forex_liquidity_engine
        from modules.forex.forex_volume_profile_engine import get_forex_volume_profile_engine
        return {"status":"READY","pair":pair,"liquidity":get_forex_liquidity_engine(db=self.db).liquidity(pair),"volume_profile":get_forex_volume_profile_engine(db=self.db).profile(pair),"generated_at":datetime.now(timezone.utc).isoformat()}
_ENGINE=None
def get_forex_market_microstructure_v2(db=None):
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None): _ENGINE=ForexMarketMicrostructureV2(db=db)
    return _ENGINE
