"""
modules/analytics/analytics_fabric_bootstrap.py
"""

from __future__ import annotations

import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_parent_dir(path: str) -> None:
    db_path = Path(path)
    if db_path.parent and str(db_path.parent) not in ("", "."):
        db_path.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class AnalyticsFabricConfig:
    db_path: str = "data/analytics_fabric.db"
    default_lease_seconds: int = 300
    runtime_max_claims_per_tick: int = 250
    target_worker_utilization: float = 0.70
    target_queue_clear_minutes: float = 15.0
    reset_db: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalyticsFabric:
    fabric_id: str
    config: AnalyticsFabricConfig

    registry: Any
    execution_queue: Any
    workload_balancer: Any
    runtime_controller: Any
    scheduler: Any
    orchestrator: Any
    resource_governor: Any
    optimizer: Any
    bulk_operations: Any
    worker_capacity_model: Any
    provider_cost_intelligence: Any
    execution_governor: Any
    global_planner: Any
    tenant_universe_intelligence: Any

    created_at: str = field(default_factory=utc_now_iso)

    def summary(self) -> Dict[str, Any]:
        summary: Dict[str, Any] = {
            "fabric_id": self.fabric_id,
            "db_path": self.config.db_path,
            "created_at": self.created_at,
            "generated_at": utc_now_iso(),
        }

        for name, component in {
            "registry": self.registry,
            "execution_queue": self.execution_queue,
            "runtime_controller": self.runtime_controller,
            "orchestrator": self.orchestrator,
            "resource_governor": self.resource_governor,
            "optimizer": self.optimizer,
            "worker_capacity_model": self.worker_capacity_model,
            "provider_cost_intelligence": self.provider_cost_intelligence,
            "execution_governor": self.execution_governor,
            "global_planner": self.global_planner,
            "tenant_universe_intelligence": self.tenant_universe_intelligence,
        }.items():
            try:
                if hasattr(component, "queue_metrics"):
                    summary[name] = component.queue_metrics()
                elif hasattr(component, "runtime_metrics"):
                    summary[name] = component.runtime_metrics()
                elif hasattr(component, "analytics_metrics"):
                    summary[name] = component.analytics_metrics()
                elif hasattr(component, "governance_metrics"):
                    summary[name] = component.governance_metrics()
                elif hasattr(component, "optimization_metrics"):
                    summary[name] = component.optimization_metrics()
                elif hasattr(component, "capacity_summary"):
                    summary[name] = component.capacity_summary()
                elif hasattr(component, "summary"):
                    summary[name] = component.summary()
                elif hasattr(component, "governance_summary"):
                    summary[name] = component.governance_summary()
                elif hasattr(component, "planner_summary"):
                    summary[name] = component.planner_summary()
                elif hasattr(component, "intelligence_summary"):
                    summary[name] = component.intelligence_summary()
                else:
                    summary[name] = {"status": "available"}
            except Exception as exc:
                summary[name] = {
                    "status": "error",
                    "error": str(exc),
                }

        return summary


@dataclass
class AnalyticsFabricHealthCheck:
    health_check_id: str
    status: str
    checks: Dict[str, Any]
    generated_at: str = field(default_factory=utc_now_iso)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def build_analytics_fabric(
    config: Optional[AnalyticsFabricConfig] = None,
) -> AnalyticsFabric:
    config = config or AnalyticsFabricConfig()

    ensure_parent_dir(config.db_path)

    if config.reset_db and os.path.exists(config.db_path):
        os.remove(config.db_path)

    from modules.analytics.universe_job_registry import UniverseJobRegistry
    from modules.analytics.universe_execution_queue import UniverseExecutionQueue
    from modules.analytics.universe_workload_balancer import UniverseWorkloadBalancer
    from modules.analytics.universe_runtime_controller import UniverseRuntimeController
    from modules.analytics.intelligent_analytics_scheduler import IntelligentAnalyticsScheduler
    from modules.analytics.universe_analytics_orchestrator import UniverseAnalyticsOrchestrator
    from modules.analytics.analytics_resource_governor import AnalyticsResourceGovernor
    from modules.analytics.autonomous_analytics_optimizer import AutonomousAnalyticsOptimizer
    from modules.analytics.analytics_bulk_operations import AnalyticsBulkOperations
    from modules.analytics.worker_capacity_model import WorkerCapacityModel
    from modules.analytics.provider_cost_intelligence import ProviderCostIntelligence
    from modules.analytics.autonomous_execution_governor import AutonomousExecutionGovernor
    from modules.analytics.global_analytics_planner import GlobalAnalyticsPlanner
    from modules.analytics.tenant_universe_intelligence_engine import TenantUniverseIntelligenceEngine

    registry = UniverseJobRegistry(
        db_path=config.db_path,
    )

    execution_queue = UniverseExecutionQueue(
        registry=registry,
        db_path=config.db_path,
        default_lease_seconds=config.default_lease_seconds,
    )

    workload_balancer = UniverseWorkloadBalancer()

    runtime_controller = UniverseRuntimeController(
        registry=registry,
        queue=execution_queue,
        balancer=workload_balancer,
        db_path=config.db_path,
        max_claims_per_tick=config.runtime_max_claims_per_tick,
    )

    scheduler = IntelligentAnalyticsScheduler(
        registry=registry,
    )

    orchestrator = UniverseAnalyticsOrchestrator(
        registry=registry,
        scheduler=scheduler,
        execution_queue=execution_queue,
        workload_balancer=workload_balancer,
        runtime_controller=runtime_controller,
    )

    resource_governor = AnalyticsResourceGovernor()

    optimizer = AutonomousAnalyticsOptimizer()

    bulk_operations = AnalyticsBulkOperations(
        registry=registry,
        queue=execution_queue,
    )

    worker_capacity_model = WorkerCapacityModel(
        target_utilization=config.target_worker_utilization,
    )

    provider_cost_intelligence = ProviderCostIntelligence()

    execution_governor = AutonomousExecutionGovernor()

    tenant_universe_intelligence = TenantUniverseIntelligenceEngine()

    global_planner = GlobalAnalyticsPlanner(
        worker_capacity_model=worker_capacity_model,
        provider_cost_intelligence=provider_cost_intelligence,
        execution_governor=execution_governor,
        resource_governor=resource_governor,
        optimizer=optimizer,
        runtime_controller=runtime_controller,
        target_queue_clear_minutes=config.target_queue_clear_minutes,
    )

    return AnalyticsFabric(
        fabric_id=f"afabric_{uuid.uuid4().hex}",
        config=config,
        registry=registry,
        execution_queue=execution_queue,
        workload_balancer=workload_balancer,
        runtime_controller=runtime_controller,
        scheduler=scheduler,
        orchestrator=orchestrator,
        resource_governor=resource_governor,
        optimizer=optimizer,
        bulk_operations=bulk_operations,
        worker_capacity_model=worker_capacity_model,
        provider_cost_intelligence=provider_cost_intelligence,
        execution_governor=execution_governor,
        global_planner=global_planner,
        tenant_universe_intelligence=tenant_universe_intelligence,
    )


