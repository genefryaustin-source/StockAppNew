from datetime import datetime, timezone
class ForexVolumeProfileEngine:
    def __init__(self, db=None): self.db=db
    def profile(self, pair="EUR/USD"):
        base=1.0718 if "EUR/USD" in pair else 1.0
        rows=[{"price":round(base+i*0.0002,5),"volume_m":round(12+abs(hash(pair+str(i)))%28,2)} for i in range(-10,11)]
        return {"status":"READY","pair":pair,"poc":max(rows,key=lambda r:r["volume_m"]),"rows":rows,"generated_at":datetime.now(timezone.utc).isoformat()}
_ENGINE=None
def get_forex_volume_profile_engine(db=None):
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None): _ENGINE=ForexVolumeProfileEngine(db=db)
    return _ENGINE
