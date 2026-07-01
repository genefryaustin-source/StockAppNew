"""
modules/forex/forex_ai_research_copilot.py

Phase 16F — AI Research Copilot.
"""
from datetime import datetime, timezone
class ForexAIResearchCopilot:
    def __init__(self, db=None): self.db=db
    def dashboard(self, snapshot=None):
        from modules.forex.forex_ai_briefing_generator import get_forex_ai_briefing_generator
        from modules.forex.forex_market_commentary_engine import get_forex_market_commentary_engine
        from modules.forex.forex_trade_explainer import get_forex_trade_explainer
        briefing=get_forex_ai_briefing_generator(db=self.db).briefing(snapshot)
        commentary=get_forex_market_commentary_engine(db=self.db).commentary()
        sample_trade={"pair":"EUR/USD","side":"BUY"}
        explanation=get_forex_trade_explainer(db=self.db).explain(sample_trade)
        return {"status":"READY","briefing":briefing,"commentary":commentary,"trade_explanation":explanation,"generated_at":datetime.now(timezone.utc).isoformat()}
_ENGINE=None
def get_forex_ai_research_copilot(db=None):
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None): _ENGINE=ForexAIResearchCopilot(db=db)
    return _ENGINE
