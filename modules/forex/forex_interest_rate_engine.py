from datetime import datetime, timezone
class ForexInterestRateEngine:
    def __init__(self, db=None): self.db=db
    def rates(self):
        return {"status":"READY","rows":[
            {"currency":"USD","policy_rate":5.50,"bias":"Hawkish"},
            {"currency":"EUR","policy_rate":4.25,"bias":"Neutral"},
            {"currency":"JPY","policy_rate":0.10,"bias":"Dovish"},
            {"currency":"GBP","policy_rate":5.25,"bias":"Hawkish"},
            {"currency":"CHF","policy_rate":1.50,"bias":"Dovish"},
            {"currency":"AUD","policy_rate":4.35,"bias":"Neutral"},
            {"currency":"CAD","policy_rate":4.75,"bias":"Neutral"},
            {"currency":"NZD","policy_rate":5.50,"bias":"Hawkish"},
        ],"generated_at":datetime.now(timezone.utc).isoformat()}
_ENGINE=None
def get_forex_interest_rate_engine(db=None):
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None): _ENGINE=ForexInterestRateEngine(db=db)
    return _ENGINE
