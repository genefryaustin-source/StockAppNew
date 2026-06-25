from datetime import datetime, timezone

from modules.forex.forex_command_processor import get_forex_command_processor
from modules.forex.forex_runtime_manager import get_forex_runtime_manager
from modules.forex.forex_registry import get_forex_registry

class ForexControlPlane:
    def __init__(self, db=None):
        self.processor=get_forex_command_processor(db=db)
        self.runtime=get_forex_runtime_manager()
        self.registry=get_forex_registry()

    def status(self):
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "runtime": self.runtime.status(),
            "registry": self.registry.summary(),
        }

    def refresh(self):
        return self.processor.execute("refresh")

    def execute(self, command, **kwargs):
        return self.processor.execute(command, **kwargs)

    def startup(self):
        return self.runtime.start()

    def shutdown(self):
        return self.runtime.stop()

_CONTROL=None

def get_forex_control_plane(db=None):
    global _CONTROL
    if _CONTROL is None:
        _CONTROL=ForexControlPlane(db=db)
    return _CONTROL
