from datetime import datetime, timezone

from modules.forex.forex_ai_orchestrator import get_forex_ai_orchestrator
from modules.forex.forex_service import get_forex_service

class ForexCommandProcessor:
    def __init__(self, db=None):
        self.ai=get_forex_ai_orchestrator(db=db)
        self.service=get_forex_service()

    def execute(self, command:str, **kwargs):
        cmd=(command or '').strip().lower()

        if cmd=='refresh':
            return self.service.refresh_market_data()
        if cmd=='briefing':
            return self.ai.morning_brief()
        if cmd=='autonomous_cycle':
            return self.ai.autonomous_cycle(**kwargs)
        if cmd=='command_center':
            return self.service.get_command_center()
        if cmd=='alpha':
            return self.service.get_alpha_recommendations()
        if cmd=='strength':
            return self.service.get_currency_strength()
        if cmd=='macro':
            return self.service.get_macro_regime()
        if cmd=='sentiment':
            return self.service.get_sentiment()

        return {
            'status':'unknown_command',
            'command':command,
            'timestamp':datetime.now(timezone.utc).isoformat()
        }

_PROCESSOR=None

def get_forex_command_processor(db=None):
    global _PROCESSOR
    if _PROCESSOR is None:
        _PROCESSOR=ForexCommandProcessor(db=db)
    return _PROCESSOR
