"""
modules/market_data/autonomous_market_data_orchestrator.py
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

import pandas as pd

from modules.market_data.provider_decision_engine import (
    get_provider_decision_engine,
)

from modules.market_data.provider_learning_engine import (
    get_provider_learning_engine,
)

from modules.market_data.provider_router import (
    get_provider_router,
    is_rate_limit_error,
)

from modules.market_data.provider_strategy_engine import (
    REQUEST_PRICE_HISTORY,
    REQUEST_LATEST_PRICE,
    get_provider_strategy_engine,
)


class AutonomousMarketDataOrchestrator:
    def __init__(self):
        self.router = get_provider_router()
        self.decision_engine = get_provider_decision_engine()
        self.learning = get_provider_learning_engine()
        self.strategy = get_provider_strategy_engine()

    def fetch_price_history(
        self,
        db,
        symbol: str,
        period: str = "1y",
        interval: str = "1d",
    ) -> Dict[str, Any]:
        from modules.market_data.service import (
            get_price_history_internal,
        )

        request_type = REQUEST_PRICE_HISTORY

        allowed = self.strategy.get_allowed_providers(
            request_type,
            db=db,
        )

        decision = self.decision_engine.decide(
            request_type=request_type,
            symbol=symbol,
            allowed_providers=allowed,
        )
        for provider_name in decision.failover_chain:
            print(
                "FAILOVER CHAIN:",
                decision.failover_chain
            )
            try:

                print(
                    "TRYING PROVIDER:",
                    provider_name,
                    symbol,
                )

                df = get_price_history_internal(
                    db=db,
                    symbol=symbol,
                    period=period,
                    interval=interval,
                    force_refresh=True,
                    provider_override=provider_name,
                )

                if (
                        df is not None
                        and not df.empty
                ):
                    return {
                        "symbol": symbol,
                        "request_type": request_type,
                        "provider": provider_name,
                        "success": True,
                        "rows": len(df),
                        "data": df,
                    }

                print(
                    "EMPTY RESULT:",
                    provider_name,
                    symbol,
                )

                continue


            except Exception as e:

                if is_rate_limit_error(e):

                    self.router.mark_rate_limited(

                        provider_name

                    )


                else:

                    self.router.mark_failure(

                        provider_name

                    )

                continue

        start = time.time()

        try:
            df = get_price_history_internal(
                db=db,
                symbol=symbol,
                period=period,
                interval=interval,
                force_refresh=True,
            )

            latency_ms = (
                time.time() - start
            ) * 1000

            success = (
                isinstance(df, pd.DataFrame)
                and not df.empty
            )

            if decision.selected_provider:
                self.learning.record_outcome(
                    db=db,
                    provider=decision.selected_provider,
                    request_type=request_type,
                    symbol=symbol,
                    success=success,
                    latency_ms=latency_ms,
                    error=None if success else "EMPTY_HISTORY",
                )

            return {
                "symbol": symbol,
                "request_type": request_type,
                "provider_decision": self.decision_engine.as_dict(decision),
                "success": success,
                "rows": len(df) if isinstance(df, pd.DataFrame) else 0,
                "data": df,
            }

        except Exception as e:
            latency_ms = (
                time.time() - start
            ) * 1000

            if decision.selected_provider:
                if is_rate_limit_error(e):
                    self.router.mark_rate_limited(
                        decision.selected_provider,
                    )
                else:
                    self.router.mark_failure(
                        decision.selected_provider,
                    )

                self.learning.record_outcome(
                    db=db,
                    provider=decision.selected_provider,
                    request_type=request_type,
                    symbol=symbol,
                    success=False,
                    latency_ms=latency_ms,
                    error=str(e),
                )

            return {
                "symbol": symbol,
                "request_type": request_type,
                "provider_decision": self.decision_engine.as_dict(decision),
                "success": False,
                "rows": 0,
                "data": pd.DataFrame(),
                "error": str(e),
            }

    def fetch_latest_price(
        self,
        db,
        symbol: str,
    ) -> Dict[str, Any]:
        from modules.market_data.service import (
            get_latest_price,
        )

        request_type = REQUEST_LATEST_PRICE

        allowed = self.strategy.get_allowed_providers(
            request_type,
            db=db,
        )

        decision = self.decision_engine.decide(
            request_type=request_type,
            symbol=symbol,
            allowed_providers=allowed,
        )

        start = time.time()

        try:
            price = get_latest_price(
                symbol,
            )

            latency_ms = (
                time.time() - start
            ) * 1000

            success = price is not None

            if decision.selected_provider:
                self.learning.record_outcome(
                    db=db,
                    provider=decision.selected_provider,
                    request_type=request_type,
                    symbol=symbol,
                    success=success,
                    latency_ms=latency_ms,
                    error=None if success else "NO_PRICE",
                )

            return {
                "symbol": symbol,
                "request_type": request_type,
                "provider_decision": self.decision_engine.as_dict(decision),
                "success": success,
                "price": price,
            }

        except Exception as e:
            latency_ms = (
                time.time() - start
            ) * 1000

            if decision.selected_provider:
                self.learning.record_outcome(
                    db=db,
                    provider=decision.selected_provider,
                    request_type=request_type,
                    symbol=symbol,
                    success=False,
                    latency_ms=latency_ms,
                    error=str(e),
                )

            return {
                "symbol": symbol,
                "request_type": request_type,
                "provider_decision": self.decision_engine.as_dict(decision),
                "success": False,
                "price": None,
                "error": str(e),
            }


_orchestrator: Optional[
    AutonomousMarketDataOrchestrator
] = None


def get_autonomous_market_data_orchestrator():
    global _orchestrator

    if _orchestrator is None:
        _orchestrator = (
            AutonomousMarketDataOrchestrator()
        )

    return _orchestrator