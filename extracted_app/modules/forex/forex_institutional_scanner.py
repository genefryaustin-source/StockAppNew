"""
modules/forex/forex_institutional_scanner.py

Institutional scanner for Forex alpha and smart-money signals.

Sprint 25:
    Runtime-aware implementation. Uses runtime.alpha and
    runtime.currency_strength when available to avoid duplicate Alpha scans.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from modules.forex.forex_alpha_execution_profiler import (
    profile_alpha_execution,
)


class ForexInstitutionalScanner:
    def __init__(self):
        self.alpha = self._safe_alpha()
        self.strength = self._safe_strength()

    def _safe_alpha(self):
        try:
            from modules.forex.forex_alpha_model import get_forex_alpha_model

            return get_forex_alpha_model()
        except Exception:
            return None

    def _safe_strength(self):
        try:
            from modules.forex.forex_currency_strength_engine import (
                get_forex_currency_strength_engine,
            )

            return get_forex_currency_strength_engine()
        except Exception:
            return None

    @profile_alpha_execution("ForexInstitutionalScanner.scan")
    def scan(
        self,
        runtime: Optional[Any] = None,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        alpha = self._run_alpha(runtime=runtime, force_refresh=force_refresh)
        strength = self._run_strength(runtime=runtime, force_refresh=force_refresh)

        signals = alpha.get("signals", []) if isinstance(alpha, dict) else []
        flows: List[Dict[str, Any]] = []

        for signal in signals:
            if not isinstance(signal, dict):
                continue

            score = float(
                signal.get("alpha_score", signal.get("conviction_score", 0)) or 0
            )
            conf = float(
                signal.get("confidence_score", signal.get("confidence", 0)) or 0
            )
            direction = str(
                signal.get("direction", signal.get("recommendation", "NEUTRAL"))
            ).upper()

            if score >= 80:
                bias = (
                    "STRONG_INSTITUTIONAL_ACCUMULATION"
                    if any(x in direction for x in ("BUY", "LONG", "BULL"))
                    else "STRONG_INSTITUTIONAL_DISTRIBUTION"
                )
            elif score >= 65:
                bias = (
                    "ACCUMULATION"
                    if any(x in direction for x in ("BUY", "LONG", "BULL"))
                    else "DISTRIBUTION"
                )
            else:
                bias = "NEUTRAL"

            flows.append(
                {
                    "pair": self._normalize_pair(
                        signal.get("pair", signal.get("symbol", "-"))
                    ),
                    "institutional_bias": bias,
                    "smart_money_score": round(score, 2),
                    "confidence": round(conf, 2),
                    "direction": direction,
                    "alpha_score": score,
                    "recommendation": signal.get("recommendation", direction),
                    "provider": signal.get("provider"),
                    "source": (
                        "runtime_alpha"
                        if runtime is not None and getattr(runtime, "alpha", None)
                        else signal.get("source", "local_alpha")
                    ),
                }
            )

        # No hardcoded fallback: an empty institutional_flow/top_institutional_trades
        # list is an honest "nothing live to report" rather than the fixed
        # EUR/USD 92% / USD/JPY 88% / AUD/USD 84% (SELL) / GBP/USD 78%
        # sample that used to render whenever the alpha model returned no
        # signals.

        flows.sort(
            key=lambda row: (
                float(row.get("smart_money_score", 0)),
                float(row.get("confidence", 0)),
            ),
            reverse=True,
        )

        strongest = (
            strength.get("strongest_currency")
            if isinstance(strength, dict)
            else None
        )
        weakest = (
            strength.get("weakest_currency")
            if isinstance(strength, dict)
            else None
        )

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "READY" if flows else "NO_DATA",
            "market_bias": (
                strength.get("status", "READY") if isinstance(strength, dict) else "READY"
            ),
            "strongest_currency": strongest or "N/A",
            "weakest_currency": weakest or "N/A",
            "institutional_flow": flows,
            "top_institutional_trades": flows[:10],
            "runtime_source": "shared" if runtime is not None else "local",
            "used_shared_runtime": bool(
                runtime is not None and getattr(runtime, "alpha", None)
            ),
        }

    def _run_alpha(
        self,
        runtime: Optional[Any] = None,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        if runtime is not None and getattr(runtime, "alpha", None):
            return runtime.alpha

        if self.alpha is None:
            return {"signals": []}

        try:
            if hasattr(self.alpha, "run_alpha_model"):
                return self.alpha.run_alpha_model(force_refresh=force_refresh)
            if hasattr(self.alpha, "command_center_payload"):
                return self.alpha.command_center_payload(force_refresh=force_refresh)
        except Exception as exc:
            return {"signals": [], "error": str(exc)}

        return {"signals": []}

    def _run_strength(
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

    def _normalize_pair(self, pair: Any) -> str:
        value = str(pair or "-").replace("_", "/").replace("-", "/").upper()
        if "/" not in value and len(value) == 6:
            value = value[:3] + "/" + value[3:]
        return value


_SCANNER = None


def get_forex_institutional_scanner():
    global _SCANNER

    if _SCANNER is None:
        _SCANNER = ForexInstitutionalScanner()

    return _SCANNER