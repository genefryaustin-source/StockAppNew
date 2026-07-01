"""
modules/forex/forex_command_center_engine.py

Sprint 25 runtime-aware Forex Command Center engine.

Purpose
-------
Builds the command-center payload while consuming the shared ForexRuntimeContext
when available. This prevents duplicate Alpha, Sentiment, Macro, Currency
Strength, and Institutional Scanner executions during a single dashboard render.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from modules.forex.forex_alpha_execution_profiler import (
    profile_alpha_execution,
)
from modules.forex.forex_runtime_context import (
    build_forex_runtime_context,
)
try:
    from modules.forex.forex_currency_strength_engine import (
        get_forex_currency_strength_engine,
    )
except Exception:
    get_forex_currency_strength_engine = None

try:
    from modules.forex.forex_alpha_model import get_forex_alpha_model
except Exception:
    get_forex_alpha_model = None

try:
    from modules.forex.forex_macro_regime_engine import (
        get_forex_macro_regime_engine,
    )
except Exception:
    get_forex_macro_regime_engine = None

try:
    from modules.forex.forex_carry_trade_engine import (
        get_forex_carry_trade_engine,
    )
except Exception:
    get_forex_carry_trade_engine = None

try:
    from modules.forex.forex_institutional_scanner import (
        get_forex_institutional_scanner,
    )
except Exception:
    get_forex_institutional_scanner = None

try:
    from modules.forex.forex_central_bank_engine import (
        get_forex_central_bank_engine,
    )
except Exception:
    get_forex_central_bank_engine = None

try:
    from modules.forex.forex_sentiment_engine import (
        get_forex_sentiment_engine,
    )
except Exception:
    get_forex_sentiment_engine = None


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _runtime_summary(runtime: Any) -> Dict[str, Any]:
    if runtime is None or not hasattr(runtime, "summary"):
        return {}
    try:
        summary = runtime.summary()
        return summary if isinstance(summary, dict) else {}
    except Exception:
        return {}


class ForexCommandCenterEngine:
    def __init__(self):
        self.strength = (
            get_forex_currency_strength_engine()
            if get_forex_currency_strength_engine
            else None
        )
        self.alpha = get_forex_alpha_model() if get_forex_alpha_model else None
        self.regime = (
            get_forex_macro_regime_engine()
            if get_forex_macro_regime_engine
            else None
        )
        self.carry = (
            get_forex_carry_trade_engine()
            if get_forex_carry_trade_engine
            else None
        )
        self.inst = (
            get_forex_institutional_scanner()
            if get_forex_institutional_scanner
            else None
        )
        self.cb = (
            get_forex_central_bank_engine()
            if get_forex_central_bank_engine
            else None
        )
        self.sent = (
            get_forex_sentiment_engine()
            if get_forex_sentiment_engine
            else None
        )

    # ------------------------------------------------------------------
    # Runtime-aware loaders
    # ------------------------------------------------------------------

    def _load_strength(self, runtime=None, force_refresh: bool = False) -> Dict[str, Any]:
        if runtime is not None and getattr(runtime, "currency_strength", None):
            return _safe_dict(runtime.currency_strength)

        if self.strength is None:
            return {}

        try:
            if hasattr(self.strength, "command_center_payload"):
                return _safe_dict(
                    self.strength.command_center_payload(
                        force_refresh=force_refresh,
                    )
                )
            if hasattr(self.strength, "scan_currencies"):
                return _safe_dict(
                    self.strength.scan_currencies(
                        force_refresh=force_refresh,
                    )
                )
            if hasattr(self.strength, "analyze"):
                return _safe_dict(
                    self.strength.analyze(
                        force_refresh=force_refresh,
                    )
                )
        except Exception as exc:
            return {"status": "WARNING", "error": str(exc)}

        return {}

    def _load_alpha(self, runtime=None, force_refresh: bool = False) -> Dict[str, Any]:
        if runtime is not None and getattr(runtime, "alpha", None):
            return _safe_dict(runtime.alpha)

        if self.alpha is None:
            return {}

        try:
            # Backward compatibility only. When runtime is passed, this path
            # should not execute.
            if hasattr(self.alpha, "command_center_payload"):
                return _safe_dict(
                    self.alpha.command_center_payload(
                        force_refresh=force_refresh,
                    )
                )
            if hasattr(self.alpha, "run_alpha_model"):
                return _safe_dict(
                    self.alpha.run_alpha_model(
                        force_refresh=force_refresh,
                    )
                )
        except Exception as exc:
            return {"status": "WARNING", "error": str(exc)}

        return {}

    def _load_regime(self, runtime=None, force_refresh: bool = False) -> Dict[str, Any]:
        if runtime is not None and getattr(runtime, "macro", None):
            return _safe_dict(runtime.macro)

        if self.regime is None:
            return {}

        try:
            return _safe_dict(
                self.regime.analyze(
                    force_refresh=force_refresh,
                )
            )
        except Exception as exc:
            return {"status": "WARNING", "error": str(exc)}

    def _load_institutional(
        self,
        runtime=None,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        if runtime is not None and getattr(runtime, "institutional", None):
            return _safe_dict(runtime.institutional)

        if self.inst is None:
            return {}

        try:
            try:
                return _safe_dict(
                    self.inst.scan(
                        runtime=runtime,
                        force_refresh=force_refresh,
                    )
                )
            except TypeError:
                return _safe_dict(
                    self.inst.scan(
                        force_refresh=force_refresh,
                    )
                )
        except Exception as exc:
            return {"status": "WARNING", "error": str(exc)}

    def _load_sentiment(
        self,
        runtime=None,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        if runtime is not None and getattr(runtime, "sentiment", None):
            return _safe_dict(runtime.sentiment)

        if self.sent is None:
            return {}

        try:
            try:
                return _safe_dict(
                    self.sent.analyze(
                        runtime=runtime,
                        force_refresh=force_refresh,
                    )
                )
            except TypeError:
                return _safe_dict(
                    self.sent.analyze(
                        force_refresh=force_refresh,
                    )
                )
        except Exception as exc:
            return {"status": "WARNING", "error": str(exc)}

    def _load_carry(
            self,
            runtime=None,
            force_refresh=False,
    ):
        if runtime is not None and getattr(runtime, "carry", None):
            return _safe_dict(runtime.carry)
        if self.carry is None:
            return {}

        try:
            return _safe_dict(
                self.carry.analyze(
                    force_refresh=force_refresh,
                )
            )
        except TypeError:
            try:
                return _safe_dict(self.carry.analyze())
            except Exception as exc:
                return {"status": "WARNING", "error": str(exc)}
        except Exception as exc:
            return {"status": "WARNING", "error": str(exc)}

    def _load_central_banks(
            self,
            runtime=None,
    ):
        if runtime is not None and getattr(runtime, "central_banks", None):
            return _safe_dict(runtime.central_banks)
        if self.cb is None:
            return {}

        try:
            return _safe_dict(self.cb.analyze())
        except Exception as exc:
            return {"status": "WARNING", "error": str(exc)}

    # ------------------------------------------------------------------
    # Payload normalization
    # ------------------------------------------------------------------

    def _top_opportunities(self, alpha: Dict[str, Any]) -> list:
        opportunities = alpha.get("top_opportunities")
        if isinstance(opportunities, list):
            return opportunities

        signals = alpha.get("signals")
        if isinstance(signals, list):
            return signals[:8]

        return []

    def _best_trade(self, alpha: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        best = alpha.get("best_trade") or alpha.get("top_signal")
        if isinstance(best, dict):
            return best

        opportunities = self._top_opportunities(alpha)
        if opportunities and isinstance(opportunities[0], dict):
            return opportunities[0]

        return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @profile_alpha_execution("ForexCommandCenter.build")
    def build(
        self,
        runtime=None,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        #
        # Ensure a shared runtime exists.
        #
        if runtime is None:
            runtime = build_forex_runtime_context(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                portfolio_id=self.portfolio_id,
                force_refresh=force_refresh,
                db=self.db,
            )
            print("=" * 80)
            print("FOREX RUNTIME IDENTITY")
            print("Tenant   :", runtime.tenant_id)
            print("User     :", runtime.user_id)
            print("Portfolio:", runtime.portfolio_id)
            print("Runtime  :", runtime.metadata.get("runtime_id"))
            print("=" * 80)
        strength = self._load_strength(
            runtime=runtime,
            force_refresh=force_refresh,
        )
        alpha = self._load_alpha(
            runtime=runtime,
            force_refresh=force_refresh,
        )
        regime = self._load_regime(
            runtime=runtime,
            force_refresh=force_refresh,
        )
        carry = self._load_carry(
            runtime=runtime,
            force_refresh=force_refresh,
        )

        inst = self._load_institutional(
            runtime=runtime,
            force_refresh=force_refresh,
        )
        cb = self._load_central_banks(
            runtime=runtime,
        )
        sent = self._load_sentiment(
            runtime=runtime,
            force_refresh=force_refresh,
        )

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),

            "market_regime": regime,

            "currency_strength": strength.get("currency_strength", []),

            "top_opportunities": self._top_opportunities(alpha),

            "best_trade": self._best_trade(alpha),

            "institutional_flow": inst.get("top_institutional_trades", []),

            "carry_trades": carry.get("top_carry_trades", []),

            "central_banks": cb.get("central_banks", []),

            "sentiment": sent.get("pair_sentiment", []),

            "summary": {
                "strongest_currency": strength.get("strongest_currency"),
                "weakest_currency": strength.get("weakest_currency"),
                "macro_regime": regime.get("macro_regime"),
                "macro_score": regime.get("macro_score"),
                "overall_sentiment": sent.get("overall_sentiment"),
            },

            # Sprint 25 runtime diagnostics
            "runtime": _runtime_summary(runtime),
            "runtime_source": "shared" if runtime is not None else "local",
            "used_shared_runtime": runtime is not None,
        }


_ENGINE = None


def get_forex_command_center_engine():
    global _ENGINE

    if _ENGINE is None:
        _ENGINE = ForexCommandCenterEngine()

    return _ENGINE
