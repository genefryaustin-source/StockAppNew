from datetime import datetime, timezone

from modules.forex.forex_terminal_router import get_forex_terminal_router

class ForexTerminalBridge:
    """Bridge between the application UI and the Forex terminal backend."""

    def __init__(self, db=None):
        self.router = get_forex_terminal_router(db=db)

    def dashboard(self, **kwargs):
        return self.router.route('dashboard', **kwargs)

    def refresh(self):
        return self.router.route('refresh')

    def submit_order(self, **kwargs):
        return self.router.route('submit_order', **kwargs)

    def execute_recommendation(self, recommendation, **kwargs):
        kwargs['recommendation'] = recommendation
        return self.router.route('execute_recommendation', **kwargs)

    def cancel_order(self, broker_order_id):
        return self.router.route('cancel_order', broker_order_id=broker_order_id)

    def emergency_stop(self):
        return self.router.route('emergency_stop')

    def heartbeat(self):
        return {
            'status':'online',
            'timestamp':datetime.now(timezone.utc).isoformat()
        }

_BRIDGE=None

def get_forex_terminal_bridge(db=None):
    global _BRIDGE
    if _BRIDGE is None:
        _BRIDGE = ForexTerminalBridge(db=db)
    return _BRIDGE
