"""
modules/forex/forex_macro_regime_engine.py
"""

from __future__ import annotations
from datetime import datetime, timezone

try:
    from modules.forex.forex_currency_strength_engine import get_forex_currency_strength_engine
except Exception:
    get_forex_currency_strength_engine=None

try:
    from modules.forex.forex_central_bank_engine import get_forex_central_bank_engine
except Exception:
    get_forex_central_bank_engine=None

class ForexMacroRegimeEngine:

    def __init__(self):
        self.strength=get_forex_currency_strength_engine() if get_forex_currency_strength_engine else None
        self.cb=get_forex_central_bank_engine() if get_forex_central_bank_engine else None

    def analyze(
            self,
            runtime=None,
            force_refresh=False,
    ):
        if (
                runtime is not None
                and isinstance(runtime.currency_strength, dict)
        ):

            strength = runtime.currency_strength

            print("=" * 80)
            print("MACRO REGIME USING RUNTIME STRENGTH")
            print("runtime id :", id(runtime))
            print("strength source : runtime")
            print("=" * 80)

        elif self.strength:

            strength = self.strength.scan_currencies(
                force_refresh=force_refresh,
            )

        else:

            strength = {}
        cb=self.cb.analyze() if self.cb else {}

        strongest=(strength.get("strongest_currency") or {}).get("currency","USD")
        weakest=(strength.get("weakest_currency") or {}).get("currency","JPY")

        risk_on={"AUD","NZD","CAD","GBP"}
        defensive={"USD","JPY","CHF"}

        if strongest in risk_on:
            regime="RISK_ON"
            score=82
        elif strongest in defensive:
            regime="RISK_OFF"
            score=78
        else:
            regime="BALANCED"
            score=60

        return{
            "generated_at":datetime.now(timezone.utc).isoformat(),
            "macro_regime":regime,
            "macro_score":score,
            "strongest_currency":strength.get("strongest_currency"),
            "weakest_currency":strength.get("weakest_currency"),
            "central_bank_snapshot":cb.get("central_banks",[]),
            "summary":{
                "usd_bias":"BULLISH" if strongest=="USD" else "NEUTRAL",
                "volatility":"MODERATE",
                "liquidity":"NORMAL",
                "risk_environment":regime,
            }
        }

_ENGINE=None

def get_forex_macro_regime_engine():
    global _ENGINE
    if _ENGINE is None:
        _ENGINE=ForexMacroRegimeEngine()
    return _ENGINE
