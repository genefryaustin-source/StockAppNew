from __future__ import annotations
from typing import Any, Dict, Iterable, Optional

try:
    from .forex_execution_orchestrator import ForexExecutionOrchestrator
    from .forex_scheduler import ForexScheduler
    from .forex_self_diagnostic_engine import ForexSelfDiagnosticEngine
    from .forex_self_healing_engine import ForexSelfHealingEngine
    from .forex_autonomous_optimizer import ForexAutonomousOptimizer
except Exception:
    from forex_execution_orchestrator import ForexExecutionOrchestrator
    from forex_scheduler import ForexScheduler
    from forex_self_diagnostic_engine import ForexSelfDiagnosticEngine
    from forex_self_healing_engine import ForexSelfHealingEngine
    from forex_autonomous_optimizer import ForexAutonomousOptimizer


class ForexControlPlane:
    """Single API facade for Forex runtime operations."""

    def __init__(self) -> None:
        self.orchestrator = ForexExecutionOrchestrator()
        self.scheduler = ForexScheduler()
        self.diagnostics = ForexSelfDiagnosticEngine()
        self.healer = ForexSelfHealingEngine()
        self.optimizer = ForexAutonomousOptimizer()

    def command(self, action: str, **kwargs: Any) -> Dict[str, Any]:
        action = (action or "").lower().strip()
        if action in {"orchestrate", "run_cycle"}:
            return self.orchestrator.orchestrate_cycle(**kwargs)
        if action in {"schedule"}:
            jobs = self.scheduler.schedule_cycle(**kwargs)
            return {"scheduled_jobs": len(jobs), "jobs": jobs[:25]}
        if action in {"diagnose", "diagnostics"}:
            return self.diagnostics.run_diagnostics()
        if action in {"heal", "self_heal"}:
            return self.healer.heal(**kwargs)
        if action in {"optimize"}:
            return self.optimizer.optimize()
        return {"error": f"Unknown Forex control action: {action}", "supported": ["run_cycle", "schedule", "diagnostics", "heal", "optimize"]}
