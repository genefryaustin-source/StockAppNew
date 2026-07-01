from datetime import datetime, timezone

from modules.forex.forex_alpha_model import get_forex_alpha_model
from modules.forex.forex_portfolio_manager import get_forex_portfolio_manager
from modules.forex.forex_risk_management_engine import get_forex_risk_management_engine

from modules.forex.forex_alpha_execution_profiler import (
    profile_alpha_execution,
)
class ForexPortfolioOptimizer:
    def __init__(self, db=None):
        self.alpha = get_forex_alpha_model()
        self.portfolio = get_forex_portfolio_manager(db=db)
        self.risk = get_forex_risk_management_engine(db=db)

    @profile_alpha_execution("ForexPortfolioOptimizer.run")
    def optimize(
            self,
            runtime=None,
            max_positions=5,
            min_alpha_score=68.0,
            account_size=100000.0,
            force_refresh=False,
    ):
        #
        # Use shared runtime Alpha if available.
        #
        print("=" * 80)
        print("PORTFOLIO OPTIMIZER")
        print("runtime id :", id(runtime) if runtime else None)
        print("has alpha  :", runtime is not None and runtime.alpha is not None)
        print("=" * 80)

        if runtime is not None and getattr(runtime, "alpha", None) is not None:
            scan = runtime.alpha
            source = "runtime"
        else:
            scan = self.alpha.run_alpha_model(
                force_refresh=force_refresh,
            )
            source = "local"

        print("Alpha Source:", source)

        signals = [
            s for s in scan.get("signals", [])
            if float(s.get("alpha_score") or 0) >= float(min_alpha_score)
               and s.get("recommendation") not in ("WATCH", "NO_TRADE")
        ]

        signals = signals[:int(max_positions)]

        risk_budget = account_size * 0.005
        allocations = []
        for s in signals:
            confidence = float(s.get('confidence_score') or 50)
            weight = confidence / max(sum(float(x.get('confidence_score') or 50) for x in signals), 1)
            notional = account_size * weight
            allocations.append({
                'pair': s.get('pair'),
                'direction': s.get('direction'),
                'recommendation': s.get('recommendation'),
                'alpha_score': s.get('alpha_score'),
                'confidence_score': s.get('confidence_score'),
                'target_weight': round(weight * 100, 2),
                'target_notional': round(notional, 2),
                'risk_budget': round(risk_budget, 2),
                'entry_price': s.get('entry_price'),
                'stop_price': s.get('stop_price'),
                'target_price': s.get('target_price'),
                'risk_reward': s.get('risk_reward'),
            })

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),

            "account_size": account_size,

            "max_positions": max_positions,

            "allocations": allocations,

            "signals_considered": len(scan.get("signals", [])),

            "selected_positions": len(allocations),

            #
            # Sprint 25 Runtime Diagnostics
            #
            "runtime_source": runtime_source,

            "used_shared_runtime": runtime_source == "runtime",
        }


_OPTIMIZER = None

def get_forex_portfolio_optimizer(db=None):
    global _OPTIMIZER
    if _OPTIMIZER is None:
        _OPTIMIZER = ForexPortfolioOptimizer(db=db)
    return _OPTIMIZER
