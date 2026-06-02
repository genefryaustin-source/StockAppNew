"""
modules/analytics/analytics_fabric_control_plane.py
"""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ControlPlaneState(str, Enum):
    INITIALIZED = "INITIALIZED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    DEGRADED = "DEGRADED"
    RECOVERING = "RECOVERING"
    FAILED = "FAILED"


class ControlPlaneServiceState(str, Enum):
    REGISTERED = "REGISTERED"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    STOPPED = "STOPPED"
    UNKNOWN = "UNKNOWN"


class ControlPlaneServiceType(str, Enum):
    COMMAND_PROCESSOR = "COMMAND_PROCESSOR"
    CONTINUOUS_RUNTIME_ENGINE = "CONTINUOUS_RUNTIME_ENGINE"
    AUTONOMOUS_SUPERVISOR = "AUTONOMOUS_SUPERVISOR"
    RUNTIME_CONTROLLER = "RUNTIME_CONTROLLER"
    EXECUTION_ORCHESTRATOR = "EXECUTION_ORCHESTRATOR"
    FORECASTING_ENGINE = "FORECASTING_ENGINE"
    OPTIMIZER = "OPTIMIZER"
    EXECUTION_PLANNER = "EXECUTION_PLANNER"
    GOVERNOR = "GOVERNOR"
    PERSISTENCE_ENGINE = "PERSISTENCE_ENGINE"
    SNAPSHOT_SCHEDULER = "SNAPSHOT_SCHEDULER"
    CONTROL_TOWER = "CONTROL_TOWER"
    OTHER = "OTHER"


@dataclass
class ControlPlaneService:
    service_id: str
    service_type: str
    name: str
    instance: Optional[Any] = None
    state: str = ControlPlaneServiceState.REGISTERED.value
    health_score: float = 100.0
    priority: int = 100
    metadata: Dict[str, Any] = field(default_factory=dict)
    registered_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def as_dict(self, include_instance: bool = False) -> Dict[str, Any]:
        data = {
            "service_id": self.service_id,
            "service_type": self.service_type,
            "name": self.name,
            "state": self.state,
            "health_score": self.health_score,
            "priority": self.priority,
            "metadata": dict(self.metadata),
            "registered_at": self.registered_at,
            "updated_at": self.updated_at,
        }

        if include_instance:
            data["instance"] = str(type(self.instance).__name__)

        return data


