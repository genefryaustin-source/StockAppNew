"""
modules/forex/forex_central_bank_engine.py
"""

from __future__ import annotations
from datetime import datetime, timezone

BANKS={
    "FED":{"currency":"USD","rate":5.25},
    "ECB":{"currency":"EUR","rate":3.75},
    "BOE":{"currency":"GBP","rate":5.00},
    "BOJ":{"currency":"JPY","rate":0.25},
    "SNB":{"currency":"CHF","rate":1.50},
    "RBA":{"currency":"AUD","rate":4.35},
    "BOC":{"currency":"CAD","rate":4.75},
    "RBNZ":{"currency":"NZD","rate":5.50},
}

class ForexCentralBankEngine:

    def analyze(self):
        rows=[]
        for bank,data in BANKS.items():
            rate=data["rate"]
            if rate>=5:
                stance="HAWKISH"
                score=90
            elif rate>=4:
                stance="MODERATELY_HAWKISH"
                score=75
            elif rate>=2:
                stance="NEUTRAL"
                score=55
            else:
                stance="DOVISH"
                score=35

            rows.append({
                "central_bank":bank,
                "currency":data["currency"],
                "policy_rate":rate,
                "policy_bias":stance,
                "hawkish_score":score,
                "currency_bias":"BULLISH" if score>=70 else "BEARISH" if score<45 else "NEUTRAL",
            })

        rows.sort(key=lambda r:r["hawkish_score"],reverse=True)

        return{
            "generated_at":datetime.now(timezone.utc).isoformat(),
            "central_banks":rows,
            "most_hawkish":rows[0],
            "most_dovish":rows[-1],
        }

_ENGINE=None

def get_forex_central_bank_engine():
    global _ENGINE
    if _ENGINE is None:
        _ENGINE=ForexCentralBankEngine()
    return _ENGINE
