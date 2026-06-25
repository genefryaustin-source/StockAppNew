from __future__ import annotations

import importlib
import inspect
from typing import Any, Dict, List, Optional

from modules.forex.forex_validation_engine import FAIL, PASS, WARN, ForexValidationEngine


class ForexComponentValidator:
    """Validates importability, callable surfaces, and light behavioral contracts for Forex components."""

    COMPONENTS = [
        {"name": "Operations Center", "module": "modules.forex.forex_operations_center", "class": "ForexOperationsCenter", "methods": ["snapshot"]},
        {"name": "Control Plane", "module": "modules.forex.forex_control_plane", "class": "ForexControlPlane", "methods": []},
        {"name": "Supervisor", "module": "modules.forex.forex_supervisor", "class": "ForexSupervisor", "methods": []},
        {"name": "Continuous Runtime", "module": "modules.forex.forex_continuous_runtime_engine", "class": "ForexContinuousRuntimeEngine", "methods": []},
        {"name": "Scheduler", "module": "modules.forex.forex_scheduler", "class": "ForexScheduler", "methods": ["schedule_cycle"]},
        {"name": "Execution Planner", "module": "modules.forex.forex_execution_planner", "class": "ForexExecutionPlanner", "methods": []},
        {"name": "Execution Orchestrator", "module": "modules.forex.forex_execution_orchestrator", "class": "ForexExecutionOrchestrator", "methods": []},
        {"name": "Resource Governor", "module": "modules.forex.forex_resource_governor", "class": "ForexResourceGovernor", "methods": []},
        {"name": "Job Registry", "module": "modules.forex.forex_job_registry", "class": "ForexJobRegistry", "methods": []},
        {"name": "Execution Queue", "module": "modules.forex.forex_execution_queue", "class": "ForexExecutionQueue", "methods": []},
        {"name": "Workload Balancer", "module": "modules.forex.forex_workload_balancer", "class": "ForexWorkloadBalancer", "methods": []},
        {"name": "Runtime Controller", "module": "modules.forex.forex_runtime_controller", "class": "ForexRuntimeController", "methods": ["tick"]},
        {"name": "Autonomous Optimizer", "module": "modules.forex.forex_autonomous_optimizer", "class": "ForexAutonomousOptimizer", "methods": ["optimize"]},
        {"name": "Self Healing", "module": "modules.forex.forex_self_healing_engine", "class": "ForexSelfHealingEngine", "methods": []},
        {"name": "Self Diagnostic", "module": "modules.forex.forex_self_diagnostic_engine", "class": "ForexSelfDiagnosticEngine", "methods": []},
        {"name": "Performance Profiler", "module": "modules.forex.forex_performance_profiler", "class": "ForexPerformanceProfiler", "methods": []},
        {"name": "Stress Test Suite", "module": "modules.forex.forex_stress_test_suite", "class": "ForexStressTestSuite", "methods": []},
    ]

    DASHBOARDS = [
        {"name": "Operations Dashboard", "module": "modules.forex.forex_operations_dashboard", "function": "render_forex_operations_dashboard"},
        {"name": "Runtime Dashboard", "module": "modules.forex.forex_runtime_dashboard", "function": "render_forex_runtime_dashboard"},
        {"name": "Scheduler Dashboard", "module": "modules.forex.forex_scheduler_dashboard", "function": "render_forex_scheduler_dashboard"},
        {"name": "Optimizer Dashboard", "module": "modules.forex.forex_optimizer_dashboard", "function": "render_forex_optimizer_dashboard"},
        {"name": "Governor Dashboard", "module": "modules.forex.forex_governor_dashboard", "function": "render_forex_governor_dashboard"},
        {"name": "Control Center", "module": "modules.forex.forex_control_center", "function": "render_forex_control_center"},
        {"name": "Master Workspace", "module": "modules.forex.forex_master_workspace", "function": "render_forex_master_workspace"},
    ]

    def __init__(self, db: Any = None, user: Any = None) -> None:
        self.engine = ForexValidationEngine(db=db, user=user)

    def validate_component(self, component: Dict[str, Any]) -> Dict[str, Any]:
        module_path = component["module"]
        class_name = component.get("class")
        required_methods = component.get("methods", [])
        module = importlib.import_module(module_path)
        cls = getattr(module, class_name) if class_name else None
        instance = None
        init_error = None
        if cls is not None:
            try:
                instance = cls()
            except Exception as exc:
                init_error = f"{exc.__class__.__name__}: {exc}"
        missing = []
        for method in required_methods:
            target = instance if instance is not None else cls
            if not hasattr(target, method):
                missing.append(method)
        status = FAIL if missing else PASS
        if init_error and not missing:
            status = WARN
        return {
            "status": status,
            "message": "Component validated." if status == PASS else "Component has validation issues.",
            "component": component.get("name"),
            "module": module_path,
            "class": class_name,
            "required_methods": required_methods,
            "missing_methods": missing,
            "init_error": init_error,
            "signature": str(inspect.signature(cls)) if cls is not None else None,
        }

    def validate_dashboard(self, dashboard: Dict[str, Any]) -> Dict[str, Any]:
        module = importlib.import_module(dashboard["module"])
        fn = getattr(module, dashboard["function"])
        sig = inspect.signature(fn)
        params = sig.parameters
        accepts_db = "db" in params or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())
        accepts_user = "user" in params or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())
        status = PASS if accepts_db and accepts_user else WARN
        return {
            "status": status,
            "message": "Dashboard renderer is compatible." if status == PASS else "Dashboard renderer imports but does not expose db/user compatibility.",
            "dashboard": dashboard.get("name"),
            "module": dashboard["module"],
            "function": dashboard["function"],
            "signature": str(sig),
            "accepts_db": accepts_db,
            "accepts_user": accepts_user,
        }

    def run_component_validation(self) -> Dict[str, Any]:
        checks = []
        for component in self.COMPONENTS:
            checks.append((component["name"], lambda c=component: self.validate_component(c)))
        return self.engine.run_checks(checks, name="Forex Component Validation").to_dict()

    def run_dashboard_validation(self) -> Dict[str, Any]:
        checks = []
        for dashboard in self.DASHBOARDS:
            checks.append((dashboard["name"], lambda d=dashboard: self.validate_dashboard(d)))
        return self.engine.run_checks(checks, name="Forex Dashboard Validation").to_dict()

    def run_all(self) -> Dict[str, Any]:
        component = self.run_component_validation()
        dashboard = self.run_dashboard_validation()
        failed = component.get("failed", 0) + dashboard.get("failed", 0)
        warned = component.get("warned", 0) + dashboard.get("warned", 0)
        total = component.get("total", 0) + dashboard.get("total", 0)
        passed = component.get("passed", 0) + dashboard.get("passed", 0)
        return {
            "status": FAIL if failed else WARN if warned else PASS,
            "score": round((passed / total) * 100, 2) if total else 0,
            "passed": passed,
            "failed": failed,
            "warned": warned,
            "total": total,
            "component_validation": component,
            "dashboard_validation": dashboard,
        }
