from datetime import datetime, timezone

from modules.forex.forex_alpha_model import get_forex_alpha_model
from modules.forex.forex_macro_regime_engine import get_forex_macro_regime_engine
from modules.forex.forex_sentiment_engine import get_forex_sentiment_engine
from modules.forex.forex_trade_execution_engine import get_forex_trade_execution_engine
from modules.forex.forex_alpha_execution_profiler import (
    profile_alpha_execution,
)
class ForexStrategyEngine:
    def __init__(self,db=None):
        self.alpha=get_forex_alpha_model(); self.regime=get_forex_macro_regime_engine(); self.sentiment=get_forex_sentiment_engine(); self.execution=get_forex_trade_execution_engine(db=db)

    @profile_alpha_execution("ForexStrategyEngine.generate_trade_plan")
    def generate_trade_plan(
            self,
            runtime=None,
            force_refresh=False,
    ):
        #
        # Alpha
        #
        if runtime is not None and getattr(runtime, "alpha", None):

            a = runtime.alpha

        else:

            a = self.alpha.run_alpha_model(
                force_refresh=force_refresh,
            )

        #
        # Macro Regime
        #
        if runtime is not None and getattr(runtime, "macro", None):

            r = runtime.macro



        else:

            r = self.regime.analyze(
                force_refresh=force_refresh,
            )

        #
        # Sentiment
        #
        if runtime is not None and getattr(runtime, "sentiment", None):

            s = runtime.sentiment


        else:

            s = self.sentiment.analyze(

                force_refresh=force_refresh,

            )

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),

            "macro_regime": (
                r.get("macro_regime")
                if isinstance(r, dict)
                else None
            ),

            "signals": (
                a.get("signals", [])
                if isinstance(a, dict)
                else []
            ),

            "top_trades": (
                a.get(
                    "top_opportunities",
                    a.get("signals", [])[:10],
                )
                if isinstance(a, dict)
                else []
            ),

            "sentiment": (
                s.get("overall_sentiment")
                if isinstance(s, dict)
                else None
            ),

            #
            # Sprint 25 Diagnostics
            #
            "runtime_source": (
                "shared"
                if runtime is not None
                else "local"
            ),

            "used_shared_runtime": runtime is not None,
        }

    def execute_top_trade(
            self,
            runtime=None,
            portfolio_id=None,
            user_id=None,
            tenant_id=None,
            force_refresh=False,
    ):
        plan = self.generate_trade_plan(
            runtime=runtime,
            force_refresh=force_refresh,
        )

        trades = plan.get("top_trades", [])

        if not trades:
            return {
                "status": "no_trades",
                "trade_plan": plan,
            }

        return self.execution.execute_recommendation(
            trades[0],
            portfolio_id=portfolio_id,
            user_id=user_id,
            tenant_id=tenant_id,
        )
_ENGINE=None
def get_forex_strategy_engine(db=None):
 global _ENGINE
 if _ENGINE is None: _ENGINE=ForexStrategyEngine(db=db)
 return _ENGINE
