from datetime import datetime, timezone

from modules.forex.forex_alpha_model import get_forex_alpha_model
from modules.forex.forex_macro_regime_engine import get_forex_macro_regime_engine
from modules.forex.forex_sentiment_engine import get_forex_sentiment_engine
from modules.forex.forex_trade_execution_engine import get_forex_trade_execution_engine

class ForexStrategyEngine:
    def __init__(self,db=None):
        self.alpha=get_forex_alpha_model(); self.regime=get_forex_macro_regime_engine(); self.sentiment=get_forex_sentiment_engine(); self.execution=get_forex_trade_execution_engine(db=db)
    def generate_trade_plan(self,force_refresh=False):
        a=self.alpha.run_alpha_model(force_refresh=force_refresh); r=self.regime.analyze(force_refresh=force_refresh); s=self.sentiment.analyze(force_refresh=force_refresh); return {"generated_at":datetime.now(timezone.utc).isoformat(),"macro_regime":r.get("macro_regime"),"signals":a.get("signals",[]),"top_trades":a.get("top_opportunities",a.get("signals",[])[:10]),"sentiment":s.get("overall_sentiment")}
    def execute_top_trade(self,portfolio_id=None,user_id=None,tenant_id=None):
        p=self.generate_trade_plan(); t=p.get("top_trades",[]); return {"status":"no_trades"} if not t else self.execution.execute_recommendation(t[0],portfolio_id=portfolio_id,user_id=user_id,tenant_id=tenant_id)
_ENGINE=None
def get_forex_strategy_engine(db=None):
 global _ENGINE
 if _ENGINE is None: _ENGINE=ForexStrategyEngine(db=db)
 return _ENGINE
