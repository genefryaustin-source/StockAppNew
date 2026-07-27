from modules.forex.forex_execution_algorithms import get_forex_execution_algorithms

class ForexTWAPEngine:
    def __init__(self, db=None): self.db = db
    def plan(self, **kwargs):
        kwargs["algo"] = "TWAP"
        return get_forex_execution_algorithms(db=self.db).plan(**kwargs)

_TWAP=None
def get_forex_twap_engine(db=None):
    global _TWAP
    if _TWAP is None or (db is not None and _TWAP.db is None): _TWAP=ForexTWAPEngine(db=db)
    return _TWAP
