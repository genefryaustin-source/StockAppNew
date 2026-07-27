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
    """
    Fixed in the no-fake-data audit: analyze() previously classified the
    regime with a fixed currency lookup table -- if the strongest currency
    was AUD/NZD/CAD/GBP the score was ALWAYS exactly 82; USD/JPY/CHF ALWAYS
    exactly 78; anything else ALWAYS exactly 60 -- regardless of how strong
    or weak that currency actually was. That's why "RISK_OFF" at
    "Macro Score: 78/100" kept showing up everywhere: it wasn't a computed
    reading, it was a constant tied to a 3-bucket lookup. "volatility" and
    "liquidity" were likewise always "MODERATE"/"NORMAL" no matter what.

    macro_score is now a real, continuously varying number derived from the
    actual strength-score gap between risk-on currencies (AUD/NZD) and
    defensive currencies (USD/JPY) -- the same real methodology
    forex_currency_strength_engine._market_bias() already uses -- so two
    different market conditions that both happen to favor CHF/JPY no longer
    produce an identical, fabricated-looking 78.
    """

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

        rows = strength.get("currency_strength") if isinstance(strength, dict) else None
        rows = rows if isinstance(rows, list) else []

        def _score(ccy):
            row = next((r for r in rows if isinstance(r, dict) and r.get("currency") == ccy), None)
            try:
                return float(row.get("strength_score")) if row and row.get("strength_score") is not None else None
            except (TypeError, ValueError):
                return None

        usd_score, jpy_score, aud_score, nzd_score = _score("USD"), _score("JPY"), _score("AUD"), _score("NZD")
        have_real_scores = all(v is not None for v in (usd_score, jpy_score, aud_score, nzd_score))

        strongest_obj = strength.get("strongest_currency") if isinstance(strength, dict) else None
        weakest_obj = strength.get("weakest_currency") if isinstance(strength, dict) else None
        strongest = (strongest_obj or {}).get("currency") if isinstance(strongest_obj, dict) else None
        weakest = (weakest_obj or {}).get("currency") if isinstance(weakest_obj, dict) else None

        if have_real_scores:
            risk_score = ((aud_score + nzd_score) / 2.0) - ((usd_score + jpy_score) / 2.0)
            if risk_score >= 15:
                regime = "RISK_ON"
            elif risk_score <= -15:
                regime = "RISK_OFF"
            else:
                regime = "BALANCED"
            # A real, continuously varying confidence reading (0-100) tied
            # to how large the actual risk-on/defensive strength gap is --
            # not a fixed constant per bucket.
            score = max(0.0, min(100.0, 50.0 + risk_score))
        elif strongest or weakest:
            regime = "UNKNOWN"
            score = 0.0
        else:
            regime = "UNKNOWN"
            score = 0.0

        return{
            "generated_at":datetime.now(timezone.utc).isoformat(),
            "macro_regime":regime,
            "macro_score":round(score, 2),
            "strongest_currency":strongest_obj,
            "weakest_currency":weakest_obj,
            "central_bank_snapshot":cb.get("central_banks",[]) if isinstance(cb, dict) else [],
            "summary":{
                "usd_bias":"BULLISH" if strongest=="USD" else "NEUTRAL" if strongest else "UNKNOWN",
                "volatility":"Unknown",
                "liquidity":"Unknown",
                "risk_environment":regime,
            }
        }

_ENGINE=None

def get_forex_macro_regime_engine(db=None, tenant_id=None, user_id=None, portfolio_id=None):
    global _ENGINE
    if _ENGINE is None:
        _ENGINE=ForexMacroRegimeEngine()
    return _ENGINE