@dataclass
class ControlPlaneRegistration:
    registration_id: str
    service_id: str
    service_type: str
    name: str
    registered_at: str = field(default_factory=utc_now_iso)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ControlPlaneHealth:
    health_score: float
    registered_services: int
    active_services: int
    degraded_services: int
    failed_services: int
    stopped_services: int
    state: str
    generated_at: str = field(default_factory=utc_now_iso)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ControlPlaneMetrics:
    registered_services: int = 0
    active_services: int = 0
    degraded_services: int = 0
    failed_services: int = 0
    commands_processed: int = 0
    snapshots_created: int = 0
    recoveries_triggered: int = 0
    lifecycle_operations: int = 0
    started_at: Optional[str] = None
    stopped_at: Optional[str] = None
    uptime_seconds: float = 0.0

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ControlPlaneStateRecord:
    state: str = ControlPlaneState.INITIALIZED.value
    started_at: Optional[str] = None
    updated_at: str = field(default_factory=utc_now_iso)
    message: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ControlPlaneSnapshot:
    snapshot_id: str
    state: str
    health: Dict[str, Any]
    metrics: Dict[str, Any]
    services: List[Dict[str, Any]]
    status: Dict[str, Any]
    generated_at: str = field(default_factory=utc_now_iso)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ControlPlaneEvent:
    event_id: str
    event_type: str
    message: str
    severity: str = "INFO"
    payload: Dict[str, Any] = field(default_factory=dict)
    generated_at: str = field(default_factory=utc_now_iso)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AnalyticsFabricControlPlane:
    """
    Top-level orchestration layer for the Analytics Fabric.

    The control plane sits above the command processor and runtime services.
    Dashboards should treat this as the unified platform API.
    """

    def __init__(
        self,
        *,
        command_processor: Optional[Any] = None,
        continuous_runtime_engine: Optional[Any] = None,
        autonomous_supervisor: Optional[Any] = None,
        runtime_controller: Optional[Any] = None,
        execution_orchestrator: Optional[Any] = None,
        forecasting_engine: Optional[Any] = None,
        optimizer: Optional[Any] = None,
        execution_planner: Optional[Any] = None,
        governor: Optional[Any] = None,
        persistence_engine: Optional[Any] = None,
        snapshot_scheduler: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.control_plane_id = f"cp_{uuid.uuid4().hex}"
        self.metadata = metadata or {}

        self.state = ControlPlaneStateRecord()
        self.metrics = ControlPlaneMetrics()
        self.services: Dict[str, ControlPlaneService] = {}
        self.registrations: List[ControlPlaneRegistration] = []
        self.events: List[ControlPlaneEvent] = []
        self.snapshots: List[ControlPlaneSnapshot] = []

        self._started_monotonic: Optional[float] = None

        self.command_processor = command_processor
        self.continuous_runtime_engine = continuous_runtime_engine
        self.autonomous_supervisor = autonomous_supervisor
        self.runtime_controller = runtime_controller
        self.execution_orchestrator = execution_orchestrator
        self.forecasting_engine = forecasting_engine
        self.optimizer = optimizer
        self.execution_planner = execution_planner
        self.governor = governor
        self.persistence_engine = persistence_engine
        self.snapshot_scheduler = snapshot_scheduler

        self._register_initial_services()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_service(
        self,
        *,
        service_type: str,
        name: str,
        instance: Optional[Any] = None,
        service_id: Optional[str] = None,
        priority: int = 100,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ControlPlaneService:
        normalized_type = self._normalize_service_type(service_type)

        service = ControlPlaneService(
            service_id=service_id or f"svc_{uuid.uuid4().hex}",
            service_type=normalized_type,
            name=name,
            instance=instance,
            priority=priority,
            metadata=metadata or {},
        )

        self.services[service.service_id] = service

        registration = ControlPlaneRegistration(
            registration_id=f"reg_{uuid.uuid4().hex}",
            service_id=service.service_id,
            service_type=normalized_type,
            name=name,
            metadata=metadata or {},
        )

        self.registrations.append(registration)
        self.metrics.registered_services = len(self.services)

        self._event(
            "SERVICE_REGISTERED",
            f"Service registered: {name}",
            payload=registration.as_dict(),
        )

        return service

    def unregister_service(
        self,
        service_id: str,
    ) -> bool:
        service = self.services.get(service_id)

        if service is None:
            return False

        del self.services[service_id]
        self.metrics.registered_services = len(self.services)

        self._event(
            "SERVICE_UNREGISTERED",
            f"Service unregistered: {service.name}",
            payload=service.as_dict(),
        )

        return True

    def service_status(
        self,
        service_id: str,
    ) -> Dict[str, Any]:
        service = self.services.get(service_id)

        if service is None:
            return {
                "status": "NOT_FOUND",
                "service_id": service_id,
                "generated_at": utc_now_iso(),
            }

        service.state = self._detect_service_state(service)
        service.health_score = self._detect_service_health(service)
        service.updated_at = utc_now_iso()

        return service.as_dict()

    def service_inventory(self) -> List[Dict[str, Any]]:
        rows = []

        for service in sorted(
            self.services.values(),
            key=lambda item: (item.priority, item.name),
        ):
            rows.append(self.service_status(service.service_id))

        return rows

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def platform_start(self) -> Dict[str, Any]:
        self.state.state = ControlPlaneState.STARTING.value
        self.state.updated_at = utc_now_iso()
        self.metrics.lifecycle_operations += 1
        self.metrics.started_at = self.metrics.started_at or utc_now_iso()
        self._started_monotonic = self._started_monotonic or time.monotonic()

        results = {}

        runtime = self.continuous_runtime_engine or self._get_service_instance(
            ControlPlaneServiceType.CONTINUOUS_RUNTIME_ENGINE.value
        )

        if runtime is not None and hasattr(runtime, "start_runtime"):
            results["continuous_runtime"] = self._safe_call(runtime.start_runtime)
        elif self.runtime_controller is not None and hasattr(self.runtime_controller, "start_runtime"):
            results["runtime_controller"] = self._safe_call(self.runtime_controller.start_runtime)

        self.state.state = ControlPlaneState.RUNNING.value
        self.state.message = "Platform started."
        self.state.updated_at = utc_now_iso()

        self._event(
            "PLATFORM_STARTED",
            "Analytics Fabric platform started.",
            payload=results,
        )

        return self.global_status()

    def platform_pause(self) -> Dict[str, Any]:
        self.state.state = ControlPlaneState.PAUSED.value
        self.state.updated_at = utc_now_iso()
        self.metrics.lifecycle_operations += 1

        runtime = self.continuous_runtime_engine or self._get_service_instance(
            ControlPlaneServiceType.CONTINUOUS_RUNTIME_ENGINE.value
        )

        result = {}

        if runtime is not None and hasattr(runtime, "pause_runtime"):
            result = self._safe_call(runtime.pause_runtime)

        self._event(
            "PLATFORM_PAUSED",
            "Analytics Fabric platform paused.",
            payload=result,
        )

        return self.global_status()

    def platform_resume(self) -> Dict[str, Any]:
        self.state.state = ControlPlaneState.RUNNING.value
        self.state.updated_at = utc_now_iso()
        self.metrics.lifecycle_operations += 1

        runtime = self.continuous_runtime_engine or self._get_service_instance(
            ControlPlaneServiceType.CONTINUOUS_RUNTIME_ENGINE.value
        )

        result = {}

        if runtime is not None and hasattr(runtime, "resume_runtime"):
            result = self._safe_call(runtime.resume_runtime)

        self._event(
            "PLATFORM_RESUMED",
            "Analytics Fabric platform resumed.",
            payload=result,
        )

        return self.global_status()

    def platform_stop(self) -> Dict[str, Any]:
        self.state.state = ControlPlaneState.STOPPING.value
        self.state.updated_at = utc_now_iso()
        self.metrics.lifecycle_operations += 1

        runtime = self.continuous_runtime_engine or self._get_service_instance(
            ControlPlaneServiceType.CONTINUOUS_RUNTIME_ENGINE.value
        )

        result = {}

        if runtime is not None and hasattr(runtime, "stop_runtime"):
            result = self._safe_call(runtime.stop_runtime)
        elif self.runtime_controller is not None and hasattr(self.runtime_controller, "stop_runtime"):
            result = self._safe_call(self.runtime_controller.stop_runtime)

        self.state.state = ControlPlaneState.STOPPED.value
        self.state.updated_at = utc_now_iso()
        self.metrics.stopped_at = utc_now_iso()

        self._event(
            "PLATFORM_STOPPED",
            "Analytics Fabric platform stopped.",
            payload=result,
        )

        return self.global_status()

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def submit_command(
        self,
        command_type: str,
        *,
        requested_by: str = "control_plane",
        payload: Optional[Dict[str, Any]] = None,
        severity: str = "INFO",
        requires_approval: Optional[bool] = None,
        execute_immediately: bool = False,
    ) -> Dict[str, Any]:
        processor = self.command_processor or self._get_service_instance(
            ControlPlaneServiceType.COMMAND_PROCESSOR.value
        )

        if processor is None:
            return {
                "status": "NO_COMMAND_PROCESSOR",
                "generated_at": utc_now_iso(),
            }

        command = processor.submit_command(
            command_type=command_type,
            requested_by=requested_by,
            payload=payload or {},
            severity=severity,
            requires_approval=requires_approval,
            execute_immediately=execute_immediately,
        )

        self.metrics.commands_processed += 1

        return self._as_dict(command)

    def route_command(
        self,
        command_type: str,
        *,
        payload: Optional[Dict[str, Any]] = None,
        execute_immediately: bool = True,
    ) -> Dict[str, Any]:
        return self.submit_command(
            command_type,
            payload=payload or {},
            execute_immediately=execute_immediately,
        )

    # ------------------------------------------------------------------
    # Health / Status / Snapshot
    # ------------------------------------------------------------------

    def global_health(self) -> Dict[str, Any]:
        inventory = self.service_inventory()

        registered = len(inventory)
        active = len([s for s in inventory if s.get("state") == ControlPlaneServiceState.ACTIVE.value])
        degraded = len([s for s in inventory if s.get("state") == ControlPlaneServiceState.DEGRADED.value])
        failed = len([s for s in inventory if s.get("state") == ControlPlaneServiceState.FAILED.value])
        stopped = len([s for s in inventory if s.get("state") == ControlPlaneServiceState.STOPPED.value])

        if registered <= 0:
            score = 0.0
        else:
            average_service_health = sum(float(s.get("health_score", 0.0) or 0.0) for s in inventory) / registered
            penalty = (failed * 20.0) + (degraded * 10.0) + (stopped * 5.0)
            score = max(0.0, min(100.0, average_service_health - penalty))

        if failed:
            self.state.state = ControlPlaneState.DEGRADED.value

        health = ControlPlaneHealth(
            health_score=round(score, 2),
            registered_services=registered,
            active_services=active,
            degraded_services=degraded,
            failed_services=failed,
            stopped_services=stopped,
            state=self.state.state,
        )

        return health.as_dict()

    def global_status(self) -> Dict[str, Any]:
        self._update_metrics_from_services()

        return {
            "control_plane_id": self.control_plane_id,
            "state": self.state.as_dict(),
            "health": self.global_health(),
            "metrics": self.control_plane_metrics(),
            "services": self.service_inventory(),
            "metadata": self.metadata,
            "generated_at": utc_now_iso(),
        }

    def control_plane_metrics(self) -> Dict[str, Any]:
        if self._started_monotonic is not None:
            self.metrics.uptime_seconds = round(time.monotonic() - self._started_monotonic, 2)

        self._update_metrics_from_services()

        command_processor = self.command_processor or self._get_service_instance(
            ControlPlaneServiceType.COMMAND_PROCESSOR.value
        )

        if command_processor is not None and hasattr(command_processor, "command_metrics"):
            try:
                command_metrics = command_processor.command_metrics()
                self.metrics.commands_processed = int(
                    command_metrics.get("commands_total", self.metrics.commands_processed) or 0
                )
            except Exception:
                pass

        return self.metrics.as_dict()

    def create_snapshot(self) -> ControlPlaneSnapshot:
        snapshot = ControlPlaneSnapshot(
            snapshot_id=f"cpsnap_{uuid.uuid4().hex}",
            state=self.state.state,
            health=self.global_health(),
            metrics=self.control_plane_metrics(),
            services=self.service_inventory(),
            status={
                "control_plane_id": self.control_plane_id,
                "state": self.state.as_dict(),
                "metadata": self.metadata,
            },
        )

        self.snapshots.append(snapshot)
        self.metrics.snapshots_created += 1

        if len(self.snapshots) > 10000:
            self.snapshots = self.snapshots[-10000:]

        self._persist_snapshot(snapshot)

        self._event(
            "CONTROL_PLANE_SNAPSHOT_CREATED",
            "Control plane snapshot created.",
            payload={"snapshot_id": snapshot.snapshot_id},
        )

        return snapshot

    def snapshot_history(self, limit: int = 1000) -> List[Dict[str, Any]]:
        return [snapshot.as_dict() for snapshot in self.snapshots[-limit:]]

    def event_history(self, limit: int = 1000) -> List[Dict[str, Any]]:
        return [event.as_dict() for event in self.events[-limit:]]

    def registration_history(self, limit: int = 1000) -> List[Dict[str, Any]]:
        return [registration.as_dict() for registration in self.registrations[-limit:]]

    # ------------------------------------------------------------------
    # Recovery
    # ------------------------------------------------------------------

    def control_plane_recovery(self) -> Dict[str, Any]:
        self.state.state = ControlPlaneState.RECOVERING.value
        self.state.updated_at = utc_now_iso()
        self.metrics.recoveries_triggered += 1

        results = {}

        runtime = self.continuous_runtime_engine or self._get_service_instance(
            ControlPlaneServiceType.CONTINUOUS_RUNTIME_ENGINE.value
        )
        supervisor = self.autonomous_supervisor or self._get_service_instance(
            ControlPlaneServiceType.AUTONOMOUS_SUPERVISOR.value
        )
        controller = self.runtime_controller or self._get_service_instance(
            ControlPlaneServiceType.RUNTIME_CONTROLLER.value
        )

        if runtime is not None and hasattr(runtime, "run_recovery_cycle"):
            results["continuous_runtime"] = self._safe_call(runtime.run_recovery_cycle)

        if supervisor is not None and hasattr(supervisor, "run_recovery_cycle"):
            results["supervisor"] = self._safe_call(supervisor.run_recovery_cycle)

        if controller is not None and hasattr(controller, "run_recovery_cycle"):
            results["runtime_controller"] = self._safe_call(controller.run_recovery_cycle)

        self.state.state = ControlPlaneState.RUNNING.value
        self.state.updated_at = utc_now_iso()

        self._event(
            "CONTROL_PLANE_RECOVERY_COMPLETED",
            "Control plane recovery completed.",
            severity="WARN",
            payload=results,
        )

        return {
            "status": "COMPLETED",
            "results": results,
            "generated_at": utc_now_iso(),
        }

    # ------------------------------------------------------------------
    # Exports
    # ------------------------------------------------------------------

    def export_state(self) -> Dict[str, Any]:
        return {
            "control_plane_id": self.control_plane_id,
            "state": self.state.as_dict(),
            "health": self.global_health(),
            "metrics": self.control_plane_metrics(),
            "services": self.service_inventory(),
            "registrations": self.registration_history(limit=10000),
            "events": self.event_history(limit=10000),
            "snapshots": self.snapshot_history(limit=10000),
            "metadata": self.metadata,
            "generated_at": utc_now_iso(),
        }

    def export_executive_package(self) -> Dict[str, Any]:
        return {
            "control_plane_id": self.control_plane_id,
            "state": self.state.as_dict(),
            "health": self.global_health(),
            "metrics": self.control_plane_metrics(),
            "service_summary": self._service_summary(),
            "recent_events": self.event_history(limit=100),
            "recent_snapshots": self.snapshot_history(limit=25),
            "command_processor": self._safe_status(
                self.command_processor,
                "command_metrics",
            ),
            "continuous_runtime": self._safe_status(
                self.continuous_runtime_engine,
                "runtime_summary",
            ),
            "supervisor": self._safe_status(
                self.autonomous_supervisor,
                "supervisor_status",
            ),
            "runtime_controller": self._safe_status(
                self.runtime_controller,
                "runtime_summary",
            ),
            "generated_at": utc_now_iso(),
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _register_initial_services(self) -> None:
        mapping = [
            (
                ControlPlaneServiceType.COMMAND_PROCESSOR.value,
                "Command Processor",
                self.command_processor,
                10,
            ),
            (
                ControlPlaneServiceType.CONTINUOUS_RUNTIME_ENGINE.value,
                "Continuous Runtime Engine",
                self.continuous_runtime_engine,
                20,
            ),
            (
                ControlPlaneServiceType.AUTONOMOUS_SUPERVISOR.value,
                "Autonomous Supervisor",
                self.autonomous_supervisor,
                30,
            ),
            (
                ControlPlaneServiceType.RUNTIME_CONTROLLER.value,
                "Runtime Controller",
                self.runtime_controller,
                40,
            ),
            (
                ControlPlaneServiceType.EXECUTION_ORCHESTRATOR.value,
                "Execution Orchestrator",
                self.execution_orchestrator,
                50,
            ),
            (
                ControlPlaneServiceType.FORECASTING_ENGINE.value,
                "Forecasting Engine",
                self.forecasting_engine,
                60,
            ),
            (
                ControlPlaneServiceType.OPTIMIZER.value,
                "Forecast Optimizer",
                self.optimizer,
                70,
            ),
            (
                ControlPlaneServiceType.EXECUTION_PLANNER.value,
                "Execution Planner",
                self.execution_planner,
                80,
            ),
            (
                ControlPlaneServiceType.GOVERNOR.value,
                "Execution Governor",
                self.governor,
                90,
            ),
            (
                ControlPlaneServiceType.PERSISTENCE_ENGINE.value,
                "Persistence Engine",
                self.persistence_engine,
                100,
            ),
            (
                ControlPlaneServiceType.SNAPSHOT_SCHEDULER.value,
                "Snapshot Scheduler",
                self.snapshot_scheduler,
                110,
            ),
        ]

        for service_type, name, instance, priority in mapping:
            if instance is not None:
                self.register_service(
                    service_type=service_type,
                    name=name,
                    instance=instance,
                    priority=priority,
                )

    def _normalize_service_type(self, service_type: str) -> str:
        normalized = str(service_type).strip().upper()
        valid = {item.value for item in ControlPlaneServiceType}

        if normalized not in valid:
            return ControlPlaneServiceType.OTHER.value

        return normalized

    def _get_service_instance(
        self,
        service_type: str,
    ) -> Optional[Any]:
        for service in self.services.values():
            if service.service_type == service_type:
                return service.instance

        return None

    def _detect_service_state(
        self,
        service: ControlPlaneService,
    ) -> str:
        instance = service.instance

        if instance is None:
            return ControlPlaneServiceState.UNKNOWN.value

        status = self._safe_service_status(instance)

        raw_state = str(
            status.get("state")
            or status.get("status")
            or service.state
            or ""
        ).upper()

        if raw_state in {
            "RUNNING",
            "READY",
            "ACTIVE",
            "SUCCESS",
            "COMPLETED",
            "INITIALIZED",
        }:
            return ControlPlaneServiceState.ACTIVE.value

        if raw_state in {"PAUSED"}:
            return ControlPlaneServiceState.PAUSED.value

        if raw_state in {"DEGRADED", "RECOVERING"}:
            return ControlPlaneServiceState.DEGRADED.value

        if raw_state in {"FAILED", "ERROR", "CRITICAL"}:
            return ControlPlaneServiceState.FAILED.value

        if raw_state in {"STOPPED", "STOPPING"}:
            return ControlPlaneServiceState.STOPPED.value

        return ControlPlaneServiceState.ACTIVE.value

    def _detect_service_health(
        self,
        service: ControlPlaneService,
    ) -> float:
        instance = service.instance

        if instance is None:
            return 0.0

        status = self._safe_service_status(instance)

        health = status.get("health", status)

        if isinstance(health, dict):
            for key in [
                "health_score",
                "supervisor_health_score",
                "runtime_health_score",
                "fabric_health",
                "score",
            ]:
                if key in health:
                    try:
                        return round(float(health[key]), 2)
                    except Exception:
                        pass

        if service.state == ControlPlaneServiceState.FAILED.value:
            return 0.0

        if service.state == ControlPlaneServiceState.DEGRADED.value:
            return 60.0

        if service.state == ControlPlaneServiceState.PAUSED.value:
            return 80.0

        return 100.0

    def _safe_service_status(
        self,
        instance: Any,
    ) -> Dict[str, Any]:
        methods = [
            "runtime_status",
            "supervisor_status",
            "global_status",
            "execution_summary",
            "command_metrics",
            "snapshot_summary",
            "summary",
        ]

        for method_name in methods:
            method = getattr(instance, method_name, None)

            if method is None:
                continue

            try:
                result = method()
                return self._as_dict(result)
            except Exception:
                continue

        return {
            "status": "AVAILABLE",
            "class": instance.__class__.__name__,
        }

    def _update_metrics_from_services(self) -> None:
        inventory = [
            self.service_status(service_id)
            for service_id in list(self.services.keys())
        ]

        self.metrics.registered_services = len(inventory)
        self.metrics.active_services = len(
            [
                item for item in inventory
                if item.get("state") == ControlPlaneServiceState.ACTIVE.value
            ]
        )
        self.metrics.degraded_services = len(
            [
                item for item in inventory
                if item.get("state") == ControlPlaneServiceState.DEGRADED.value
            ]
        )
        self.metrics.failed_services = len(
            [
                item for item in inventory
                if item.get("state") == ControlPlaneServiceState.FAILED.value
            ]
        )

    def _service_summary(self) -> Dict[str, Any]:
        inventory = self.service_inventory()

        counts: Dict[str, int] = {}

        for item in inventory:
            key = item.get("service_type", "UNKNOWN")
            counts[key] = counts.get(key, 0) + 1

        return {
            "counts_by_type": counts,
            "registered_services": len(inventory),
            "active_services": len(
                [
                    item for item in inventory
                    if item.get("state") == ControlPlaneServiceState.ACTIVE.value
                ]
            ),
            "degraded_services": len(
                [
                    item for item in inventory
                    if item.get("state") == ControlPlaneServiceState.DEGRADED.value
                ]
            ),
            "failed_services": len(
                [
                    item for item in inventory
                    if item.get("state") == ControlPlaneServiceState.FAILED.value
                ]
            ),
        }

    def _persist_snapshot(
        self,
        snapshot: ControlPlaneSnapshot,
    ) -> None:
        if self.persistence_engine is None:
            return

        try:
            self.persistence_engine.save_executive_snapshot(
                snapshot_name="analytics_fabric_control_plane_snapshot",
                payload=snapshot.as_dict(),
            )
        except Exception:
            pass

    def _event(
        self,
        event_type: str,
        message: str,
        *,
        severity: str = "INFO",
        payload: Optional[Dict[str, Any]] = None,
    ) -> ControlPlaneEvent:
        event = ControlPlaneEvent(
            event_id=f"cpevt_{uuid.uuid4().hex}",
            event_type=event_type,
            message=message,
            severity=severity,
            payload=payload or {},
        )

        self.events.append(event)

        if len(self.events) > 10000:
            self.events = self.events[-10000:]

        return event

    def _safe_call(
        self,
        fn: Any,
        *args: Any,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        try:
            result = fn(*args, **kwargs)
            return self._as_dict(result)
        except Exception as exc:
            return {
                "status": "ERROR",
                "error": str(exc),
                "generated_at": utc_now_iso(),
            }

    @staticmethod
    def _safe_status(
        target: Any,
        method_name: str,
    ) -> Dict[str, Any]:
        if target is None:
            return {"status": "NOT_AVAILABLE"}

        method = getattr(target, method_name, None)

        if method is None:
            return {"status": "METHOD_NOT_AVAILABLE"}

        try:
            result = method()

            if result is None:
                return {}

            if isinstance(result, dict):
                return result

            if hasattr(result, "as_dict"):
                return result.as_dict()

            if hasattr(result, "__dataclass_fields__"):
                return asdict(result)

            return {"value": str(result)}
        except Exception as exc:
            return {
                "status": "ERROR",
                "error": str(exc),
            }

    @staticmethod
    def _as_dict(value: Any) -> Dict[str, Any]:
        if value is None:
            return {}

        if isinstance(value, dict):
            return value

        if isinstance(value, list):
            return {"items": value}

        if hasattr(value, "as_dict"):
            return value.as_dict()

        if hasattr(value, "__dataclass_fields__"):
            return asdict(value)

        return {"value": str(value)}


def create_analytics_fabric_control_plane(
    *,
    command_processor: Optional[Any] = None,
    continuous_runtime_engine: Optional[Any] = None,
    autonomous_supervisor: Optional[Any] = None,
    runtime_controller: Optional[Any] = None,
    execution_orchestrator: Optional[Any] = None,
    forecasting_engine: Optional[Any] = None,
    optimizer: Optional[Any] = None,
    execution_planner: Optional[Any] = None,
    governor: Optional[Any] = None,
    persistence_engine: Optional[Any] = None,
    snapshot_scheduler: Optional[Any] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> AnalyticsFabricControlPlane:
    return AnalyticsFabricControlPlane(
        command_processor=command_processor,
        continuous_runtime_engine=continuous_runtime_engine,
        autonomous_supervisor=autonomous_supervisor,
        runtime_controller=runtime_controller,
        execution_orchestrator=execution_orchestrator,
        forecasting_engine=forecasting_engine,
        optimizer=optimizer,
        execution_planner=execution_planner,
        governor=governor,
        persistence_engine=persistence_engine,
        snapshot_scheduler=snapshot_scheduler,
        metadata=metadata,
    )