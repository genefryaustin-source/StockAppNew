from modules.forex.forex_execution_algorithms import get_forex_execution_algorithms

class ForexVWAPEngine:
    def __init__(self, db=None): self.db = db
    def plan(self, **kwargs):
        kwargs["algo"] = "VWAP"
        return get_forex_execution_algorithms(db=self.db).plan(**kwargs)

_VWAP=None
def get_forex_vwap_engine(db=None):
    global _VWAP
    if _VWAP is None or (db is not None and _VWAP.db is None): _VWAP=ForexVWAPEngine(db=db)
    return _VWAP
