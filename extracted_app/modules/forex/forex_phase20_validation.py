"""
modules/forex/forex_phase20_validation.py

Phase 20I — Validation helper.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any, Dict, Optional


PHASE20_REQUIRED_MODULES = [
    "modules.forex.forex_autonomous_strategy_orchestrator",
    "modules.forex.forex_strategy_scheduler",
    "modules.forex.forex_strategy_selector",
    "modules.forex.forex_strategy_allocator",
    "modules.forex.forex_learning_engine",
    "modules.forex.forex_trade_feedback_engine",
    "modules.forex.forex_model_evaluator",
    "modules.forex.forex_parameter_optimizer",
    "modules.forex.forex_execution_supervisor",
    "modules.forex.forex_execution_optimizer",
    "modules.forex.forex_execution_quality_engine",
    "modules.forex.forex_slippage_analyzer",
    "modules.forex.forex_dynamic_allocation_engine",
    "modules.forex.forex_rebalancing_engine",
    "modules.forex.forex_capital_allocator",
    "modules.forex.forex_strategy_rotation_engine",
    "modules.forex.forex_performance_attribution_v2",
    "modules.forex.forex_benchmark_engine",
    "modules.forex.forex_strategy_scorecard",
    "modules.forex.forex_manager_dashboard",
    "modules.forex.forex_enterprise_operations_center_v2",
    "modules.forex.forex_system_health_dashboard",
    "modules.forex.forex_cluster_monitor",
    "modules.forex.forex_service_registry",
    "modules.forex.forex_autonomous_command_center",
    "modules.forex.forex_autonomous_platform_dashboard",
]


def validate_phase20_autonomous_platform(db=None, snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    results = []
    artifacts = {}
    snapshot = snapshot or {}

    def add(test, passed, details=""):
        results.append({
            "Category": "Phase 20",
            "Test": test,
            "Passed": bool(passed),
            "Severity": "required",
            "Details": details,
        })

    for module in PHASE20_REQUIRED_MODULES:
        try:
            import_module(module)
            add(f"Import {module}", True, "import ok")
        except Exception as exc:
            add(f"Import {module}", False, str(exc))

    try:
        from modules.forex.forex_autonomous_command_center import get_forex_autonomous_command_center
        payload = get_forex_autonomous_command_center(db=db).dashboard(snapshot=snapshot)
        artifacts["phase20_autonomous_command_center"] = payload
        add("Autonomous command center payload", isinstance(payload, dict) and payload.get("status") == "READY", str(payload.get("status")))

        required = [
            "executive_decision_center",
            "autonomous_strategies",
            "learning_engine",
            "portfolio_manager",
            "execution_intelligence",
            "performance_analytics",
            "enterprise_operations",
        ]
        for key in required:
            add(f"autonomous.{key}", key in payload, "present" if key in payload else "missing")

        add("Live execution safety", payload.get("live_execution_enabled") is False, str(payload.get("live_execution_enabled")))
    except Exception as exc:
        add("Autonomous command center validation", False, str(exc))

    return {
        "status": "PASS" if all(r["Passed"] for r in results if r["Severity"] == "required") else "FAIL",
        "results": results,
        "artifacts": artifacts,
    }
