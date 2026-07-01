from datetime import datetime, timezone
class ForexGDPEngine:
    def __init__(self, db=None): self.db=db
    def growth(self):
        return {"status":"READY","rows":[
            {"currency":"USD","gdp_growth":2.1,"trend":"Resilient"},
            {"currency":"EUR","gdp_growth":0.6,"trend":"Weak"},
            {"currency":"JPY","gdp_growth":0.8,"trend":"Soft"},
            {"currency":"GBP","gdp_growth":0.9,"trend":"Recovering"},
            {"currency":"AUD","gdp_growth":1.5,"trend":"Stable"},
        ],"generated_at":datetime.now(timezone.utc).isoformat()}
_ENGINE=None
def get_forex_gdp_engine(db=None):
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None): _ENGINE=ForexGDPEngine(db=db)
    return _ENGINE
