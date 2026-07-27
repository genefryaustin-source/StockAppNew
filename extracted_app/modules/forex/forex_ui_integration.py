
"""
modules/forex/forex_ui_integration.py

Top-level integration layer between the main StockApp UI and the Forex subsystem.
"""

from modules.forex.forex_app_adapter import get_forex_app_adapter

class ForexUIIntegration:

    def __init__(self, db=None):
        self.app = get_forex_app_adapter(db=db)

    def render(self, **kwargs):
        return self.app.render_workspace(**kwargs)

    def refresh(self):
        return self.app.refresh()

    def submit_order(self, **kwargs):
        return self.app.submit_order(**kwargs)

    def execute_recommendation(self, recommendation, **kwargs):
        return self.app.execute_recommendation(recommendation, **kwargs)

    def cancel_order(self, broker_order_id):
        return self.app.cancel_order(broker_order_id)

    def emergency_stop(self):
        return self.app.emergency_stop()


_INSTANCE = None

def get_forex_ui_integration(db=None):
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = ForexUIIntegration(db=db)
    return _INSTANCE
