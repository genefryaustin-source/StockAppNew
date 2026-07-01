"""
modules/forex/forex_order_flow_engine.py

Phase 16C — Institutional flow analytics.
"""
from datetime import datetime, timezone
class ForexOrderFlowEngine:
    def __init__(self, db=None): self.db=db
    def flow(self, pair="EUR/USD"):
        from modules.forex.forex_market_microstructure_v2 import get_forex_market_microstructure_v2
        micro=get_forex_market_microstructure_v2(db=self.db).dashboard(pair)
        imbalance=micro["liquidity"]["depth"].get("liquidity_imbalance_pct",0)
        return {"status":"READY","pair":pair,"dealer_bias":"BUY" if imbalance>5 else "SELL" if imbalance<-5 else "NEUTRAL","imbalance_pct":imbalance,"microstructure":micro,"generated_at":datetime.now(timezone.utc).isoformat()}
_ENGINE=None
def get_forex_order_flow_engine(db=None):
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None): _ENGINE=ForexOrderFlowEngine(db=db)
    return _ENGINE
