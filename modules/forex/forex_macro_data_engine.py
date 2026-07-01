"""
modules/forex/forex_macro_data_engine.py

Phase 16B — Institutional macro intelligence engine.
"""
from datetime import datetime, timezone
class ForexMacroDataEngine:
    def __init__(self, db=None): self.db=db
    def dashboard(self):
        from modules.forex.forex_interest_rate_engine import get_forex_interest_rate_engine
        from modules.forex.forex_inflation_engine import get_forex_inflation_engine
        from modules.forex.forex_gdp_engine import get_forex_gdp_engine
        from modules.forex.forex_macro_calendar_engine import get_forex_macro_calendar_engine
        rates=get_forex_interest_rate_engine(db=self.db).rates()
        inflation=get_forex_inflation_engine(db=self.db).inflation()
        growth=get_forex_gdp_engine(db=self.db).growth()
        calendar=get_forex_macro_calendar_engine(db=self.db).calendar()
        scorecard=[]
        by_ccy={}
        for r in rates["rows"]: by_ccy.setdefault(r["currency"],{}).update(r)
        for r in inflation["rows"]: by_ccy.setdefault(r["currency"],{}).update(r)
        for r in growth["rows"]: by_ccy.setdefault(r["currency"],{}).update(r)
        for ccy,row in by_ccy.items():
            score=(row.get("policy_rate",0)*8)+(row.get("gdp_growth",0)*10)-(row.get("cpi_yoy",0)*4)
            scorecard.append({"currency":ccy,"macro_score":round(score,2),**row})
        scorecard.sort(key=lambda x:x["macro_score"],reverse=True)
        return {"status":"READY","generated_at":datetime.now(timezone.utc).isoformat(),"rates":rates,"inflation":inflation,"growth":growth,"calendar":calendar,"scorecard":scorecard}
_ENGINE=None
def get_forex_macro_data_engine(db=None):
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None): _ENGINE=ForexMacroDataEngine(db=db)
    return _ENGINE
