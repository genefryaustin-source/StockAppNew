from __future__ import annotations
from typing import Any, Dict, Optional

try:
    from .forex_control_plane import ForexControlPlane
    from .forex_runtime_controller import ForexRuntimeController
    from .forex_self_diagnostic_engine import ForexSelfDiagnosticEngine
except Exception:
    from forex_control_plane import ForexControlPlane
    from forex_runtime_controller import ForexRuntimeController
    from forex_self_diagnostic_engine import ForexSelfDiagnosticEngine


class ForexSupervisor:
    """Supervises scheduled ticks, diagnostics, and self-healing."""

    def __init__(self) -> None:
        self.control = ForexControlPlane()
        self.runtime = ForexRuntimeController()
        self.diagnostics = ForexSelfDiagnosticEngine()

    def supervise_tick(self, max_jobs: int = 10, heal_on_degraded: bool = True) -> Dict[str, Any]:
        diagnostic = self.diagnostics.run_diagnostics()
        healing = None
        if heal_on_degraded and diagnostic["health_score"] < 80:
            healing = self.control.command("heal")
        runtime = self.runtime.tick(max_jobs=max_jobs)
        optimize = self.control.command("optimize")
        return {"diagnostic": diagnostic, "healing": healing, "runtime": runtime, "optimization": optimize}
