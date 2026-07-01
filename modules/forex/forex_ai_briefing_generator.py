from datetime import datetime, timezone
class ForexAIBriefingGenerator:
    def __init__(self, db=None): self.db=db
    def briefing(self, payload=None):
        return {"status":"READY","headline":"FX desk briefing: monitor USD strength, CHF safe-haven demand, and AUD downside risk.","bullets":["USD remains supported by rate differentials.","CHF ranks strongly in defensive regime.","AUD/NZD remain vulnerable in risk-off tape."],"generated_at":datetime.now(timezone.utc).isoformat()}
_ENGINE=None
def get_forex_ai_briefing_generator(db=None):
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None): _ENGINE=ForexAIBriefingGenerator(db=db)
    return _ENGINE
