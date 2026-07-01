"""
modules/forex/forex_sentiment_engine.py

Sprint 25 runtime-aware Forex sentiment engine.
Uses runtime.alpha and runtime.currency_strength when available to prevent
duplicate Alpha executions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from modules.forex.forex_alpha_execution_profiler import (
    profile_alpha_execution,
)

try:
    from modules.forex.forex_alpha_model import get_forex_alpha_model
except Exception:
    get_forex_alpha_model = None

try:
    from modules.forex.forex_currency_strength_engine import (
        get_forex_currency_strength_engine,
    )
except Exception:
    get_forex_currency_strength_engine = None


class ForexSentimentEngine:
    def __init__(self):
        self.alpha = get_forex_alpha_model() if get_forex_alpha_model else None
        self.strength = (
            get_forex_currency_strength_engine()
            if get_forex_currency_strength_engine
            else None
        )

    @profile_alpha_execution("ForexSentimentEngine.analyze")
    def analyze(
        self,
        runtime: Optional[Any] = None,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        alpha = self._load_alpha(runtime=runtime, force_refresh=force_refresh)
        strength = self._load_strength(runtime=runtime, force_refresh=force_refresh)

        rows = []

        signals = alpha.get("signals", []) if isinstance(alpha, dict) else []
        if not isinstance(signals, list):
            signals = []

        for signal in signals:
            if not isinstance(signal, dict):
                continue

            score = float(signal.get("alpha_score", 0) or 0)
            confidence = float(signal.get("confidence_score", 0) or 0)
            direction = str(signal.get("direction", "")).upper()
            recommendation = str(signal.get("recommendation", "")).upper()

            directional_text = f"{direction} {recommendation}"

            if score >= 85:
                sentiment = (
                    "EXTREMELY_BULLISH"
                    if any(x in directional_text for x in ("BUY", "LONG", "BULL"))
                    else "EXTREMELY_BEARISH"
                )
            elif score >= 70:
                sentiment = (
                    "BULLISH"
                    if any(x in directional_text for x in ("BUY", "LONG", "BULL"))
                    else "BEARISH"
                )
            else:
                sentiment = "NEUTRAL"

            rows.append(
                {
                    "pair": signal.get("pair") or signal.get("symbol"),
                    "market_sentiment": sentiment,
                    "sentiment_score": round(score, 2),
                    "confidence_score": round(confidence, 2),
                    "direction": direction or recommendation or "NEUTRAL",
                    "recommendation": signal.get("recommendation"),
                    "provider": signal.get("provider"),
                    "source": (
                        "runtime_alpha"
                        if runtime is not None and getattr(runtime, "alpha", None)
                        else signal.get("source", "local_alpha")
                    ),
                }
            )

        rows.sort(
            key=lambda row: (
                float(row.get("sentiment_score", 0)),
                float(row.get("confidence_score", 0)),
            ),
            reverse=True,
        )

        overall_sentiment = "NEUTRAL"
        if rows:
            top_direction = str(rows[0].get("direction", "")).upper()
            if any(x in top_direction for x in ("BUY", "LONG", "BULL")):
                overall_sentiment = "BULLISH"
            elif any(x in top_direction for x in ("SELL", "SHORT", "BEAR")):
                overall_sentiment = "BEARISH"

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "READY",
            "strongest_currency": (
                strength.get("strongest_currency")
                if isinstance(strength, dict)
                else None
            ),
            "weakest_currency": (
                strength.get("weakest_currency")
                if isinstance(strength, dict)
                else None
            ),
            "overall_sentiment": overall_sentiment,
            "pair_sentiment": rows,
            "top_sentiment_trades": rows[:10],
            "runtime_source": "shared" if runtime is not None else "local",
            "used_shared_runtime": bool(
                runtime is not None and getattr(runtime, "alpha", None)
            ),
        }

    def _load_alpha(
        self,
        runtime: Optional[Any] = None,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        print("=" * 80)
        print("SENTIMENT _load_alpha")
        print("runtime id :", id(runtime) if runtime else None)
        print("alpha id   :", id(runtime.alpha) if runtime and runtime.alpha else None)
        print("alpha none :", runtime.alpha is None if runtime else None)
        print("=" * 80)

        if runtime is None:
            print("runtime is None")
        else:
            print("runtime.alpha exists :", hasattr(runtime, "alpha"))
            print("runtime.alpha is None:", runtime.alpha is None)

        print("=" * 80)
        if runtime is not None and getattr(runtime, "alpha", None):
            return runtime.alpha

        if self.alpha is None:
            return {"signals": []}

        try:
            if runtime and runtime.alpha:
                alpha = runtime.alpha
            else:
                alpha = self.alpha.run_alpha_model(force_refresh=force_refresh)
        except Exception as exc:
            return {"signals": [], "error": str(exc)}
        return alpha
    def _load_strength(
        self,
        runtime: Optional[Any] = None,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        if runtime is not None and getattr(runtime, "currency_strength", None):
            return runtime.currency_strength

        if self.strength is None:
            return {}

        try:
            if hasattr(self.strength, "scan_currencies"):
                return self.strength.scan_currencies(force_refresh=force_refresh)
            if hasattr(self.strength, "command_center_payload"):
                return self.strength.command_center_payload(
                    force_refresh=force_refresh
                )
            if hasattr(self.strength, "analyze"):
                return self.strength.analyze(force_refresh=force_refresh)
        except Exception as exc:
            return {"status": "WARNING", "error": str(exc)}

        return {}


_ENGINE = None


def get_forex_sentiment_engine():
    global _ENGINE

    if _ENGINE is None:
        _ENGINE = ForexSentimentEngine()

    return _ENGINE
