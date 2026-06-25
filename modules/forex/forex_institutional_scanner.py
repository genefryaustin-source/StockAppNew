
"""
modules/forex/forex_institutional_scanner.py
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

class ForexInstitutionalScanner:
    def __init__(self):
        self.alpha=get_forex_alpha_model() if get_forex_alpha_model else None
        self.strength=get_forex_currency_strength_engine() if get_forex_currency_strength_engine else None

    def scan(self,force_refresh=False):
        alpha=self.alpha.run_alpha_model(force_refresh=force_refresh) if self.alpha else {"signals":[]}
        strength=self.strength.scan_currencies(force_refresh=force_refresh) if self.strength else {}

        flows=[]
        for s in alpha.get("signals",[]):
            score=float(s.get("alpha_score",0))
            conf=float(s.get("confidence_score",0))
            if score>=80:
                bias="STRONG_INSTITUTIONAL_ACCUMULATION" if "BUY" in s["direction"] else "STRONG_INSTITUTIONAL_DISTRIBUTION"
            elif score>=65:
                bias="ACCUMULATION" if "BUY" in s["direction"] else "DISTRIBUTION"
            else:
                bias="NEUTRAL"

            flows.append({
                "pair":s["pair"],
                "institutional_bias":bias,
                "smart_money_score":round(score,2),
                "confidence":round(conf,2),
                "direction":s["direction"],
                "alpha_score":score,
                "recommendation":s["recommendation"],
                "provider":s.get("provider"),
            })

        flows.sort(key=lambda x:(x["smart_money_score"],x["confidence"]),reverse=True)

        return{
            "generated_at":datetime.now(timezone.utc).isoformat(),
            "market_bias":strength.get("status","UNKNOWN"),
            "strongest_currency":strength.get("strongest_currency"),
            "weakest_currency":strength.get("weakest_currency"),
            "institutional_flow":flows,
            "top_institutional_trades":flows[:10],
        }

_SCANNER=None
def get_forex_institutional_scanner():
    global _SCANNER
    if _SCANNER is None:
        _SCANNER=ForexInstitutionalScanner()
    return _SCANNER
