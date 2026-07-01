"""
modules/forex/forex_carry_trade_engine.py
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict,List

try:
    from modules.forex.forex_price_service import get_forex_price_service
except Exception:
    get_forex_price_service=None

POLICY_RATE_PROXY={
    "NZD":5.50,
    "USD":5.25,
    "GBP":5.00,
    "CAD":4.75,
    "AUD":4.35,
    "EUR":3.75,
    "CHF":1.50,
    "JPY":0.25,
}

PAIRS=[
    "EUR/USD","GBP/USD","AUD/USD","NZD/USD",
    "USD/JPY","USD/CHF","USD/CAD",
    "EUR/JPY","GBP/JPY","AUD/JPY","CAD/JPY","NZD/JPY"
]

def _split(pair):
    p=pair.replace("-","/").replace("_","/").upper()
    if "/" in p:
        return p.split("/",1)
    return p[:3],p[3:6]

class ForexCarryTradeEngine:
    def __init__(self):
        self.price_service=get_forex_price_service() if get_forex_price_service else None

    def analyze(
            self,
            pairs=None,
            runtime=None,
            force_refresh=False,
    ):
        pairs = pairs or PAIRS

        if (
                runtime is not None
                and hasattr(runtime, "quotes")
                and isinstance(runtime.quotes, dict)
                and runtime.quotes
        ):
            quotes = runtime.quotes

            print("=" * 80)
            print("CARRY QUOTE SOURCE")
            print("runtime")
            print("=" * 80)
            print("=" * 80)
            print("CARRY USING RUNTIME QUOTES")
            print("runtime id:", id(runtime))
            print("quote count:", len(quotes))
            print("=" * 80)

        elif self.price_service:
            print("=" * 80)
            print("CARRY QUOTE SOURCE")
            print("price_service")
            print("=" * 80)

            quotes = self.price_service.get_quotes(
                pairs,
                runtime=runtime,
                force_refresh=force_refresh,
            )

        else:
            quotes = {}

        rows = []
        for pair in pairs:
            b,q=_split(pair)
            carry=POLICY_RATE_PROXY.get(b,0)-POLICY_RATE_PROXY.get(q,0)
            quote=quotes.get(pair,{})
            price=quote.get("mid") or quote.get("last")
            direction="BUY" if carry>0 else "SELL"
            expected=abs(carry)*0.8
            score=min(100,50+abs(carry)*8)
            rows.append({
                "pair":pair,
                "direction":direction,
                "funding_currency":q if carry>0 else b,
                "target_currency":b if carry>0 else q,
                "carry_spread":round(carry,2),
                "expected_return":round(expected,2),
                "score":round(score,2),
                "price":price,
                "provider":quote.get("provider"),
            })

        rows.sort(key=lambda r:r["score"],reverse=True)

        return{
            "generated_at":datetime.now(timezone.utc).isoformat(),
            "highest_yield":max(POLICY_RATE_PROXY,key=POLICY_RATE_PROXY.get),
            "lowest_yield":min(POLICY_RATE_PROXY,key=POLICY_RATE_PROXY.get),
            "top_carry_trades":rows[:10],
            "all_trades":rows,
        }

_ENGINE=None
def get_forex_carry_trade_engine():
    global _ENGINE
    if _ENGINE is None:
        _ENGINE=ForexCarryTradeEngine()
    return _ENGINE
