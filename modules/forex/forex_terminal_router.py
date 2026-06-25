from datetime import datetime, timezone

from modules.forex.forex_terminal_controller import get_forex_terminal_controller

class ForexTerminalRouter:
    def __init__(self, db=None):
        self.controller=get_forex_terminal_controller(db=db)

    def route(self, action:str, **kwargs):
        action=(action or '').lower()

        if action=='dashboard':
            return self.controller.dashboard(**kwargs)
        if action=='refresh':
            return self.controller.refresh()
        if action=='submit_order':
            return self.controller.submit_order(**kwargs)
        if action=='execute_recommendation':
            rec=kwargs.pop('recommendation')
            return self.controller.execute_recommendation(rec, **kwargs)
        if action=='cancel_order':
            return self.controller.cancel_order(kwargs.get('broker_order_id'))
        if action=='emergency_stop':
            return self.controller.emergency_stop()

        return {
            'status':'unknown_action',
            'action':action,
            'timestamp':datetime.now(timezone.utc).isoformat()
        }

_ROUTER=None
def get_forex_terminal_router(db=None):
    global _ROUTER
    if _ROUTER is None:
        _ROUTER=ForexTerminalRouter(db=db)
    return _ROUTER
