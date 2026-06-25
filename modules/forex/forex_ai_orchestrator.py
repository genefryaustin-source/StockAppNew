from datetime import datetime, timezone

from modules.forex.forex_ai_assistant import get_forex_ai_assistant
from modules.forex.forex_service import get_forex_service

class ForexAIOrchestrator:
    def __init__(self, db=None):
        self.ai=get_forex_ai_assistant(db=db)
        self.service=get_forex_service()

    def morning_brief(self):
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "market": self.service.get_command_center(),
            "briefing": self.ai.daily_briefing(),
        }

    def autonomous_cycle(self, portfolio_id=None, user_id=None, tenant_id=None):
        self.service.refresh_market_data()
        return self.ai.execute(
            portfolio_id=portfolio_id,
            user_id=user_id,
            tenant_id=tenant_id,
        )

_ORCH=None

def get_forex_ai_orchestrator(db=None):
    global _ORCH
    if _ORCH is None:
        _ORCH=ForexAIOrchestrator(db=db)
    return _ORCH
