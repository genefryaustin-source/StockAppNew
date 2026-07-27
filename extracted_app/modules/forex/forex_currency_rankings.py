from datetime import datetime, timezone
class ForexCurrencyRankings:
    def __init__(self, db=None): self.db=db
    def rankings(self):
        ccys=["USD","EUR","JPY","GBP","CHF","AUD","CAD","NZD"]
        rows=[{"currency":c,"rank_score":round((abs(hash(c))%1000)/10,2)} for c in ccys]
        rows.sort(key=lambda r:r["rank_score"],reverse=True)
        return {"status":"READY","rows":rows,"leader":rows[0],"laggard":rows[-1],"generated_at":datetime.now(timezone.utc).isoformat()}
_ENGINE=None
def get_forex_currency_rankings(db=None):
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None): _ENGINE=ForexCurrencyRankings(db=db)
    return _ENGINE
