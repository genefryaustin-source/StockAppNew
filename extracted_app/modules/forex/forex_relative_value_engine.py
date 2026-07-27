from datetime import datetime, timezone
class ForexRelativeValueEngine:
    def __init__(self, db=None): self.db=db
    def relative_value(self):
        from modules.forex.forex_currency_rankings import get_forex_currency_rankings
        rows=get_forex_currency_rankings(db=self.db).rankings()["rows"]
        leader,laggard=rows[0],rows[-1]
        return {"status":"READY","best_long":leader,"best_short":laggard,"preferred_cross":f"{leader['currency']}/{laggard['currency']}","generated_at":datetime.now(timezone.utc).isoformat()}
_ENGINE=None
def get_forex_relative_value_engine(db=None):
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None): _ENGINE=ForexRelativeValueEngine(db=db)
    return _ENGINE
