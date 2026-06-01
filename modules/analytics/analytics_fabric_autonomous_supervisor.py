"""
modules/analytics/analytics_fabric_autonomous_supervisor.py
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


class SupervisorState(str, Enum):
    INITIALIZED = "INITIALIZED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"
    DEGRADED = "DEGRADED"
    RECOVERING = "RECOVERING"
    FAILED = "FAILED"


class SupervisorDecisionType(str, Enum):
    START_RUNTIME = "START_RUNTIME"
    PAUSE_RUNTIME = "PAUSE_RUNTIME"
    RESUME_RUNTIME = "RESUME_RUNTIME"
    RUN_AUTONOMOUS_CYCLE = "RUN_AUTONOMOUS_CYCLE"
    RUN_FORECASTING = "RUN_FORECASTING"
    RUN_OPTIMIZATION = "RUN_OPTIMIZATION"
    RUN_PLANNING = "RUN_PLANNING"
    RUN_EXECUTION = "RUN_EXECUTION"
    RUN_RECOVERY = "RUN_RECOVERY"
    CREATE_SNAPSHOT = "CREATE_SNAPSHOT"
    ENFORCE_GOVERNANCE = "ENFORCE_GOVERNANCE"
    DETECT_INCIDENTS = "DETECT_INCIDENTS"
    NOOP = "NOOP"


class SupervisorSeverity(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class SupervisorPolicy:
    policy_id: str = field(default_factory=lambda: f"sup_policy_{uuid.uuid4().hex}")
    enabled: bool = True

    autonomous_mode_enabled: bool = True
    allow_runtime_start: bool = True
    allow_runtime_pause: bool = True
    allow_recovery_automation: bool = True
    allow_snapshot_creation: bool = True
    allow_governance_enforcement: bool = True

    forecast_interval_seconds: int = 300
    optimization_interval_seconds: int = 600
    planning_interval_seconds: int = 600
    execution_interval_seconds: int = 900
    autonomous_cycle_interval_seconds: int = 900
    recovery_interval_seconds: int = 300
    snapshot_interval_seconds: int = 900

    min_health_score: float = 70.0
    min_readiness_score: float = 70.0
    critical_health_score: float = 50.0
    critical_readiness_score: float = 50.0

    max_failed_cycles_before_degraded: int = 3
    max_failed_cycles_before_pause: int = 5

    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SupervisorCycleSchedule:
    name: str
    interval_seconds: int
    last_run_at: Optional[str] = None
    next_run_at: Optional[str] = None
    enabled: bool = True

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SupervisorDecision:
    decision_id: str
    decision_type: str
    severity: str
    reason: str
    approved: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    generated_at: str = field(default_factory=utc_now_iso)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SupervisorIncident:
    incident_id: str
    incident_type: str
    severity: str
    description: str
    status: str = "OPEN"
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    resolved_at: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SupervisorCycleResult:
    cycle_id: str
    cycle_type: str
    status: str
    started_at: str
    completed_at: str
    runtime_ms: float
    result: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SupervisorMetrics:
    supervisor_cycles: int = 0
    autonomous_cycles: int = 0
    forecast_cycles: int = 0
    optimization_cycles: int = 0
    planning_cycles: int = 0
    execution_cycles: int = 0
    recovery_cycles: int = 0
    snapshot_cycles: int = 0
    failed_cycles: int = 0
    decisions_generated: int = 0
    incidents_detected: int = 0
    recoveries_triggered: int = 0
    governance_enforcements: int = 0
    started_at: Optional[str] = None
    last_cycle_at: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SupervisorSnapshot:
    snapshot_id: str
    state: str
    policy: Dict[str, Any]
    schedules: List[Dict[str, Any]]
    metrics: Dict[str, Any]
    runtime_status: Dict[str, Any]
    decisions: List[Dict[str, Any]]
    incidents: List[Dict[str, Any]]
    generated_at: str = field(default_factory=utc_now_iso)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AnalyticsFabricAutonomousSupervisor:
    """
    Continuous autonomous supervisor for the Analytics Fabric Runtime Controller.

    This layer coordinates scheduled cycles, decision-making, incident detection,
    recovery automation, governance enforcement, and snapshot creation.

    It does not run in a background thread. It exposes deterministic cycle methods
    that can be called by Streamlit, CLI scripts, schedulers, or service workers.
    """

    def __init__(
        self,
        *,
        runtime_controller: Optional[Any] = None,
        execution_governor: Optional[Any] = None,
        persistence_engine: Optional[Any] = None,
        snapshot_scheduler: Optional[Any] = None,
        policy: Optional[SupervisorPolicy] = None,
    ) -> None:
        self.runtime_controller = runtime_controller
        self.execution_governor = execution_governor
        self.persistence_engine = persistence_engine
        self.snapshot_scheduler = snapshot_scheduler
        self.policy = policy or SupervisorPolicy()

        self.state = SupervisorState.INITIALIZED.value
        self.metrics = SupervisorMetrics()
        self.decisions: List[SupervisorDecision] = []
        self.incidents: List[SupervisorIncident] = []
        self.cycle_history: List[SupervisorCycleResult] = []
        self.snapshots: List[SupervisorSnapshot] = []

        self.schedules: Dict[str, SupervisorCycleSchedule] = {}
        self._initialize_schedules()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start_supervisor(self) -> Dict[str, Any]:
        if not self.policy.enabled:
            self.state = SupervisorState.STOPPED.value
            return self.supervisor_status()

        self.state = SupervisorState.RUNNING.value
        self.metrics.started_at = self.metrics.started_at or utc_now_iso()

        if self.runtime_controller is not None and self.policy.allow_runtime_start:
            try:
                self.runtime_controller.start_runtime()
                self._decision(
                    SupervisorDecisionType.START_RUNTIME.value,
                    SupervisorSeverity.INFO.value,
                    "Runtime start requested by autonomous supervisor.",
                )
            except Exception as exc:
                self._incident(
                    "RUNTIME_START_FAILED",
                    SupervisorSeverity.HIGH.value,
                    str(exc),
                )

        return self.supervisor_status()

    def stop_supervisor(self) -> Dict[str, Any]:
        self.state = SupervisorState.STOPPED.value
        return self.supervisor_status()

    def pause_supervisor(self) -> Dict[str, Any]:
        self.state = SupervisorState.PAUSED.value

        if self.runtime_controller is not None and self.policy.allow_runtime_pause:
            try:
                self.runtime_controller.pause_runtime()
                self._decision(
                    SupervisorDecisionType.PAUSE_RUNTIME.value,
                    SupervisorSeverity.INFO.value,
                    "Runtime pause requested by autonomous supervisor.",
                )
            except Exception as exc:
                self._incident(
                    "RUNTIME_PAUSE_FAILED",
                    SupervisorSeverity.MEDIUM.value,
                    str(exc),
                )

        return self.supervisor_status()

    def resume_supervisor(self) -> Dict[str, Any]:
        self.state = SupervisorState.RUNNING.value

        if self.runtime_controller is not None:
            try:
                self.runtime_controller.resume_runtime()
                self._decision(
                    SupervisorDecisionType.RESUME_RUNTIME.value,
                    SupervisorSeverity.INFO.value,
                    "Runtime resume requested by autonomous supervisor.",
                )
            except Exception as exc:
                self._incident(
                    "RUNTIME_RESUME_FAILED",
                    SupervisorSeverity.MEDIUM.value,
                    str(exc),
                )

        return self.supervisor_status()

    # ------------------------------------------------------------------
    # Main Cycles
    # ------------------------------------------------------------------

    def run_supervisor_cycle(self, *, force: bool = False) -> Dict[str, Any]:
        started = time.perf_counter()
        started_at = utc_now_iso()

        if self.state in {SupervisorState.STOPPED.value, SupervisorState.PAUSED.value}:
            result = {
                "status": "SKIPPED",
                "reason": f"Supervisor state is {self.state}.",
                "generated_at": utc_now_iso(),
            }
            return result

        if not self.policy.enabled:
            return {
                "status": "DISABLED",
                "generated_at": utc_now_iso(),
            }

        self.metrics.supervisor_cycles += 1
        self.metrics.last_cycle_at = utc_now_iso()

        cycle_results: Dict[str, Any] = {}

        try:
            cycle_results["health_enforcement"] = self.enforce_health()
            cycle_results["incident_detection"] = self.detect_incidents()
            cycle_results["governance_enforcement"] = self.enforce_governance()

            for cycle_name in [
                "forecast",
                "optimization",
                "planning",
                "execution",
                "autonomous",
                "recovery",
                "snapshot",
            ]:
                schedule = self.schedules.get(cycle_name)

                if force or self._schedule_due(schedule):
                    cycle_results[cycle_name] = self.run_named_cycle(cycle_name)
                    self._advance_schedule(cycle_name)

            runtime_ms = round((time.perf_counter() - started) * 1000.0, 4)

            result = SupervisorCycleResult(
                cycle_id=f"sup_cycle_{uuid.uuid4().hex}",
                cycle_type="SUPERVISOR",
                status="SUCCESS",
                started_at=started_at,
                completed_at=utc_now_iso(),
                runtime_ms=runtime_ms,
                result=cycle_results,
            )

            self.cycle_history.append(result)
            self._trim_history()

            return result.as_dict()

        except Exception as exc:
            self.metrics.failed_cycles += 1

            if self.metrics.failed_cycles >= self.policy.max_failed_cycles_before_pause:
                self.state = SupervisorState.PAUSED.value
            elif self.metrics.failed_cycles >= self.policy.max_failed_cycles_before_degraded:
                self.state = SupervisorState.DEGRADED.value

            incident = self._incident(
                "SUPERVISOR_CYCLE_FAILED",
                SupervisorSeverity.HIGH.value,
                str(exc),
            )

            runtime_ms = round((time.perf_counter() - started) * 1000.0, 4)

            result = SupervisorCycleResult(
                cycle_id=f"sup_cycle_{uuid.uuid4().hex}",
                cycle_type="SUPERVISOR",
                status="FAILED",
                started_at=started_at,
                completed_at=utc_now_iso(),
                runtime_ms=runtime_ms,
                result={"incident": incident.as_dict()},
                error=str(exc),
            )

            self.cycle_history.append(result)
            self._trim_history()

            return result.as_dict()

    def run_named_cycle(self, cycle_name: str) -> Dict[str, Any]:
        cycle_name = cycle_name.lower().strip()

        if cycle_name == "forecast":
            return self.run_forecasting_cycle()

        if cycle_name == "optimization":
            return self.run_optimization_cycle()

        if cycle_name == "planning":
            return self.run_planning_cycle()

        if cycle_name == "execution":
            return self.run_execution_cycle()

        if cycle_name == "autonomous":
            return self.run_autonomous_cycle()

        if cycle_name == "recovery":
            return self.run_recovery_cycle()

        if cycle_name == "snapshot":
            return self.run_snapshot_cycle()

        return {
            "status": "UNKNOWN_CYCLE",
            "cycle_name": cycle_name,
            "generated_at": utc_now_iso(),
        }

    def run_forecasting_cycle(self) -> Dict[str, Any]:
        self.metrics.forecast_cycles += 1
        self._decision(
            SupervisorDecisionType.RUN_FORECASTING.value,
            SupervisorSeverity.INFO.value,
            "Forecasting cycle selected by supervisor.",
        )

        if self.runtime_controller is None:
            return {"status": "NO_RUNTIME_CONTROLLER"}

        return self.runtime_controller.run_forecasting_cycle()

    def run_optimization_cycle(self) -> Dict[str, Any]:
        self.metrics.optimization_cycles += 1
        self._decision(
            SupervisorDecisionType.RUN_OPTIMIZATION.value,
            SupervisorSeverity.INFO.value,
            "Optimization cycle selected by supervisor.",
        )

        if self.runtime_controller is None:
            return {"status": "NO_RUNTIME_CONTROLLER"}

        return self.runtime_controller.run_optimization_cycle()

    def run_planning_cycle(self) -> Dict[str, Any]:
        self.metrics.planning_cycles += 1
        self._decision(
            SupervisorDecisionType.RUN_PLANNING.value,
            SupervisorSeverity.INFO.value,
            "Planning cycle selected by supervisor.",
        )

        if self.runtime_controller is None:
            return {"status": "NO_RUNTIME_CONTROLLER"}

        return self.runtime_controller.run_planning_cycle()

    def run_execution_cycle(self) -> Dict[str, Any]:
        self.metrics.execution_cycles += 1
        self._decision(
            SupervisorDecisionType.RUN_EXECUTION.value,
            SupervisorSeverity.INFO.value,
            "Execution cycle selected by supervisor.",
        )

        if self.runtime_controller is None:
            return {"status": "NO_RUNTIME_CONTROLLER"}

        return self.runtime_controller.run_execution_cycle()

    def run_autonomous_cycle(self) -> Dict[str, Any]:
        self.metrics.autonomous_cycles += 1
        self._decision(
            SupervisorDecisionType.RUN_AUTONOMOUS_CYCLE.value,
            SupervisorSeverity.INFO.value,
            "Full autonomous runtime cycle selected by supervisor.",
        )

        if self.runtime_controller is None:
            return {"status": "NO_RUNTIME_CONTROLLER"}

        return self.runtime_controller.run_autonomous_cycle()

    def run_recovery_cycle(self) -> Dict[str, Any]:
        self.metrics.recovery_cycles += 1
        self.metrics.recoveries_triggered += 1
        self.state = SupervisorState.RECOVERING.value

        self._decision(
            SupervisorDecisionType.RUN_RECOVERY.value,
            SupervisorSeverity.HIGH.value,
            "Recovery cycle selected by supervisor.",
        )

        if self.runtime_controller is None:
            self.state = SupervisorState.RUNNING.value
            return {"status": "NO_RUNTIME_CONTROLLER"}

        result = self.runtime_controller.run_recovery_cycle()
        self.state = SupervisorState.RUNNING.value

        return {
            "status": "RECOVERY_COMPLETED",
            "result": result,
            "generated_at": utc_now_iso(),
        }

    def run_snapshot_cycle(self) -> Dict[str, Any]:
        self.metrics.snapshot_cycles += 1

        self._decision(
            SupervisorDecisionType.CREATE_SNAPSHOT.value,
            SupervisorSeverity.INFO.value,
            "Snapshot cycle selected by supervisor.",
        )

        payload = self.supervisor_snapshot()

        if self.snapshot_scheduler is not None:
            try:
                scheduler_result = self.snapshot_scheduler.run_snapshot_cycle()
            except Exception as exc:
                scheduler_result = {
                    "status": "SNAPSHOT_SCHEDULER_FAILED",
                    "error": str(exc),
                }
        else:
            scheduler_result = {"status": "NO_SNAPSHOT_SCHEDULER"}

        return {
            "status": "SNAPSHOT_COMPLETED",
            "supervisor_snapshot": payload.as_dict(),
            "scheduler_result": scheduler_result,
            "generated_at": utc_now_iso(),
        }

    # ------------------------------------------------------------------
    # Decision / Enforcement
    # ------------------------------------------------------------------

    def detect_incidents(self) -> Dict[str, Any]:
        self._decision(
            SupervisorDecisionType.DETECT_INCIDENTS.value,
            SupervisorSeverity.INFO.value,
            "Supervisor incident detection executed.",
        )

        detected = []

        if self.runtime_controller is None:
            return {
                "status": "NO_RUNTIME_CONTROLLER",
                "detected": detected,
            }

        detectors = [
            ("runtime_failure", self.runtime_controller.detect_runtime_failure),
            ("capacity_pressure", self.runtime_controller.detect_capacity_pressure),
            ("provider_pressure", self.runtime_controller.detect_provider_pressure),
            ("queue_pressure", self.runtime_controller.detect_queue_pressure),
            ("governance_pressure", self.runtime_controller.detect_governance_pressure),
        ]

        for detector_name, detector in detectors:
            try:
                incident = detector()
                if incident:
                    incident_dict = self._as_dict(incident)
                    detected.append(incident_dict)
                    self._incident(
                        incident_dict.get("incident_type", detector_name.upper()),
                        incident_dict.get("severity", SupervisorSeverity.MEDIUM.value),
                        incident_dict.get("description", f"{detector_name} detected."),
                        metadata={"runtime_incident": incident_dict},
                    )
            except Exception as exc:
                self._incident(
                    f"{detector_name.upper()}_DETECTION_FAILED",
                    SupervisorSeverity.MEDIUM.value,
                    str(exc),
                )

        return {
            "status": "COMPLETED",
            "detected": detected,
            "count": len(detected),
            "generated_at": utc_now_iso(),
        }

    def enforce_health(self) -> Dict[str, Any]:
        health = self._runtime_health()

        health_score = float(health.get("health_score", 100.0) or 100.0)
        readiness_score = float(health.get("readiness_score", 100.0) or 100.0)

        actions = []

        if health_score < self.policy.critical_health_score:
            self.state = SupervisorState.DEGRADED.value
            actions.append("CRITICAL_HEALTH_DEGRADED")
            self._incident(
                "CRITICAL_HEALTH_DEGRADED",
                SupervisorSeverity.CRITICAL.value,
                "Runtime health score is below critical threshold.",
                metadata={"health": health},
            )

            if self.policy.allow_recovery_automation:
                actions.append("RUN_RECOVERY")
                self.run_recovery_cycle()

        elif health_score < self.policy.min_health_score:
            self.state = SupervisorState.DEGRADED.value
            actions.append("HEALTH_DEGRADED")
            self._incident(
                "HEALTH_DEGRADED",
                SupervisorSeverity.HIGH.value,
                "Runtime health score is below minimum threshold.",
                metadata={"health": health},
            )

        if readiness_score < self.policy.critical_readiness_score:
            actions.append("CRITICAL_READINESS_DEGRADED")
            self._incident(
                "CRITICAL_READINESS_DEGRADED",
                SupervisorSeverity.CRITICAL.value,
                "Runtime readiness score is below critical threshold.",
                metadata={"health": health},
            )

        elif readiness_score < self.policy.min_readiness_score:
            actions.append("READINESS_DEGRADED")
            self._incident(
                "READINESS_DEGRADED",
                SupervisorSeverity.HIGH.value,
                "Runtime readiness score is below minimum threshold.",
                metadata={"health": health},
            )

        if not actions and self.state == SupervisorState.DEGRADED.value:
            self.state = SupervisorState.RUNNING.value

        return {
            "status": "COMPLETED",
            "actions": actions,
            "health": health,
            "generated_at": utc_now_iso(),
        }

    def enforce_governance(self) -> Dict[str, Any]:
        if not self.policy.allow_governance_enforcement:
            return {
                "status": "DISABLED",
                "generated_at": utc_now_iso(),
            }

        self.metrics.governance_enforcements += 1

        self._decision(
            SupervisorDecisionType.ENFORCE_GOVERNANCE.value,
            SupervisorSeverity.INFO.value,
            "Governance enforcement cycle executed.",
        )

        if self.execution_governor is None:
            return {
                "status": "NO_GOVERNOR",
                "generated_at": utc_now_iso(),
            }

        try:
            summary = self.execution_governor.governance_summary()
            return {
                "status": "COMPLETED",
                "governance_summary": summary,
                "generated_at": utc_now_iso(),
            }
        except Exception as exc:
            self._incident(
                "GOVERNANCE_ENFORCEMENT_FAILED",
                SupervisorSeverity.HIGH.value,
                str(exc),
            )
            return {
                "status": "FAILED",
                "error": str(exc),
                "generated_at": utc_now_iso(),
            }

    # ------------------------------------------------------------------
    # Scheduling
    # ------------------------------------------------------------------

    def register_cycle_schedule(
        self,
        name: str,
        interval_seconds: int,
        *,
        enabled: bool = True,
    ) -> SupervisorCycleSchedule:
        schedule = SupervisorCycleSchedule(
            name=name,
            interval_seconds=max(1, int(interval_seconds)),
            enabled=enabled,
            next_run_at=self._next_run_iso(interval_seconds),
        )

        self.schedules[name] = schedule
        return schedule

    def pause_cycle_schedule(self, name: str) -> bool:
        schedule = self.schedules.get(name)
        if not schedule:
            return False
        schedule.enabled = False
        return True

    def resume_cycle_schedule(self, name: str) -> bool:
        schedule = self.schedules.get(name)
        if not schedule:
            return False
        schedule.enabled = True
        if not schedule.next_run_at:
            schedule.next_run_at = self._next_run_iso(schedule.interval_seconds)
        return True

    def update_cycle_schedule(self, name: str, interval_seconds: int) -> bool:
        schedule = self.schedules.get(name)
        if not schedule:
            return False
        schedule.interval_seconds = max(1, int(interval_seconds))
        schedule.next_run_at = self._next_run_iso(schedule.interval_seconds)
        return True

    def list_cycle_schedules(self) -> List[Dict[str, Any]]:
        return [schedule.as_dict() for schedule in self.schedules.values()]

    # ------------------------------------------------------------------
    # Snapshot / Status
    # ------------------------------------------------------------------

    def supervisor_snapshot(self) -> SupervisorSnapshot:
        snapshot = SupervisorSnapshot(
            snapshot_id=f"sup_snap_{uuid.uuid4().hex}",
            state=self.state,
            policy=asdict(self.policy),
            schedules=self.list_cycle_schedules(),
            metrics=self.metrics.as_dict(),
            runtime_status=self._runtime_status(),
            decisions=[d.as_dict() for d in self.decisions[-100:]],
            incidents=[i.as_dict() for i in self.incidents[-100:]],
        )

        self.snapshots.append(snapshot)

        if len(self.snapshots) > 1000:
            self.snapshots = self.snapshots[-1000:]

        self._persist_snapshot(snapshot)

        return snapshot

    def supervisor_status(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "policy_enabled": self.policy.enabled,
            "autonomous_mode_enabled": self.policy.autonomous_mode_enabled,
            "metrics": self.metrics.as_dict(),
            "runtime_status": self._runtime_status(),
            "open_incidents": len([i for i in self.incidents if i.status == "OPEN"]),
            "decisions": len(self.decisions),
            "cycles": len(self.cycle_history),
            "snapshots": len(self.snapshots),
            "generated_at": utc_now_iso(),
        }

    def supervisor_health(self) -> Dict[str, Any]:
        open_incidents = len([i for i in self.incidents if i.status == "OPEN"])
        failed_cycles = self.metrics.failed_cycles

        score = 100.0
        score -= min(40.0, open_incidents * 5.0)
        score -= min(40.0, failed_cycles * 5.0)

        if self.state == SupervisorState.DEGRADED.value:
            score -= 20.0
        elif self.state == SupervisorState.FAILED.value:
            score -= 50.0
        elif self.state == SupervisorState.PAUSED.value:
            score -= 10.0
        elif self.state == SupervisorState.STOPPED.value:
            score -= 20.0

        score = max(0.0, min(100.0, score))

        return {
            "supervisor_health_score": round(score, 2),
            "state": self.state,
            "open_incidents": open_incidents,
            "failed_cycles": failed_cycles,
            "generated_at": utc_now_iso(),
        }

    def decision_history(self, limit: int = 1000) -> List[Dict[str, Any]]:
        return [d.as_dict() for d in self.decisions[-limit:]]

    def incident_history(self, limit: int = 1000) -> List[Dict[str, Any]]:
        return [i.as_dict() for i in self.incidents[-limit:]]

    def cycle_results(self, limit: int = 1000) -> List[Dict[str, Any]]:
        return [c.as_dict() for c in self.cycle_history[-limit:]]

    def snapshot_history(self, limit: int = 1000) -> List[Dict[str, Any]]:
        return [s.as_dict() for s in self.snapshots[-limit:]]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _initialize_schedules(self) -> None:
        self.register_cycle_schedule(
            "forecast",
            self.policy.forecast_interval_seconds,
        )
        self.register_cycle_schedule(
            "optimization",
            self.policy.optimization_interval_seconds,
        )
        self.register_cycle_schedule(
            "planning",
            self.policy.planning_interval_seconds,
        )
        self.register_cycle_schedule(
            "execution",
            self.policy.execution_interval_seconds,
        )
        self.register_cycle_schedule(
            "autonomous",
            self.policy.autonomous_cycle_interval_seconds,
        )
        self.register_cycle_schedule(
            "recovery",
            self.policy.recovery_interval_seconds,
        )
        self.register_cycle_schedule(
            "snapshot",
            self.policy.snapshot_interval_seconds,
        )

    def _schedule_due(self, schedule: Optional[SupervisorCycleSchedule]) -> bool:
        if schedule is None or not schedule.enabled:
            return False

        if not schedule.next_run_at:
            return True

        try:
            return datetime.fromisoformat(schedule.next_run_at) <= datetime.now(timezone.utc)
        except Exception:
            return True

    def _advance_schedule(self, name: str) -> None:
        schedule = self.schedules.get(name)
        if not schedule:
            return

        schedule.last_run_at = utc_now_iso()
        schedule.next_run_at = self._next_run_iso(schedule.interval_seconds)

    def _next_run_iso(self, interval_seconds: int) -> str:
        return datetime.fromtimestamp(
            time.time() + max(1, int(interval_seconds)),
            tz=timezone.utc,
        ).isoformat()

    def _decision(
        self,
        decision_type: str,
        severity: str,
        reason: str,
        *,
        approved: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SupervisorDecision:
        decision = SupervisorDecision(
            decision_id=f"sup_decision_{uuid.uuid4().hex}",
            decision_type=decision_type,
            severity=severity,
            reason=reason,
            approved=approved,
            metadata=metadata or {},
        )

        self.decisions.append(decision)
        self.metrics.decisions_generated += 1

        if len(self.decisions) > 10000:
            self.decisions = self.decisions[-10000:]

        return decision

    def _incident(
        self,
        incident_type: str,
        severity: str,
        description: str,
        *,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SupervisorIncident:
        incident = SupervisorIncident(
            incident_id=f"sup_incident_{uuid.uuid4().hex}",
            incident_type=incident_type,
            severity=severity,
            description=description,
            metadata=metadata or {},
        )

        self.incidents.append(incident)
        self.metrics.incidents_detected += 1

        if len(self.incidents) > 10000:
            self.incidents = self.incidents[-10000:]

        self._persist_incident(incident)

        return incident

    def _runtime_status(self) -> Dict[str, Any]:
        if self.runtime_controller is None:
            return {"status": "NO_RUNTIME_CONTROLLER"}

        try:
            return self.runtime_controller.runtime_status()
        except Exception as exc:
            return {"status": "ERROR", "error": str(exc)}

    def _runtime_health(self) -> Dict[str, Any]:
        if self.runtime_controller is None:
            return {
                "health_score": 100.0,
                "readiness_score": 100.0,
            }

        try:
            return self.runtime_controller.runtime_health()
        except Exception:
            return {
                "health_score": 0.0,
                "readiness_score": 0.0,
            }

    def _persist_snapshot(self, snapshot: SupervisorSnapshot) -> None:
        if self.persistence_engine is None:
            return

        try:
            self.persistence_engine.save_executive_snapshot(
                snapshot_name="autonomous_supervisor_snapshot",
                payload=snapshot.as_dict(),
            )
        except Exception:
            pass

    def _persist_incident(self, incident: SupervisorIncident) -> None:
        if self.persistence_engine is None:
            return

        try:
            self.persistence_engine.save_governance_decision(
                decision_type="autonomous_supervisor_incident",
                severity=incident.severity,
                payload=incident.as_dict(),
            )
        except Exception:
            pass

    def _trim_history(self) -> None:
        if len(self.cycle_history) > 10000:
            self.cycle_history = self.cycle_history[-10000:]

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
        return {"value": str(value)}


def create_analytics_fabric_autonomous_supervisor(
    *,
    runtime_controller: Optional[Any] = None,
    execution_governor: Optional[Any] = None,
    persistence_engine: Optional[Any] = None,
    snapshot_scheduler: Optional[Any] = None,
    policy: Optional[SupervisorPolicy] = None,
) -> AnalyticsFabricAutonomousSupervisor:
    return AnalyticsFabricAutonomousSupervisor(
        runtime_controller=runtime_controller,
        execution_governor=execution_governor,
        persistence_engine=persistence_engine,
        snapshot_scheduler=snapshot_scheduler,
        policy=policy,
    )