from datetime import datetime, timezone

from modules.forex.forex_autonomous_trader import get_forex_autonomous_trader
from modules.forex.forex_strategy_lab import get_forex_strategy_lab
from modules.forex.forex_portfolio_optimizer import get_forex_portfolio_optimizer

class ForexAIAssistant:
    def __init__(self, db=None):
        self.trader=get_forex_autonomous_trader(db=db)
        self.lab=get_forex_strategy_lab(db=db)
        self.optimizer=get_forex_portfolio_optimizer(db=db)


    def daily_briefing(self,
            runtime=None,
            force_refresh=False,):
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),

            "strategy_lab": self.lab.run(
                runtime=runtime,
                force_refresh=force_refresh,
            ),

            "portfolio_plan": self.optimizer.optimize(
                runtime=runtime,
                force_refresh=force_refresh,
            ),

            #
            # Sprint 25 Runtime Diagnostics
            #
            "runtime": runtime.summary() if runtime else {},
        }

    def execute(self, portfolio_id=None, user_id=None, tenant_id=None):
        return self.trader.run_cycle(
            portfolio_id=portfolio_id,
            user_id=user_id,
            tenant_id=tenant_id,
        )

_AI=None
def get_forex_ai_assistant(db=None):
    global _AI
    if _AI is None:
        _AI=ForexAIAssistant(db=db)
    return _AI
