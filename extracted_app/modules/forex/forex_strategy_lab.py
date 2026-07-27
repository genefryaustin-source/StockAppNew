from datetime import datetime, timezone
from modules.forex.forex_strategy_engine import get_forex_strategy_engine
from modules.forex.forex_trade_journal_engine import get_forex_trade_journal_engine
from modules.forex.forex_performance_analytics_engine import get_forex_performance_analytics_engine
from modules.forex.forex_alpha_execution_profiler import (
    profile_alpha_execution,
)
class ForexStrategyLab:
    def __init__(self, db=None):
        self.strategy=get_forex_strategy_engine(db=db)
        self.journal=get_forex_trade_journal_engine(db=db)
        self.performance=get_forex_performance_analytics_engine(db=db)

    @profile_alpha_execution("ForexStrategyLab.run")
    def run(
            self,
            runtime=None,
            force_refresh=False,
    ):
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),

            "trade_plan": self.strategy.generate_trade_plan(
                runtime=runtime,
                force_refresh=force_refresh,
            ),

            "performance": self.performance.analyze(),

            "journal": self.journal.summarize(),

            #
            # Sprint 25 Runtime Diagnostics
            #
            "runtime": runtime.summary() if runtime else {},
        }
    def execute_best_strategy(self, portfolio_id=None, user_id=None, tenant_id=None):
        return self.strategy.execute_top_trade(portfolio_id=portfolio_id,user_id=user_id,tenant_id=tenant_id)

_LAB=None
def get_forex_strategy_lab(db=None):
    global _LAB
    if _LAB is None:
        _LAB=ForexStrategyLab(db=db)
    return _LAB
