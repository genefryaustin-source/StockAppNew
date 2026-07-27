from datetime import datetime, timezone
class ForexInflationEngine:
    def __init__(self, db=None): self.db=db
    def inflation(self):
        return {"status":"READY","rows":[
            {"currency":"USD","cpi_yoy":3.3,"trend":"Cooling"},
            {"currency":"EUR","cpi_yoy":2.6,"trend":"Sticky"},
            {"currency":"JPY","cpi_yoy":2.8,"trend":"Rising"},
            {"currency":"GBP","cpi_yoy":2.9,"trend":"Cooling"},
            {"currency":"AUD","cpi_yoy":3.6,"trend":"Sticky"},
        ],"generated_at":datetime.now(timezone.utc).isoformat()}
_ENGINE=None
def get_forex_inflation_engine(db=None):
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None): _ENGINE=ForexInflationEngine(db=db)
    return _ENGINE
