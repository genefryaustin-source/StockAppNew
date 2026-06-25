"""
modules/forex/forex_sentiment_engine.py
"""

from __future__ import annotations

from datetime import datetime, timezone

try:
    from modules.forex.forex_alpha_model import get_forex_alpha_model
except Exception:
    get_forex_alpha_model=None

try:
    from modules.forex.forex_currency_strength_engine import get_forex_currency_strength_engine
except Exception:
    get_forex_currency_strength_engine=None


class ForexSentimentEngine:

    def __init__(self):
        self.alpha=get_forex_alpha_model() if get_forex_alpha_model else None
        self.strength=get_forex_currency_strength_engine() if get_forex_currency_strength_engine else None

    def analyze(self,force_refresh=False):
        alpha=self.alpha.run_alpha_model(force_refresh=force_refresh) if self.alpha else {"signals":[]}
        strength=self.strength.scan_currencies(force_refresh=force_refresh) if self.strength else {}

        rows=[]

        for signal in alpha.get("signals",[]):
            score=float(signal.get("alpha_score",0))
            confidence=float(signal.get("confidence_score",0))

            if score>=85:
                sentiment="EXTREMELY_BULLISH" if "BUY" in signal["direction"] else "EXTREMELY_BEARISH"
            elif score>=70:
                sentiment="BULLISH" if "BUY" in signal["direction"] else "BEARISH"
            else:
                sentiment="NEUTRAL"

            rows.append({
                "pair":signal["pair"],
                "market_sentiment":sentiment,
                "sentiment_score":round(score,2),
                "confidence_score":round(confidence,2),
                "direction":signal["direction"],
                "recommendation":signal["recommendation"],
                "provider":signal.get("provider"),
            })

        rows.sort(key=lambda r:(r["sentiment_score"],r["confidence_score"]),reverse=True)

        return {
            "generated_at":datetime.now(timezone.utc).isoformat(),
            "strongest_currency":strength.get("strongest_currency"),
            "weakest_currency":strength.get("weakest_currency"),
            "overall_sentiment":"BULLISH" if rows and "BUY" in rows[0]["direction"] else "BEARISH" if rows else "NEUTRAL",
            "pair_sentiment":rows,
            "top_sentiment_trades":rows[:10],
        }


_ENGINE=None

def get_forex_sentiment_engine():
    global _ENGINE
    if _ENGINE is None:
        _ENGINE=ForexSentimentEngine()
    return _ENGINE
