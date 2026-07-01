from modules.forex.forex_execution_algorithms import get_forex_execution_algorithms

class ForexIcebergOrders:
    def __init__(self, db=None): self.db = db
    def plan(self, **kwargs):
        kwargs["algo"] = "ICEBERG"
        return get_forex_execution_algorithms(db=self.db).plan(**kwargs)

_ICE=None
def get_forex_iceberg_orders(db=None):
    global _ICE
    if _ICE is None or (db is not None and _ICE.db is None): _ICE=ForexIcebergOrders(db=db)
    return _ICE
