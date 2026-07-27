"""
modules/analytics/analytics_fabric_system_test_suite.py
"""

from __future__ import annotations

import importlib
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class SystemTestResult:
    name: str
    status: str
    duration_ms: float
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SystemTestSummary:
    suite: str
    passed: int
    failed: int
    warnings: int
    total: int
    started_at: str
    completed_at: str
    duration_ms: float

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SystemTestReport:
    summary: SystemTestSummary
    results: List[SystemTestResult]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "summary": self.summary.as_dict(),
            "results": [result.as_dict() for result in self.results],
            "metadata": self.metadata,
        }


class AnalyticsFabricSystemTestSuite:
    def __init__(
        self,
        *,
        db_path: Optional[str] = None,
        reset_db: bool = True,
        fail_fast: bool = False,
        verbose: bool = True,
    ) -> None:
        self.db_path = db_path or str(
            Path(tempfile.gettempdir())
            / f"analytics_fabric_system_test_{uuid.uuid4().hex}.db"
        )
        self.reset_db = reset_db
        self.fail_fast = fail_fast
        self.verbose = verbose

        self.results: List[SystemTestResult] = []
        self.context: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Public Runner
    # ------------------------------------------------------------------

    def run_all(self) -> SystemTestReport:
        started_at = utc_now_iso()
        suite_started = time.perf_counter()

        tests: List[tuple[str, Callable[[], Dict[str, Any]]]] = [
            ("Imports", self.test_imports),
            ("Bootstrap", self.test_bootstrap),
            ("Persistence", self.test_persistence),
            ("Forecasting", self.test_forecasting),
            ("Optimization", self.test_optimization),
            ("Execution Planning", self.test_execution_planning),
            ("Execution Orchestration", self.test_execution_orchestration),
            ("Runtime Controller", self.test_runtime_controller),
            ("Autonomous Supervisor", self.test_autonomous_supervisor),
            ("Continuous Runtime", self.test_continuous_runtime),
            ("Command Processor", self.test_command_processor),
            ("Control Plane", self.test_control_plane),
            ("UI Imports", self.test_ui_imports),
            ("Master Workspace Import", self.test_master_workspace_import),
            ("End To End Command Flow", self.test_end_to_end_command_flow),
        ]

        for name, fn in tests:
            result = self._run_test(name, fn)
            self.results.append(result)

            if self.verbose:
                print(
                    f"{result.status:<7} | "
                    f"{result.name:<28} | "
                    f"{result.duration_ms:>10.2f} ms | "
                    f"{result.message}"
                )

            if self.fail_fast and result.status == "FAILED":
                break

        completed_at = utc_now_iso()
        duration_ms = round((time.perf_counter() - suite_started) * 1000.0, 4)

        passed = len([r for r in self.results if r.status == "PASSED"])
        failed = len([r for r in self.results if r.status == "FAILED"])
        warnings = len([r for r in self.results if r.status == "WARNING"])

        summary = SystemTestSummary(
            suite="Analytics Fabric System Test Suite",
            passed=passed,
            failed=failed,
            warnings=warnings,
            total=len(self.results),
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
        )

        return SystemTestReport(
            summary=summary,
            results=self.results,
            metadata={
                "db_path": self.db_path,
                "reset_db": self.reset_db,
                "fail_fast": self.fail_fast,
            },
        )

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_imports(self) -> Dict[str, Any]:
        modules = [
            "modules.analytics.analytics_fabric_bootstrap",
            "modules.analytics.analytics_fabric_persistence_engine",
            "modules.analytics.analytics_fabric_snapshot_scheduler",
            "modules.analytics.analytics_fabric_forecasting_engine",
            "modules.analytics.autonomous_forecast_optimizer",
            "modules.analytics.autonomous_execution_planner",
            "modules.analytics.autonomous_execution_orchestrator",
            "modules.analytics.analytics_fabric_runtime_controller",
            "modules.analytics.analytics_fabric_autonomous_supervisor",
            "modules.analytics.analytics_fabric_continuous_runtime_engine",
            "modules.analytics.analytics_fabric_command_processor",
            "modules.analytics.analytics_fabric_control_plane",
        ]

        loaded = []

        for module_name in modules:
            importlib.import_module(module_name)
            loaded.append(module_name)

        return {
            "message": "All analytics system modules imported.",
            "loaded": loaded,
        }

    def test_bootstrap(self) -> Dict[str, Any]:
        from modules.analytics.analytics_fabric_bootstrap import (
            AnalyticsFabricConfig,
            build_analytics_fabric,
            run_fabric_health_check,
        )

        fabric = build_analytics_fabric(
            AnalyticsFabricConfig(
                db_path=self.db_path,
                reset_db=self.reset_db,
            )
        )

        health = run_fabric_health_check(fabric)

        self.context["fabric"] = fabric

        return {
            "message": "Analytics fabric bootstrapped.",
            "health": self._as_dict(health),
        }

    def test_persistence(self) -> Dict[str, Any]:
        from modules.analytics.analytics_fabric_persistence_engine import (
            AnalyticsFabricPersistenceEngine,
        )

        engine = AnalyticsFabricPersistenceEngine(
            db_path=self.db_path.replace(".db", "_history.db")
        )

        validation_id = engine.save_validation_result(
            "system_test",
            {
                "summary": {
                    "status": "PASS",
                    "passed": 1,
                    "failed": 0,
                    "warnings": 0,
                },
                "checks": [],
            },
        )

        health_id = engine.save_fabric_health_snapshot(
            {
                "health_score": 100,
                "generated_at": utc_now_iso(),
            }
        )

        summary = engine.summary()

        self.context["persistence_engine"] = engine

        return {
            "message": "Persistence engine saved and summarized records.",
            "validation_id": validation_id,
            "health_id": health_id,
            "summary": summary,
        }

    def test_forecasting(self) -> Dict[str, Any]:
        from modules.analytics.analytics_fabric_forecasting_engine import (
            AnalyticsFabricForecastingEngine,
        )

        persistence = self.context.get("persistence_engine")

        engine = AnalyticsFabricForecastingEngine(
            persistence_engine=persistence,
        )

        report = engine.generate_forecast_report()

        self.context["forecasting_engine"] = engine
        self.context["forecast_report"] = report

        return {
            "message": "Forecast report generated.",
            "report": report.as_dict(),
        }

    def test_optimization(self) -> Dict[str, Any]:
        from modules.analytics.autonomous_forecast_optimizer import (
            AutonomousForecastOptimizer,
        )

        optimizer = AutonomousForecastOptimizer(
            forecasting_engine=self.context["forecasting_engine"],
            persistence_engine=self.context["persistence_engine"],
        )

        report = optimizer.generate_optimization_report()

        self.context["optimizer"] = optimizer
        self.context["optimization_report"] = report

        return {
            "message": "Optimization report generated.",
            "report": report.as_dict(),
        }

    def test_execution_planning(self) -> Dict[str, Any]:
        from modules.analytics.autonomous_execution_planner import (
            AutonomousExecutionPlanner,
        )

        planner = AutonomousExecutionPlanner(
            analytics_fabric=self.context.get("fabric"),
            forecast_optimizer=self.context["optimizer"],
            forecasting_engine=self.context["forecasting_engine"],
            persistence_engine=self.context["persistence_engine"],
        )

        plan = planner.build_execution_plan_from_optimizer(
            optimization_report=self.context["optimization_report"]
        )

        dry_result = planner.execute_plan(
            plan,
            dry_run=True,
        )

        self.context["execution_planner"] = planner
        self.context["execution_plan"] = plan

        return {
            "message": "Execution plan generated and dry-run executed.",
            "plan": plan.as_dict(),
            "dry_result": dry_result.as_dict(),
        }

    def test_execution_orchestration(self) -> Dict[str, Any]:
        from modules.analytics.autonomous_execution_orchestrator import (
            AutonomousExecutionOrchestrator,
        )

        orchestrator = AutonomousExecutionOrchestrator(
            execution_planner=self.context["execution_planner"],
            analytics_fabric=self.context.get("fabric"),
            persistence_engine=self.context["persistence_engine"],
        )

        result = orchestrator.execute_plan(
            self.context["execution_plan"],
            dry_run=True,
        )

        summary = orchestrator.execution_summary()

        self.context["orchestrator"] = orchestrator

        return {
            "message": "Execution orchestrator completed dry-run plan.",
            "result": result.as_dict(),
            "summary": summary,
        }

    def test_runtime_controller(self) -> Dict[str, Any]:
        from modules.analytics.analytics_fabric_runtime_controller import (
            AnalyticsFabricRuntimeController,
        )

        fabric = self.context.get("fabric")

        controller = AnalyticsFabricRuntimeController(
            forecasting_engine=self.context["forecasting_engine"],
            optimizer=self.context["optimizer"],
            planner=self.context["execution_planner"],
            orchestrator=self.context["orchestrator"],
            governor=getattr(fabric, "execution_governor", None),
            global_planner=getattr(fabric, "global_planner", None),
            worker_capacity_model=getattr(fabric, "worker_capacity_model", None),
            provider_cost_intelligence=getattr(fabric, "provider_cost_intelligence", None),
            persistence_engine=self.context["persistence_engine"],
        )

        controller.initialize_runtime()
        autonomous_result = controller.run_autonomous_cycle()
        snapshot = controller.runtime_snapshot()

        self.context["runtime_controller"] = controller

        return {
            "message": "Runtime controller initialized and autonomous cycle executed.",
            "autonomous_result": autonomous_result,
            "snapshot": snapshot.as_dict(),
            "summary": controller.runtime_summary(),
        }

    def test_autonomous_supervisor(self) -> Dict[str, Any]:
        from modules.analytics.analytics_fabric_autonomous_supervisor import (
            AnalyticsFabricAutonomousSupervisor,
        )
        from modules.analytics.analytics_fabric_snapshot_scheduler import (
            AnalyticsFabricSnapshotScheduler,
        )

        snapshot_scheduler = AnalyticsFabricSnapshotScheduler(
            persistence_engine=self.context["persistence_engine"],
            analytics_fabric=self.context.get("fabric"),
        )

        supervisor = AnalyticsFabricAutonomousSupervisor(
            runtime_controller=self.context["runtime_controller"],
            execution_governor=getattr(self.context.get("fabric"), "execution_governor", None),
            persistence_engine=self.context["persistence_engine"],
            snapshot_scheduler=snapshot_scheduler,
        )

        supervisor.start_supervisor()
        result = supervisor.run_supervisor_cycle(force=True)

        self.context["snapshot_scheduler"] = snapshot_scheduler
        self.context["supervisor"] = supervisor

        return {
            "message": "Autonomous supervisor started and forced cycle executed.",
            "cycle_result": result,
            "status": supervisor.supervisor_status(),
        }

    def test_continuous_runtime(self) -> Dict[str, Any]:
        from modules.analytics.analytics_fabric_continuous_runtime_engine import (
            AnalyticsFabricContinuousRuntimeEngine,
            ContinuousRuntimeConfig,
        )

        engine = AnalyticsFabricContinuousRuntimeEngine(
            supervisor=self.context["supervisor"],
            runtime_controller=self.context["runtime_controller"],
            snapshot_scheduler=self.context["snapshot_scheduler"],
            persistence_engine=self.context["persistence_engine"],
            config=ContinuousRuntimeConfig(
                loop_interval_seconds=0.01,
                heartbeat_interval_seconds=0.01,
                health_check_interval_seconds=0.01,
                recovery_interval_seconds=0.01,
                snapshot_interval_seconds=0.01,
                governance_interval_seconds=0.01,
                enable_threaded_loop=False,
            ),
        )

        engine.start_runtime()
        tick = engine.run_once(force=True)
        heartbeat = engine.emit_heartbeat()

        self.context["continuous_runtime_engine"] = engine

        return {
            "message": "Continuous runtime engine started, ticked, and emitted heartbeat.",
            "tick": tick.as_dict(),
            "heartbeat": heartbeat.as_dict(),
            "summary": engine.runtime_summary(),
        }

    def test_command_processor(self) -> Dict[str, Any]:
        from modules.analytics.analytics_fabric_command_processor import (
            AnalyticsCommandType,
            AnalyticsFabricCommandProcessor,
        )

        processor = AnalyticsFabricCommandProcessor(
            continuous_runtime_engine=self.context["continuous_runtime_engine"],
            supervisor=self.context["supervisor"],
            runtime_controller=self.context["runtime_controller"],
            orchestrator=self.context["orchestrator"],
            persistence_engine=self.context["persistence_engine"],
            require_approval_for_runtime_stop=True,
            require_approval_for_real_execution=False,
        )

        command = processor.submit_command(
            AnalyticsCommandType.RUN_FORECAST.value,
            requested_by="system_test",
            execute_immediately=True,
        )

        stop_command = processor.submit_command(
            AnalyticsCommandType.STOP_RUNTIME.value,
            requested_by="system_test",
            execute_immediately=False,
        )

        processor.approve_command(
            stop_command.command_id,
            approved_by="system_test",
            reason="System test approval.",
        )

        self.context["command_processor"] = processor

        return {
            "message": "Command processor submitted, executed, and approved commands.",
            "command": command.as_dict(),
            "stop_command": stop_command.as_dict(),
            "metrics": processor.command_metrics(),
        }

    def test_control_plane(self) -> Dict[str, Any]:
        from modules.analytics.analytics_fabric_control_plane import (
            AnalyticsFabricControlPlane,
        )

        fabric = self.context.get("fabric")

        control_plane = AnalyticsFabricControlPlane(
            command_processor=self.context["command_processor"],
            continuous_runtime_engine=self.context["continuous_runtime_engine"],
            autonomous_supervisor=self.context["supervisor"],
            runtime_controller=self.context["runtime_controller"],
            execution_orchestrator=self.context["orchestrator"],
            forecasting_engine=self.context["forecasting_engine"],
            optimizer=self.context["optimizer"],
            execution_planner=self.context["execution_planner"],
            governor=getattr(fabric, "execution_governor", None),
            persistence_engine=self.context["persistence_engine"],
            snapshot_scheduler=self.context["snapshot_scheduler"],
            metadata={"test": "system_suite"},
        )

        status = control_plane.global_status()
        health = control_plane.global_health()
        snapshot = control_plane.create_snapshot()

        self.context["control_plane"] = control_plane

        return {
            "message": "Control plane created, status checked, snapshot created.",
            "status": status,
            "health": health,
            "snapshot": snapshot.as_dict(),
        }

    def test_ui_imports(self) -> Dict[str, Any]:
        modules = [
            "modules.ui.admin.analytics_fabric_control_plane_dashboard",
            "modules.ui.admin.analytics_fabric_command_center",
            "modules.ui.admin.analytics_fabric_continuous_runtime_dashboard",
            "modules.ui.admin.analytics_fabric_autonomous_supervisor_dashboard",
            "modules.ui.admin.analytics_fabric_runtime_control_center",
            "modules.ui.admin.autonomous_execution_orchestrator_dashboard",
            "modules.ui.admin.autonomous_execution_planner_dashboard",
            "modules.ui.admin.autonomous_forecast_optimizer_dashboard",
            "modules.ui.admin.analytics_fabric_forecasting_dashboard",
            "modules.ui.admin.analytics_fabric_history_control_center",
            "modules.ui.admin.analytics_fabric_history_dashboard",
            "modules.ui.admin.analytics_fabric_control_tower",
            "modules.ui.admin.analytics_fabric_executive_dashboard",
            "modules.ui.admin.analytics_fabric_validation_dashboard",
            "modules.ui.admin.analytics_fabric_operations_center",
        ]

        loaded = []

        for module_name in modules:
            importlib.import_module(module_name)
            loaded.append(module_name)

        return {
            "message": "All Analytics Fabric UI modules imported.",
            "loaded": loaded,
        }

    def test_master_workspace_import(self) -> Dict[str, Any]:
        module = importlib.import_module(
            "modules.ui.admin.analytics_fabric_master_workspace"
        )

        required = [
            "render_analytics_fabric_master_workspace",
            "render_analytics_master_workspace",
        ]

        missing = [
            name for name in required
            if not hasattr(module, name)
        ]

        if missing:
            raise AssertionError(f"Missing workspace render functions: {missing}")

        return {
            "message": "Master workspace imported and render functions found.",
            "required": required,
        }

    def test_end_to_end_command_flow(self) -> Dict[str, Any]:
        processor = self.context["command_processor"]
        control_plane = self.context["control_plane"]

        routed = control_plane.route_command(
            "RUN_CONTINUOUS_RUNTIME_TICK",
            payload={"force": True},
            execute_immediately=True,
        )

        metrics = processor.command_metrics()

        if metrics.get("commands_total", 0) <= 0:
            raise AssertionError("Command processor did not record commands.")

        return {
            "message": "End-to-end command routed through control plane.",
            "routed": routed,
            "metrics": metrics,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _run_test(
        self,
        name: str,
        fn: Callable[[], Dict[str, Any]],
    ) -> SystemTestResult:
        started = time.perf_counter()

        try:
            details = fn()
            duration_ms = round((time.perf_counter() - started) * 1000.0, 4)

            return SystemTestResult(
                name=name,
                status="PASSED",
                duration_ms=duration_ms,
                message=details.pop("message", "Passed."),
                details=details,
            )

        except Exception as exc:
            duration_ms = round((time.perf_counter() - started) * 1000.0, 4)

            return SystemTestResult(
                name=name,
                status="FAILED",
                duration_ms=duration_ms,
                message=str(exc),
                details={
                    "exception_type": exc.__class__.__name__,
                },
            )

    @staticmethod
    def _as_dict(value: Any) -> Dict[str, Any]:
        if value is None:
            return {}

        if isinstance(value, dict):
            return value

        if hasattr(value, "as_dict"):
            return value.as_dict()

        if hasattr(value, "__dataclass_fields__"):
            return asdict(value)

        if isinstance(value, list):
            return {"items": value}

        return {"value": str(value)}


def run_analytics_fabric_system_test_suite(
    *,
    db_path: Optional[str] = None,
    reset_db: bool = True,
    fail_fast: bool = False,
    verbose: bool = True,
) -> SystemTestReport:
    suite = AnalyticsFabricSystemTestSuite(
        db_path=db_path,
        reset_db=reset_db,
        fail_fast=fail_fast,
        verbose=verbose,
    )

    return suite.run_all()