def run_fabric_health_check(
    fabric: AnalyticsFabric,
) -> AnalyticsFabricHealthCheck:
    checks: Dict[str, Any] = {}

    components = {
        "registry": fabric.registry,
        "execution_queue": fabric.execution_queue,
        "workload_balancer": fabric.workload_balancer,
        "runtime_controller": fabric.runtime_controller,
        "scheduler": fabric.scheduler,
        "orchestrator": fabric.orchestrator,
        "resource_governor": fabric.resource_governor,
        "optimizer": fabric.optimizer,
        "bulk_operations": fabric.bulk_operations,
        "worker_capacity_model": fabric.worker_capacity_model,
        "provider_cost_intelligence": fabric.provider_cost_intelligence,
        "execution_governor": fabric.execution_governor,
        "global_planner": fabric.global_planner,
        "tenant_universe_intelligence": fabric.tenant_universe_intelligence,
    }

    for name, component in components.items():
        checks[name] = {
            "available": component is not None,
            "class": component.__class__.__name__ if component else None,
        }

    try:
        checks["queue_metrics"] = fabric.execution_queue.queue_metrics()
    except Exception as exc:
        checks["queue_metrics"] = {
            "error": str(exc),
        }

    try:
        checks["runtime_metrics"] = fabric.runtime_controller.runtime_metrics()
    except Exception as exc:
        checks["runtime_metrics"] = {
            "error": str(exc),
        }

    failures = [
        name
        for name, check in checks.items()
        if isinstance(check, dict)
        and check.get("available") is False
    ]

    status = "PASS" if not failures else "FAIL"

    return AnalyticsFabricHealthCheck(
        health_check_id=f"afhc_{uuid.uuid4().hex}",
        status=status,
        checks=checks,
    )


def run_capacity_analysis(
    fabric: AnalyticsFabric,
    *,
    workers: Optional[list[Any]] = None,
    queue_metrics: Optional[Dict[str, Any]] = None,
    tenant_id: Optional[str] = None,
) -> Any:
    workers = workers or []
    queue_metrics = queue_metrics or fabric.execution_queue.queue_metrics()

    return fabric.worker_capacity_model.analyze_from_runtime(
        workers=workers,
        queue_metrics=queue_metrics,
        tenant_id=tenant_id,
    )


def run_global_plan(
    fabric: AnalyticsFabric,
    *,
    universes: Optional[list[Any]] = None,
    queue_metrics: Optional[Dict[str, Any]] = None,
    worker_report: Optional[Any] = None,
    provider_profiles: Optional[list[Any]] = None,
    tenant_metrics: Optional[Dict[str, Any]] = None,
    universe_metrics: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Any:
    return fabric.global_planner.build_execution_plan(
        universes=universes,
        queue_metrics=queue_metrics or fabric.execution_queue.queue_metrics(),
        worker_report=worker_report,
        provider_profiles=provider_profiles,
        tenant_metrics=tenant_metrics or {},
        universe_metrics=universe_metrics or {},
    )


def fabric_summary(
    fabric: AnalyticsFabric,
) -> Dict[str, Any]:
    return fabric.summary()


def create_default_analytics_fabric(
    db_path: str = "data/analytics_fabric.db",
    *,
    reset_db: bool = False,
) -> AnalyticsFabric:
    return build_analytics_fabric(
        AnalyticsFabricConfig(
            db_path=db_path,
            reset_db=reset_db,
        )
    )