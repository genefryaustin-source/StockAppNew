"""
modules/forex/forex_data_analytics_command_center.py

Phase 16G — Institutional data and analytics command center.
"""
from datetime import datetime, timezone
class ForexDataAnalyticsCommandCenter:
    def __init__(self, db=None): self.db=db
    def dashboard(self, snapshot=None, pair="EUR/USD"):
        from modules.forex.forex_market_data_fabric import get_forex_market_data_fabric
        from modules.forex.forex_macro_data_engine import get_forex_macro_data_engine
        from modules.forex.forex_order_flow_engine import get_forex_order_flow_engine
        from modules.forex.forex_currency_rankings import get_forex_currency_rankings
        from modules.forex.forex_relative_value_engine import get_forex_relative_value_engine
        from modules.forex.forex_currency_rotation_engine import get_forex_currency_rotation_engine
        from modules.forex.forex_cross_pair_engine import get_forex_cross_pair_engine
        from modules.forex.forex_alert_manager_v2 import get_forex_alert_manager_v2
        from modules.forex.forex_ai_research_copilot import get_forex_ai_research_copilot
        return {
            "status":"READY",
            "generated_at":datetime.now(timezone.utc).isoformat(),
            "market_data_fabric":get_forex_market_data_fabric(db=self.db).fabric_snapshot(),
            "macro_intelligence":get_forex_macro_data_engine(db=self.db).dashboard(),
            "flow_analytics":get_forex_order_flow_engine(db=self.db).flow(pair=pair),
            "currency_rankings":get_forex_currency_rankings(db=self.db).rankings(),
            "relative_value":get_forex_relative_value_engine(db=self.db).relative_value(),
            "currency_rotation":get_forex_currency_rotation_engine(db=self.db).rotation(),
            "cross_pairs":get_forex_cross_pair_engine(db=self.db).crosses(),
            "alerts":get_forex_alert_manager_v2(db=self.db).dashboard(snapshot=snapshot),
            "ai_research_copilot":get_forex_ai_research_copilot(db=self.db).dashboard(snapshot=snapshot),
        }
_ENGINE=None
def get_forex_data_analytics_command_center(db=None):
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None): _ENGINE=ForexDataAnalyticsCommandCenter(db=db)
    return _ENGINE
