
from modules.forex.forex_terminal_bridge import get_forex_terminal_bridge

class ForexStreamlitAdapter:
    """Thin adapter between Streamlit pages and the Forex backend."""

    def __init__(self, db=None):
        self.bridge = get_forex_terminal_bridge(db=db)

    def load_dashboard(self, **kwargs):
        return self.bridge.dashboard(**kwargs)

    def refresh(self):
        return self.bridge.refresh()

    def submit_order(self, **kwargs):
        return self.bridge.submit_order(**kwargs)

    def execute_recommendation(self, recommendation, **kwargs):
        return self.bridge.execute_recommendation(recommendation, **kwargs)

    def cancel_order(self, broker_order_id):
        return self.bridge.cancel_order(broker_order_id)

    def emergency_stop(self):
        return self.bridge.emergency_stop()

_ADAPTER = None

def get_forex_streamlit_adapter(db=None):
    global _ADAPTER
    if _ADAPTER is None:
        _ADAPTER = ForexStreamlitAdapter(db=db)
    return _ADAPTER
