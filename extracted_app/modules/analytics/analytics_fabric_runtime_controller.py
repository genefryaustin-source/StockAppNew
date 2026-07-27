"""
modules/analytics/analytics_fabric_runtime_controller.py
"""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def utc_now_iso() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


class RuntimeState(str, Enum):
    INITIALIZING = "INITIALIZING"
    READY = "READY"
    OPTIMIZING = "OPTIMIZING"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    DEGRADED = "DEGRADED"
    RECOVERING = "RECOVERING"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"
    FAILED = "FAILED"


@dataclass
class FabricRuntimeHealth:
    health_score: float = 100.0
    capacity_score: float = 100.0
    provider_score: float = 100.0
    governance_score: float = 100.0
    queue_score: float = 100.0
    readiness_score: float = 100.0
    updated_at: str = field(
        default_factory=utc_now_iso
    )

    def as_dict(self):
        return asdict(self)


@dataclass
class FabricRuntimeMetrics:
    forecast_cycles: int = 0
    optimization_cycles: int = 0
    planning_cycles: int = 0
    execution_cycles: int = 0
    autonomous_cycles: int = 0
    recovery_cycles: int = 0
    runtime_uptime_seconds: float = 0.0
    runtime_health_score: float = 100.0
    runtime_readiness_score: float = 100.0

    def as_dict(self):
        return asdict(self)


@dataclass
class FabricRuntimeDecision:
    decision_id: str
    decision_type: str
    decision: str
    reason: str
    created_at: str = field(
        default_factory=utc_now_iso
    )

    def as_dict(self):
        return asdict(self)


@dataclass
class FabricRuntimeIncident:
    incident_id: str
    incident_type: str
    severity: str
    description: str
    status: str = "OPEN"
    created_at: str = field(
        default_factory=utc_now_iso
    )

    def as_dict(self):
        return asdict(self)


@dataclass
class FabricRuntimeRecoveryPlan:
    recovery_id: str
    incident_id: str
    actions: List[str]
    status: str = "PENDING"
    created_at: str = field(
        default_factory=utc_now_iso
    )

    def as_dict(self):
        return asdict(self)


@dataclass
class FabricRuntimeSnapshot:
    snapshot_id: str
    runtime_state: str
    health: Dict[str, Any]
    metrics: Dict[str, Any]
    generated_at: str = field(
        default_factory=utc_now_iso
    )

    def as_dict(self):
        return asdict(self)


@dataclass
class FabricRuntimeState:
    state: str = RuntimeState.INITIALIZING.value
    started_at: Optional[str] = None
    updated_at: str = field(
        default_factory=utc_now_iso
    )

    def as_dict(self):
        return asdict(self)


