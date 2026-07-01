from __future__ import annotations

import importlib
import traceback

MODULES = [
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
    "modules.forex.forex_phase20_validation",
]


def main() -> int:
    failed = 0
    for module in MODULES:
        try:
            importlib.import_module(module)
            print("PASS", module)
        except Exception:
            failed += 1
            print("FAIL", module)
            traceback.print_exc()
    if failed:
        return 1

    try:
        from modules.forex.forex_autonomous_command_center import get_forex_autonomous_command_center
        payload = get_forex_autonomous_command_center().dashboard(snapshot={})
        required = [
            "executive_decision_center", "autonomous_strategies", "learning_engine",
            "portfolio_manager", "execution_intelligence", "performance_analytics",
            "enterprise_operations",
        ]
        missing = [k for k in required if k not in payload]
        if missing:
            print("FAIL missing payload keys", missing)
            return 1
        if payload.get("live_execution_enabled") is not False:
            print("FAIL live execution safety flag")
            return 1
        print("PASS autonomous command center payload")
    except Exception:
        traceback.print_exc()
        return 1

    print("PASSED: Phase 20 smoke test complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
