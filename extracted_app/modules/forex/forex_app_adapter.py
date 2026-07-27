
"""
modules/forex/forex_app_adapter.py

Application integration adapter for the Forex subsystem.
"""

from modules.forex.forex_streamlit_adapter import get_forex_streamlit_adapter

class ForexAppAdapter:
    def __init__(self, db=None):
        self.adapter = get_forex_streamlit_adapter(db=db)

    def render_workspace(self, **kwargs):
        return self.adapter.load_dashboard(**kwargs)

    def refresh(self):
        return self.adapter.refresh()

    def submit_order(self, **kwargs):
        return self.adapter.submit_order(**kwargs)

    def execute_recommendation(self, recommendation, **kwargs):
        return self.adapter.execute_recommendation(recommendation, **kwargs)

    def cancel_order(self, broker_order_id):
        return self.adapter.cancel_order(broker_order_id)

    def emergency_stop(self):
        return self.adapter.emergency_stop()

_APP=None

def get_forex_app_adapter(db=None):
    global _APP
    if _APP is None:
        _APP = ForexAppAdapter(db=db)
    return _APP