class AnalyticsFabricRuntimeController:
    """
    Top-level Analytics Fabric supervisory controller.
    """

    def __init__(
        self,
        forecasting_engine=None,
        optimizer=None,
        planner=None,
        orchestrator=None,
        governor=None,
        global_planner=None,
        worker_capacity_model=None,
        provider_cost_intelligence=None,
        persistence_engine=None,
    ):
        self.forecasting_engine = forecasting_engine
        self.optimizer = optimizer
        self.planner = planner
        self.orchestrator = orchestrator
        self.governor = governor
        self.global_planner = global_planner
        self.worker_capacity_model = (
            worker_capacity_model
        )
        self.provider_cost_intelligence = (
            provider_cost_intelligence
        )
        self.persistence_engine = (
            persistence_engine
        )

        self.runtime_state = (
            FabricRuntimeState()
        )

        self.runtime_health_obj = (
            FabricRuntimeHealth()
        )

        self.runtime_metrics_obj = (
            FabricRuntimeMetrics()
        )

        self.decisions: List[
            FabricRuntimeDecision
        ] = []

        self.incidents: List[
            FabricRuntimeIncident
        ] = []

        self.recovery_plans: List[
            FabricRuntimeRecoveryPlan
        ] = []

        self.snapshots: List[
            FabricRuntimeSnapshot
        ] = []

        self.start_time = None

    def initialize_runtime(self):
        self.runtime_state.state = (
            RuntimeState.READY.value
        )

        self.runtime_state.updated_at = (
            utc_now_iso()
        )

        self.start_time = time.time()

        return self.runtime_status()

    def start_runtime(self):
        if self.start_time is None:
            self.start_time = time.time()

        self.runtime_state.state = (
            RuntimeState.READY.value
        )

        self.runtime_state.started_at = (
            utc_now_iso()
        )

        return self.runtime_status()

    def stop_runtime(self):
        self.runtime_state.state = (
            RuntimeState.STOPPED.value
        )

        return self.runtime_status()

    def pause_runtime(self):
        self.runtime_state.state = (
            RuntimeState.PAUSED.value
        )

        return self.runtime_status()

    def resume_runtime(self):
        self.runtime_state.state = (
            RuntimeState.READY.value
        )

        return self.runtime_status()

    def runtime_status(self):
        return {
            "state":
                self.runtime_state.state,
            "health":
                self.runtime_health(),
            "metrics":
                self.runtime_metrics(),
        }

    def runtime_summary(self):
        return {
            "state":
                self.runtime_state.state,
            "health_score":
                self.runtime_health_obj.health_score,
            "readiness_score":
                self.runtime_health_obj.readiness_score,
            "decisions":
                len(self.decisions),
            "incidents":
                len(self.incidents),
            "snapshots":
                len(self.snapshots),
            "metrics":
                self.runtime_metrics(),
        }

    def runtime_health(self):
        return (
            self.runtime_health_obj
            .as_dict()
        )

    def runtime_metrics(self):
        if self.start_time:

            self.runtime_metrics_obj.runtime_uptime_seconds = (
                round(
                    time.time()
                    - self.start_time,
                    2,
                )
            )

        self.runtime_metrics_obj.runtime_health_score = (
            self.runtime_health_obj
            .health_score
        )

        self.runtime_metrics_obj.runtime_readiness_score = (
            self.runtime_health_obj
            .readiness_score
        )

        return (
            self.runtime_metrics_obj
            .as_dict()
        )

    def runtime_snapshot(self):
        snapshot = (
            FabricRuntimeSnapshot(
                snapshot_id=
                f"rtsnap_{uuid.uuid4().hex}",
                runtime_state=
                self.runtime_state.state,
                health=
                self.runtime_health(),
                metrics=
                self.runtime_metrics(),
            )
        )

        self.snapshots.append(
            snapshot
        )

        self.save_runtime_snapshot(
            snapshot
        )

        return snapshot

    def runtime_decisions(self):
        return [
            d.as_dict()
            for d in self.decisions
        ]

    def runtime_incidents(self):
        return [
            i.as_dict()
            for i in self.incidents
        ]

    def run_forecasting_cycle(self):
        self.runtime_metrics_obj.forecast_cycles += 1

        self._decision(
            "FORECAST",
            "Forecast cycle executed",
        )

        return {
            "cycle":
                self.runtime_metrics_obj.forecast_cycles,
            "status":
                "SUCCESS",
        }

    def run_optimization_cycle(self):
        self.runtime_state.state = (
            RuntimeState.OPTIMIZING.value
        )

        self.runtime_metrics_obj.optimization_cycles += 1

        self._decision(
            "OPTIMIZATION",
            "Optimization cycle executed",
        )

        return {
            "cycle":
                self.runtime_metrics_obj.optimization_cycles,
            "status":
                "SUCCESS",
        }

    def run_planning_cycle(self):
        self.runtime_state.state = (
            RuntimeState.PLANNING.value
        )

        self.runtime_metrics_obj.planning_cycles += 1

        self._decision(
            "PLANNING",
            "Planning cycle executed",
        )

        return {
            "cycle":
                self.runtime_metrics_obj.planning_cycles,
            "status":
                "SUCCESS",
        }

    def run_execution_cycle(self):
        self.runtime_state.state = (
            RuntimeState.EXECUTING.value
        )

        self.runtime_metrics_obj.execution_cycles += 1

        self._decision(
            "EXECUTION",
            "Execution cycle executed",
        )

        return {
            "cycle":
                self.runtime_metrics_obj.execution_cycles,
            "status":
                "SUCCESS",
        }

    def run_autonomous_cycle(self):
        self.runtime_metrics_obj.autonomous_cycles += 1

        forecast = (
            self.run_forecasting_cycle()
        )

        optimization = (
            self.run_optimization_cycle()
        )

        planning = (
            self.run_planning_cycle()
        )

        execution = (
            self.run_execution_cycle()
        )

        snapshot = (
            self.runtime_snapshot()
        )

        self.runtime_state.state = (
            RuntimeState.READY.value
        )

        return {
            "forecast":
                forecast,
            "optimization":
                optimization,
            "planning":
                planning,
            "execution":
                execution,
            "snapshot":
                snapshot.as_dict(),
        }

    def run_recovery_cycle(self):
        self.runtime_metrics_obj.recovery_cycles += 1

        self.runtime_state.state = (
            RuntimeState.RECOVERING.value
        )

        incidents = (
            self.runtime_incidents()
        )

        recovery_results = []

        for incident in incidents:

            plan = (
                self.create_recovery_plan(
                    incident
                )
            )

            recovery_results.append(
                self.execute_recovery_plan(
                    plan
                )
            )

        self.runtime_state.state = (
            RuntimeState.READY.value
        )

        return recovery_results

    def detect_runtime_failure(self):
        if (
            self.runtime_health_obj
            .health_score < 50
        ):
            return self._incident(
                "RUNTIME_FAILURE",
                "CRITICAL",
                "Runtime health below threshold",
            )

        return None

    def detect_capacity_pressure(self):
        if (
            self.runtime_health_obj
            .capacity_score < 70
        ):
            return self._incident(
                "CAPACITY_PRESSURE",
                "HIGH",
                "Capacity pressure detected",
            )

        return None

    def detect_provider_pressure(self):
        if (
            self.runtime_health_obj
            .provider_score < 70
        ):
            return self._incident(
                "PROVIDER_PRESSURE",
                "HIGH",
                "Provider pressure detected",
            )

        return None

    def detect_queue_pressure(self):
        if (
            self.runtime_health_obj
            .queue_score < 70
        ):
            return self._incident(
                "QUEUE_PRESSURE",
                "HIGH",
                "Queue pressure detected",
            )

        return None

    def detect_governance_pressure(self):
        if (
            self.runtime_health_obj
            .governance_score < 70
        ):
            return self._incident(
                "GOVERNANCE_PRESSURE",
                "HIGH",
                "Governance pressure detected",
            )

        return None

    def create_recovery_plan(
        self,
        incident,
    ):
        if isinstance(
            incident,
            dict,
        ):
            incident_id = (
                incident[
                    "incident_id"
                ]
            )
        else:
            incident_id = (
                incident.incident_id
            )

        plan = (
            FabricRuntimeRecoveryPlan(
                recovery_id=
                f"recovery_{uuid.uuid4().hex}",
                incident_id=
                incident_id,
                actions=[
                    "Evaluate",
                    "Recover",
                    "Validate",
                    "Resume",
                ],
            )
        )

        self.recovery_plans.append(
            plan
        )

        return plan

    def execute_recovery_plan(
        self,
        plan,
    ):
        plan.status = "COMPLETED"

        return {
            "recovery_id":
                plan.recovery_id,
            "status":
                plan.status,
        }

    def save_runtime_snapshot(
        self,
        snapshot,
    ):
        if (
            not self.persistence_engine
        ):
            return

        try:
            self.persistence_engine.save_executive_snapshot(
                snapshot_name=
                "runtime_snapshot",
                payload=
                snapshot.as_dict(),
            )
        except Exception:
            pass

    def save_runtime_decision(
        self,
        decision,
    ):
        if (
            not self.persistence_engine
        ):
            return

        try:
            self.persistence_engine.save_governance_decision(
                decision_type=
                decision.decision_type,
                severity=
                "INFO",
                payload=
                decision.as_dict(),
            )
        except Exception:
            pass

    def save_runtime_incident(
        self,
        incident,
    ):
        if (
            not self.persistence_engine
        ):
            return

        try:
            self.persistence_engine.save_governance_decision(
                decision_type=
                "runtime_incident",
                severity=
                incident.severity,
                payload=
                incident.as_dict(),
            )
        except Exception:
            pass

    def save_runtime_metrics(self):
        if (
            not self.persistence_engine
        ):
            return

        try:
            self.persistence_engine.save_executive_snapshot(
                snapshot_name=
                "runtime_metrics",
                payload=
                self.runtime_metrics(),
            )
        except Exception:
            pass

    def _decision(
        self,
        decision_type,
        reason,
    ):
        decision = (
            FabricRuntimeDecision(
                decision_id=
                f"decision_{uuid.uuid4().hex}",
                decision_type=
                decision_type,
                decision=
                "EXECUTE",
                reason=
                reason,
            )
        )

        self.decisions.append(
            decision
        )

        self.save_runtime_decision(
            decision
        )

        return decision

    def _incident(
        self,
        incident_type,
        severity,
        description,
    ):
        incident = (
            FabricRuntimeIncident(
                incident_id=
                f"incident_{uuid.uuid4().hex}",
                incident_type=
                incident_type,
                severity=
                severity,
                description=
                description,
            )
        )

        self.incidents.append(
            incident
        )

        self.save_runtime_incident(
            incident
        )

        return incident