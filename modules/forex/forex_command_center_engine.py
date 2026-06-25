"""
modules/forex/forex_command_center_engine.py
"""

from __future__ import annotations
from datetime import datetime, timezone

try:
    from modules.forex.forex_currency_strength_engine import get_forex_currency_strength_engine
except Exception:
    get_forex_currency_strength_engine=None
try:
    from modules.forex.forex_alpha_model import get_forex_alpha_model
except Exception:
    get_forex_alpha_model=None
try:
    from modules.forex.forex_macro_regime_engine import get_forex_macro_regime_engine
except Exception:
    get_forex_macro_regime_engine=None
try:
    from modules.forex.forex_carry_trade_engine import get_forex_carry_trade_engine
except Exception:
    get_forex_carry_trade_engine=None
try:
    from modules.forex.forex_institutional_scanner import get_forex_institutional_scanner
except Exception:
    get_forex_institutional_scanner=None
try:
    from modules.forex.forex_central_bank_engine import get_forex_central_bank_engine
except Exception:
    get_forex_central_bank_engine=None
try:
    from modules.forex.forex_sentiment_engine import get_forex_sentiment_engine
except Exception:
    get_forex_sentiment_engine=None

class ForexCommandCenterEngine:

    def __init__(self):
        self.strength=get_forex_currency_strength_engine() if get_forex_currency_strength_engine else None
        self.alpha=get_forex_alpha_model() if get_forex_alpha_model else None
        self.regime=get_forex_macro_regime_engine() if get_forex_macro_regime_engine else None
        self.carry=get_forex_carry_trade_engine() if get_forex_carry_trade_engine else None
        self.inst=get_forex_institutional_scanner() if get_forex_institutional_scanner else None
        self.cb=get_forex_central_bank_engine() if get_forex_central_bank_engine else None
        self.sent=get_forex_sentiment_engine() if get_forex_sentiment_engine else None

    def build(self,force_refresh=False):
        strength=self.strength.command_center_payload(force_refresh=force_refresh) if self.strength else {}
        alpha=self.alpha.command_center_payload(force_refresh=force_refresh) if self.alpha else {}
        regime=self.regime.analyze(force_refresh=force_refresh) if self.regime else {}
        carry=self.carry.analyze(force_refresh=force_refresh) if self.carry else {}
        inst=self.inst.scan(force_refresh=force_refresh) if self.inst else {}
        cb=self.cb.analyze() if self.cb else {}
        sent=self.sent.analyze(force_refresh=force_refresh) if self.sent else {}

        return {
            "generated_at":datetime.now(timezone.utc).isoformat(),
            "market_regime":regime,
            "currency_strength":strength.get("currency_strength",[]),
            "top_opportunities":alpha.get("top_opportunities",[]),
            "best_trade":alpha.get("best_trade"),
            "institutional_flow":inst.get("top_institutional_trades",[]),
            "carry_trades":carry.get("top_carry_trades",[]),
            "central_banks":cb.get("central_banks",[]),
            "sentiment":sent.get("pair_sentiment",[]),
            "summary":{
                "strongest_currency":strength.get("strongest_currency"),
                "weakest_currency":strength.get("weakest_currency"),
                "macro_regime":regime.get("macro_regime"),
                "macro_score":regime.get("macro_score"),
            }
        }

_ENGINE=None
def get_forex_command_center_engine():
    global _ENGINE
    if _ENGINE is None:
        _ENGINE=ForexCommandCenterEngine()
    return _ENGINE
