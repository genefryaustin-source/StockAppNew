from datetime import datetime, timezone

from modules.forex.forex_strategy_lab import get_forex_strategy_lab
from modules.forex.forex_trade_execution_engine import get_forex_trade_execution_engine
from modules.forex.forex_risk_management_engine import get_forex_risk_management_engine

class ForexAutonomousTrader:
    def __init__(self, db=None):
        self.lab=get_forex_strategy_lab(db=db)
        self.execution=get_forex_trade_execution_engine(db=db)
        self.risk=get_forex_risk_management_engine(db=db)

    def run_cycle(self, portfolio_id=None, user_id=None, tenant_id=None):
        risk=self.risk.analyze()
        if risk.get("risk_level")=="HIGH":
            return {
                "generated_at":datetime.now(timezone.utc).isoformat(),
                "status":"blocked",
                "reason":"Risk controls prevented autonomous execution.",
                "risk":risk,
            }

        plan=self.lab.run()
        trade_plan=plan.get("trade_plan",{})
        trades=trade_plan.get("top_trades",[])
        if not trades:
            return {
                "generated_at":datetime.now(timezone.utc).isoformat(),
                "status":"idle",
                "reason":"No qualifying trade opportunities."
            }

        result=self.execution.execute_recommendation(
            trades[0],
            portfolio_id=portfolio_id,
            user_id=user_id,
            tenant_id=tenant_id,
        )

        return {
            "generated_at":datetime.now(timezone.utc).isoformat(),
            "status":"executed",
            "trade":result,
            "risk":risk,
        }

_TRADER=None

def get_forex_autonomous_trader(db=None):
    global _TRADER
    if _TRADER is None:
        _TRADER=ForexAutonomousTrader(db=db)
    return _TRADER
