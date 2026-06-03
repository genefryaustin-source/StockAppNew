"""
modules/analytics/analytics_fabric_self_healing_engine.py
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


def clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 100.0,
) -> float:
    return max(minimum, min(maximum, float(value)))


class HealingActionType(str, Enum):
    NOOP = "NOOP"
    RESTART_COMPONENT = "RESTART_COMPONENT"
    REINITIALIZE_COMPONENT = "REINITIALIZE_COMPONENT"
    RUN_RECOVERY_CYCLE = "RUN_RECOVERY_CYCLE"
    CLEAR_QUEUE_BACKLOG = "CLEAR_QUEUE_BACKLOG"
    REFRESH_SNAPSHOT = "REFRESH_SNAPSHOT"
    REBUILD_RUNTIME_STATE = "REBUILD_RUNTIME_STATE"
    PAUSE_RUNTIME = "PAUSE_RUNTIME"
    RESUME_RUNTIME = "RESUME_RUNTIME"
    RESTART_RUNTIME = "RESTART_RUNTIME"
    RELOAD_CONTROL_PLANE = "RELOAD_CONTROL_PLANE"
    VALIDATE_HEALTH = "VALIDATE_HEALTH"
    ESCALATE_TO_OPERATOR = "ESCALATE_TO_OPERATOR"


class HealingActionStatus(str, Enum):
    PLANNED = "PLANNED"
    SKIPPED = "SKIPPED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ESCALATED = "ESCALATED"


class HealingSeverity(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class HealingMode(str, Enum):
    OBSERVE_ONLY = "OBSERVE_ONLY"
    ASSISTED = "ASSISTED"
    SUPERVISED_AUTONOMY = "SUPERVISED_AUTONOMY"
    FULL_AUTONOMY = "FULL_AUTONOMY"


@dataclass
class SelfHealingPolicy:
    policy_id: str = field(default_factory=lambda: f"healpol_{uuid.uuid4().hex}")
    name: str = "Default Analytics Fabric Self-Healing Policy"
    enabled: bool = True
    mode: str = HealingMode.SUPERVISED_AUTONOMY.value

    allow_runtime_restart: bool = False
    allow_component_reinitialize: bool = True
    allow_recovery_cycle: bool = True
    allow_snapshot_refresh: bool = True
    allow_control_plane_reload: bool = False
    allow_queue_backlog_clear: bool = False

    require_approval_for_high: bool = True
    require_approval_for_critical: bool = True

    max_recovery_attempts_per_component: int = 3
    cooldown_seconds: int = 60
    min_health_improvement_required: float = 5.0

    metadata: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HealingAction:
    action_id: str
    component: str
    action_type: str
    severity: str
    status: str
    title: str
    description: str
    recommendation: str
    requires_approval: bool = True
    approved: bool = False
    confidence_score: float = 0.0
    expected_health_gain: float = 0.0
    finding_id: Optional[str] = None
    planned_at: str = field(default_factory=utc_now_iso)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None
    result: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HealingPlan:
    plan_id: str
    report_id: Optional[str]
    mode: str
    status: str
    actions: List[HealingAction]
    actions_total: int
    actions_requiring_approval: int
    estimated_health_gain: float
    generated_at: str = field(default_factory=utc_now_iso)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "actions": [action.as_dict() for action in self.actions],
        }


@dataclass
class HealingExecutionResult:
    execution_id: str
    plan_id: str
    status: str
    actions_attempted: int
    actions_completed: int
    actions_failed: int
    actions_skipped: int
    actions_escalated: int
    started_at: str
    completed_at: str
    duration_ms: float
    results: List[Dict[str, Any]]
    pre_health_score: Optional[float] = None
    post_health_score: Optional[float] = None
    health_improvement: Optional[float] = None
    validation_passed: bool = False
    error: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HealingMetrics:
    plans_generated: int = 0
    executions_total: int = 0
    actions_completed: int = 0
    actions_failed: int = 0
    actions_skipped: int = 0
    actions_escalated: int = 0
    successful_recoveries: int = 0
    failed_recoveries: int = 0
    average_health_improvement: float = 0.0
    average_mttr_ms: float = 0.0
    last_execution_at: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AnalyticsFabricSelfHealingEngine:
    """
    Autonomous recovery layer for Analytics Fabric.

    Consumes diagnostic reports from AnalyticsFabricSelfDiagnosticEngine and
    creates safe recovery plans, executes approved actions, validates health
    after recovery, and records recovery metrics/history.
    """

    def __init__(
        self,
        *,
        diagnostic_engine: Optional[Any] = None,
        control_plane: Optional[Any] = None,
        command_processor: Optional[Any] = None,
        continuous_runtime_engine: Optional[Any] = None,
        autonomous_supervisor: Optional[Any] = None,
        runtime_controller: Optional[Any] = None,
        execution_orchestrator: Optional[Any] = None,
        execution_planner: Optional[Any] = None,
        forecast_optimizer: Optional[Any] = None,
        forecasting_engine: Optional[Any] = None,
        persistence_engine: Optional[Any] = None,
        policy: Optional[SelfHealingPolicy] = None,
    ) -> None:
        self.diagnostic_engine = diagnostic_engine
        self.control_plane = control_plane
        self.command_processor = command_processor
        self.continuous_runtime_engine = continuous_runtime_engine
        self.autonomous_supervisor = autonomous_supervisor
        self.runtime_controller = runtime_controller
        self.execution_orchestrator = execution_orchestrator
        self.execution_planner = execution_planner
        self.forecast_optimizer = forecast_optimizer
        self.forecasting_engine = forecasting_engine
        self.persistence_engine = persistence_engine

        self.policy = policy or SelfHealingPolicy()
        self.metrics = HealingMetrics()

        self.plan_history: List[HealingPlan] = []
        self.execution_history: List[HealingExecutionResult] = []
        self.audit_trail: List[Dict[str, Any]] = []
        self.component_attempts: Dict[str, int] = {}
        self.component_last_recovery_at: Dict[str, float] = {}

    # ============================================================
    # Planning
    # ============================================================

    def generate_healing_plan(
        self,
        diagnostic_report: Optional[Any] = None,
    ) -> HealingPlan:
        if diagnostic_report is None:
            if self.diagnostic_engine is None:
                raise ValueError("diagnostic_engine is required when diagnostic_report is not provided.")
            diagnostic_report = self.diagnostic_engine.run_diagnostics()

        report = self._as_dict(diagnostic_report)
        actions: List[HealingAction] = []

        for component_report in report.get("component_reports", []):
            component = component_report.get("component", "unknown")
            health_score = float(component_report.get("health_score", 0) or 0)
            risk_score = float(component_report.get("risk_score", 0) or 0)
            findings = component_report.get("findings", [])

            if not findings and health_score >= 90 and risk_score <= 20:
                continue

            if not findings and health_score < 90:
                findings = [
                    {
                        "finding_id": None,
                        "severity": self._severity_from_scores(health_score, risk_score),
                        "title": "Component Health Degradation",
                        "description": f"{component} health score is {health_score}.",
                        "recommendation": "Run component recovery validation.",
                    }
                ]

            for finding in findings:
                action = self._action_from_finding(
                    component=component,
                    finding=finding,
                    health_score=health_score,
                    risk_score=risk_score,
                )
                if action is not None:
                    actions.append(action)

        actions = self._deduplicate_actions(actions)

        plan = HealingPlan(
            plan_id=f"healplan_{uuid.uuid4().hex}",
            report_id=report.get("report_id"),
            mode=self.policy.mode,
            status="PLANNED",
            actions=actions,
            actions_total=len(actions),
            actions_requiring_approval=len([a for a in actions if a.requires_approval]),
            estimated_health_gain=round(sum(a.expected_health_gain for a in actions), 2),
            metadata={
                "diagnostic_state": report.get("state"),
                "overall_health_score": report.get("overall_health_score"),
                "overall_risk_score": report.get("overall_risk_score"),
            },
        )

        self.plan_history.append(plan)
        self.metrics.plans_generated += 1
        self._audit("PLAN_GENERATED", "Healing plan generated.", {"plan": plan.as_dict()})
        self._trim_history()

        return plan

    def approve_plan(self, plan: HealingPlan, *, approved_by: str = "operator") -> HealingPlan:
        approved_actions = [
            self._replace_action(action, approved=True, requires_approval=False)
            for action in plan.actions
        ]

        approved = HealingPlan(
            plan_id=plan.plan_id,
            report_id=plan.report_id,
            mode=plan.mode,
            status="APPROVED",
            actions=approved_actions,
            actions_total=len(approved_actions),
            actions_requiring_approval=0,
            estimated_health_gain=plan.estimated_health_gain,
            generated_at=plan.generated_at,
            metadata={**plan.metadata, "approved_by": approved_by, "approved_at": utc_now_iso()},
        )

        self.plan_history.append(approved)
        self._audit("PLAN_APPROVED", "Healing plan approved.", approved.as_dict())
        return approved

    # ============================================================
    # Execution
    # ============================================================

    def execute_healing_plan(
        self,
        plan: HealingPlan,
        *,
        dry_run: bool = True,
        approved_by: Optional[str] = None,
    ) -> HealingExecutionResult:
        started_perf = time.perf_counter()
        started_at = utc_now_iso()

        pre_health = self._current_health_score()

        results: List[Dict[str, Any]] = []
        completed = 0
        failed = 0
        skipped = 0
        escalated = 0

        for action in plan.actions:
            if not self.policy.enabled:
                skipped += 1
                results.append(self._skip_result(action, "Self-healing policy is disabled."))
                continue

            if self._cooldown_active(action.component):
                skipped += 1
                results.append(self._skip_result(action, "Component recovery cooldown is active."))
                continue

            if self._attempt_limit_reached(action.component):
                escalated += 1
                results.append(self._escalate_result(action, "Maximum recovery attempts reached."))
                continue

            if action.requires_approval and not action.approved and not dry_run:
                escalated += 1
                results.append(self._escalate_result(action, "Action requires approval."))
                continue

            if not self._is_action_allowed(action) and not dry_run:
                skipped += 1
                results.append(self._skip_result(action, "Action is not allowed by self-healing policy."))
                continue

            try:
                result = self.execute_healing_action(action, dry_run=dry_run)
                results.append(result)

                if result.get("status") == HealingActionStatus.COMPLETED.value:
                    completed += 1
                    self._record_component_attempt(action.component)
                elif result.get("status") == HealingActionStatus.SKIPPED.value:
                    skipped += 1
                elif result.get("status") == HealingActionStatus.ESCALATED.value:
                    escalated += 1
                else:
                    failed += 1

            except Exception as exc:
                failed += 1
                self._record_component_attempt(action.component)
                results.append(
                    {
                        "action_id": action.action_id,
                        "component": action.component,
                        "action_type": action.action_type,
                        "status": HealingActionStatus.FAILED.value,
                        "error": str(exc),
                    }
                )

        post_health = self._current_health_score()
        improvement = None

        if pre_health is not None and post_health is not None:
            improvement = round(post_health - pre_health, 2)

        validation_passed = self.validate_recovery(
            pre_health_score=pre_health,
            post_health_score=post_health,
            actions_failed=failed,
        )

        duration_ms = round((time.perf_counter() - started_perf) * 1000.0, 4)

        status = "COMPLETED" if failed == 0 else "FAILED"
        if escalated > 0 and completed == 0 and failed == 0:
            status = "ESCALATED"
        if dry_run:
            status = "DRY_RUN_COMPLETED"

        execution = HealingExecutionResult(
            execution_id=f"healexec_{uuid.uuid4().hex}",
            plan_id=plan.plan_id,
            status=status,
            actions_attempted=len(plan.actions),
            actions_completed=completed,
            actions_failed=failed,
            actions_skipped=skipped,
            actions_escalated=escalated,
            started_at=started_at,
            completed_at=utc_now_iso(),
            duration_ms=duration_ms,
            results=results,
            pre_health_score=pre_health,
            post_health_score=post_health,
            health_improvement=improvement,
            validation_passed=validation_passed,
        )

        self.execution_history.append(execution)
        self._update_metrics(execution)
        self._audit("PLAN_EXECUTED", "Healing plan executed.", execution.as_dict())
        self._trim_history()

        return execution

    def execute_healing_action(
        self,
        action: HealingAction,
        *,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        if dry_run:
            return {
                "action_id": action.action_id,
                "component": action.component,
                "action_type": action.action_type,
                "status": HealingActionStatus.COMPLETED.value,
                "dry_run": True,
                "message": "Dry-run healing action completed.",
            }

        target = self._component_instance(action.component)

        if action.action_type == HealingActionType.NOOP.value:
            return self._completed(action, "No action required.")

        if action.action_type == HealingActionType.VALIDATE_HEALTH.value:
            health = self._current_health_score()
            return self._completed(action, "Health validation completed.", {"health_score": health})

        if action.action_type == HealingActionType.RUN_RECOVERY_CYCLE.value:
            return self._call_first_available(
                action,
                target,
                ["run_recovery_cycle", "recover", "recovery_cycle"],
                "Recovery cycle executed.",
            )

        if action.action_type == HealingActionType.REINITIALIZE_COMPONENT.value:
            return self._call_first_available(
                action,
                target,
                ["initialize", "initialize_runtime", "start_supervisor", "start_runtime"],
                "Component reinitialized.",
            )

        if action.action_type == HealingActionType.RESTART_COMPONENT.value:
            pause_result = self._call_optional(target, ["stop", "stop_runtime", "pause_runtime"])
            start_result = self._call_optional(target, ["start", "start_runtime", "resume_runtime", "initialize_runtime"])
            return self._completed(
                action,
                "Component restart attempted.",
                {"stop": pause_result, "start": start_result},
            )

        if action.action_type == HealingActionType.PAUSE_RUNTIME.value:
            return self._call_first_available(
                action,
                target or self.continuous_runtime_engine,
                ["pause_runtime"],
                "Runtime paused.",
            )

        if action.action_type == HealingActionType.RESUME_RUNTIME.value:
            return self._call_first_available(
                action,
                target or self.continuous_runtime_engine,
                ["resume_runtime", "start_runtime"],
                "Runtime resumed.",
            )

        if action.action_type == HealingActionType.RESTART_RUNTIME.value:
            runtime = self.continuous_runtime_engine or target
            stop_result = self._call_optional(runtime, ["stop_runtime", "pause_runtime"])
            start_result = self._call_optional(runtime, ["start_runtime", "resume_runtime"])
            return self._completed(
                action,
                "Runtime restart attempted.",
                {"stop": stop_result, "start": start_result},
            )

        if action.action_type == HealingActionType.RELOAD_CONTROL_PLANE.value:
            return self._call_first_available(
                action,
                self.control_plane,
                ["control_plane_recovery", "platform_resume", "global_status"],
                "Control plane reload/recovery executed.",
            )

        if action.action_type == HealingActionType.REFRESH_SNAPSHOT.value:
            return self._call_first_available(
                action,
                self.control_plane,
                ["create_snapshot", "global_status"],
                "Snapshot refreshed.",
            )

        if action.action_type == HealingActionType.CLEAR_QUEUE_BACKLOG.value:
            return self._call_first_available(
                action,
                target,
                ["clear_backlog", "rebalance", "run_autonomous_cycle"],
                "Queue/backlog recovery executed.",
            )

        if action.action_type == HealingActionType.REBUILD_RUNTIME_STATE.value:
            return self._call_first_available(
                action,
                self.runtime_controller,
                ["initialize_runtime", "runtime_snapshot", "run_autonomous_cycle"],
                "Runtime state rebuilt.",
            )

        if action.action_type == HealingActionType.ESCALATE_TO_OPERATOR.value:
            return self._escalate_result(action, "Escalated to operator.")

        return self._skip_result(action, f"Unsupported healing action type: {action.action_type}")

    # ============================================================
    # Validation / Reporting
    # ============================================================

    def validate_recovery(
        self,
        *,
        pre_health_score: Optional[float],
        post_health_score: Optional[float],
        actions_failed: int,
    ) -> bool:
        if actions_failed > 0:
            return False

        if pre_health_score is None or post_health_score is None:
            return actions_failed == 0

        return (post_health_score - pre_health_score) >= -1.0

    def self_healing_summary(self) -> Dict[str, Any]:
        return {
            "policy": self.policy.as_dict(),
            "metrics": self.metrics.as_dict(),
            "plans": len(self.plan_history),
            "executions": len(self.execution_history),
            "audit_events": len(self.audit_trail),
            "component_attempts": dict(self.component_attempts),
        }

    def healing_history(self, limit: int = 1000) -> List[Dict[str, Any]]:
        return [
            execution.as_dict()
            for execution in self.execution_history[-limit:]
        ]

    def plan_history_records(self, limit: int = 1000) -> List[Dict[str, Any]]:
        return [
            plan.as_dict()
            for plan in self.plan_history[-limit:]
        ]

    def audit_history(self, limit: int = 1000) -> List[Dict[str, Any]]:
        return self.audit_trail[-limit:]

    def export_executive_report(self) -> Dict[str, Any]:
        return {
            "generated_at": utc_now_iso(),
            "summary": self.self_healing_summary(),
            "recent_executions": self.healing_history(limit=25),
            "recent_plans": self.plan_history_records(limit=10),
        }

    # ============================================================
    # Internals
    # ============================================================

    def _action_from_finding(
        self,
        *,
        component: str,
        finding: Dict[str, Any],
        health_score: float,
        risk_score: float,
    ) -> Optional[HealingAction]:
        severity = str(finding.get("severity") or self._severity_from_scores(health_score, risk_score)).upper()
        action_type = self._action_type_for_component(component, severity, health_score, risk_score)

        requires_approval = self._requires_approval(severity, action_type)

        return HealingAction(
            action_id=f"healact_{uuid.uuid4().hex}",
            component=component,
            action_type=action_type,
            severity=severity,
            status=HealingActionStatus.PLANNED.value,
            title=f"Heal {component}: {finding.get('title', 'Diagnostic Finding')}",
            description=finding.get("description", ""),
            recommendation=finding.get("recommendation", "Run recovery validation."),
            requires_approval=requires_approval,
            approved=not requires_approval,
            confidence_score=self._confidence_for_action(action_type, health_score, risk_score),
            expected_health_gain=self._expected_gain_for_action(action_type, health_score, risk_score),
            finding_id=finding.get("finding_id"),
        )

    def _action_type_for_component(
        self,
        component: str,
        severity: str,
        health_score: float,
        risk_score: float,
    ) -> str:
        component_name = str(component or "").lower()

        if severity == HealingSeverity.CRITICAL.value or health_score < 50:
            if "control_plane" in component_name:
                return HealingActionType.RELOAD_CONTROL_PLANE.value
            if "runtime" in component_name:
                return HealingActionType.RESTART_RUNTIME.value
            return HealingActionType.REINITIALIZE_COMPONENT.value

        if severity == HealingSeverity.HIGH.value or health_score < 70 or risk_score > 50:
            if "control_plane" in component_name:
                return HealingActionType.RUN_RECOVERY_CYCLE.value
            if "continuous_runtime" in component_name:
                return HealingActionType.RUN_RECOVERY_CYCLE.value
            if "runtime_controller" in component_name:
                return HealingActionType.REBUILD_RUNTIME_STATE.value
            if "supervisor" in component_name:
                return HealingActionType.RUN_RECOVERY_CYCLE.value
            return HealingActionType.REINITIALIZE_COMPONENT.value

        if severity in {HealingSeverity.MEDIUM.value, HealingSeverity.LOW.value}:
            return HealingActionType.VALIDATE_HEALTH.value

        return HealingActionType.NOOP.value

    def _requires_approval(self, severity: str, action_type: str) -> bool:
        if self.policy.mode == HealingMode.OBSERVE_ONLY.value:
            return True

        if severity == HealingSeverity.CRITICAL.value and self.policy.require_approval_for_critical:
            return True

        if severity == HealingSeverity.HIGH.value and self.policy.require_approval_for_high:
            return True

        if action_type in {
            HealingActionType.RESTART_RUNTIME.value,
            HealingActionType.RELOAD_CONTROL_PLANE.value,
            HealingActionType.CLEAR_QUEUE_BACKLOG.value,
        }:
            return True

        return False

    def _is_action_allowed(self, action: HealingAction) -> bool:
        if self.policy.mode == HealingMode.OBSERVE_ONLY.value:
            return False

        if action.action_type == HealingActionType.RESTART_RUNTIME.value:
            return self.policy.allow_runtime_restart

        if action.action_type == HealingActionType.REINITIALIZE_COMPONENT.value:
            return self.policy.allow_component_reinitialize

        if action.action_type == HealingActionType.RUN_RECOVERY_CYCLE.value:
            return self.policy.allow_recovery_cycle

        if action.action_type == HealingActionType.REFRESH_SNAPSHOT.value:
            return self.policy.allow_snapshot_refresh

        if action.action_type == HealingActionType.RELOAD_CONTROL_PLANE.value:
            return self.policy.allow_control_plane_reload

        if action.action_type == HealingActionType.CLEAR_QUEUE_BACKLOG.value:
            return self.policy.allow_queue_backlog_clear

        return True

    def _current_health_score(self) -> Optional[float]:
        if self.diagnostic_engine is None:
            return None

        try:
            report = self.diagnostic_engine.run_diagnostics()
            data = self._as_dict(report)
            return float(data.get("overall_health_score"))
        except Exception:
            return None

    def _component_instance(self, component: str) -> Optional[Any]:
        mapping = {
            "control_plane": self.control_plane,
            "command_processor": self.command_processor,
            "continuous_runtime": self.continuous_runtime_engine,
            "autonomous_supervisor": self.autonomous_supervisor,
            "runtime_controller": self.runtime_controller,
            "execution_orchestrator": self.execution_orchestrator,
            "execution_planner": self.execution_planner,
            "forecast_optimizer": self.forecast_optimizer,
            "forecasting_engine": self.forecasting_engine,
            "persistence_engine": self.persistence_engine,
        }

        return mapping.get(str(component or "").lower())

    def _severity_from_scores(self, health_score: float, risk_score: float) -> str:
        if health_score < 40 or risk_score >= 80:
            return HealingSeverity.CRITICAL.value
        if health_score < 60 or risk_score >= 60:
            return HealingSeverity.HIGH.value
        if health_score < 80 or risk_score >= 40:
            return HealingSeverity.MEDIUM.value
        if health_score < 90 or risk_score >= 20:
            return HealingSeverity.LOW.value
        return HealingSeverity.INFO.value

    def _confidence_for_action(self, action_type: str, health_score: float, risk_score: float) -> float:
        base = 75.0

        if action_type in {
            HealingActionType.VALIDATE_HEALTH.value,
            HealingActionType.REFRESH_SNAPSHOT.value,
            HealingActionType.RUN_RECOVERY_CYCLE.value,
        }:
            base += 10

        if health_score < 50:
            base -= 10

        if risk_score > 70:
            base -= 5

        return round(clamp(base), 2)

    def _expected_gain_for_action(self, action_type: str, health_score: float, risk_score: float) -> float:
        if action_type == HealingActionType.NOOP.value:
            return 0.0
        if action_type == HealingActionType.VALIDATE_HEALTH.value:
            return 2.0
        if action_type == HealingActionType.REFRESH_SNAPSHOT.value:
            return 3.0
        if action_type == HealingActionType.RUN_RECOVERY_CYCLE.value:
            return 8.0
        if action_type == HealingActionType.REINITIALIZE_COMPONENT.value:
            return 12.0
        if action_type in {
            HealingActionType.RESTART_RUNTIME.value,
            HealingActionType.RELOAD_CONTROL_PLANE.value,
        }:
            return 18.0
        return 5.0

    def _cooldown_active(self, component: str) -> bool:
        last = self.component_last_recovery_at.get(component)
        if last is None:
            return False
        return (time.time() - last) < self.policy.cooldown_seconds

    def _attempt_limit_reached(self, component: str) -> bool:
        return self.component_attempts.get(component, 0) >= self.policy.max_recovery_attempts_per_component

    def _record_component_attempt(self, component: str) -> None:
        self.component_attempts[component] = self.component_attempts.get(component, 0) + 1
        self.component_last_recovery_at[component] = time.time()

    def _call_first_available(
        self,
        action: HealingAction,
        target: Any,
        method_names: List[str],
        success_message: str,
    ) -> Dict[str, Any]:
        if target is None:
            return self._escalate_result(action, "Target component is not registered.")

        errors = []

        for method_name in method_names:
            method = getattr(target, method_name, None)

            if method is None:
                continue

            try:
                result = method()
                return self._completed(
                    action,
                    success_message,
                    {
                        "method": method_name,
                        "result": self._as_dict(result),
                    },
                )
            except Exception as exc:
                errors.append({"method": method_name, "error": str(exc)})

        return self._skip_result(
            action,
            "No compatible recovery method available.",
            {"errors": errors},
        )

    def _call_optional(self, target: Any, method_names: List[str]) -> Dict[str, Any]:
        if target is None:
            return {"status": "NO_TARGET"}

        for method_name in method_names:
            method = getattr(target, method_name, None)

            if method is None:
                continue

            try:
                result = method()
                return {
                    "status": "COMPLETED",
                    "method": method_name,
                    "result": self._as_dict(result),
                }
            except Exception as exc:
                return {
                    "status": "FAILED",
                    "method": method_name,
                    "error": str(exc),
                }

        return {"status": "NO_METHOD"}

    def _completed(
        self,
        action: HealingAction,
        message: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return {
            "action_id": action.action_id,
            "component": action.component,
            "action_type": action.action_type,
            "status": HealingActionStatus.COMPLETED.value,
            "message": message,
            "payload": payload or {},
        }

    def _skip_result(
        self,
        action: HealingAction,
        reason: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return {
            "action_id": action.action_id,
            "component": action.component,
            "action_type": action.action_type,
            "status": HealingActionStatus.SKIPPED.value,
            "reason": reason,
            "payload": payload or {},
        }

    def _escalate_result(
        self,
        action: HealingAction,
        reason: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return {
            "action_id": action.action_id,
            "component": action.component,
            "action_type": action.action_type,
            "status": HealingActionStatus.ESCALATED.value,
            "reason": reason,
            "payload": payload or {},
        }

    def _replace_action(self, action: HealingAction, **updates: Any) -> HealingAction:
        data = action.as_dict()
        data.update(updates)
        return HealingAction(**data)

    def _deduplicate_actions(self, actions: List[HealingAction]) -> List[HealingAction]:
        seen = set()
        deduped = []

        for action in actions:
            key = (action.component, action.action_type, action.finding_id)

            if key in seen:
                continue

            seen.add(key)
            deduped.append(action)

        return deduped

    def _update_metrics(self, execution: HealingExecutionResult) -> None:
        self.metrics.executions_total += 1
        self.metrics.actions_completed += execution.actions_completed
        self.metrics.actions_failed += execution.actions_failed
        self.metrics.actions_skipped += execution.actions_skipped
        self.metrics.actions_escalated += execution.actions_escalated
        self.metrics.last_execution_at = execution.completed_at

        if execution.validation_passed:
            self.metrics.successful_recoveries += 1
        else:
            self.metrics.failed_recoveries += 1

        improvements = [
            item.health_improvement
            for item in self.execution_history
            if item.health_improvement is not None
        ]

        durations = [
            item.duration_ms
            for item in self.execution_history
            if item.duration_ms is not None
        ]

        if improvements:
            self.metrics.average_health_improvement = round(sum(improvements) / len(improvements), 2)

        if durations:
            self.metrics.average_mttr_ms = round(sum(durations) / len(durations), 2)

    def _audit(self, event_type: str, message: str, payload: Dict[str, Any]) -> None:
        self.audit_trail.append(
            {
                "event_id": f"healaudit_{uuid.uuid4().hex}",
                "event_type": event_type,
                "message": message,
                "payload": payload,
                "created_at": utc_now_iso(),
            }
        )

        if len(self.audit_trail) > 10000:
            self.audit_trail = self.audit_trail[-10000:]

    def _trim_history(self) -> None:
        if len(self.plan_history) > 1000:
            self.plan_history = self.plan_history[-1000:]

        if len(self.execution_history) > 1000:
            self.execution_history = self.execution_history[-1000:]

        if len(self.audit_trail) > 10000:
            self.audit_trail = self.audit_trail[-10000:]

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