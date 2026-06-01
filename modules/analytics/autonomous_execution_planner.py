"""
modules/analytics/autonomous_execution_planner.py
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, float(value)))


class ExecutionPlanState(str, Enum):
    DRAFT = "DRAFT"
    READY = "READY"
    REQUIRES_APPROVAL = "REQUIRES_APPROVAL"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ExecutionActionType(str, Enum):
    SCALE_WORKERS = "SCALE_WORKERS"
    ADD_EXECUTION_NODES = "ADD_EXECUTION_NODES"
    REBALANCE_PROVIDERS = "REBALANCE_PROVIDERS"
    SHIFT_PROVIDER_ALLOCATION = "SHIFT_PROVIDER_ALLOCATION"
    REDUCE_PROVIDER_SPEND = "REDUCE_PROVIDER_SPEND"
    PAUSE_LOW_PRIORITY_UNIVERSES = "PAUSE_LOW_PRIORITY_UNIVERSES"
    RESUME_UNIVERSES = "RESUME_UNIVERSES"
    ADJUST_BATCH_SIZE = "ADJUST_BATCH_SIZE"
    INCREASE_BATCH_SIZE = "INCREASE_BATCH_SIZE"
    DECREASE_BATCH_SIZE = "DECREASE_BATCH_SIZE"
    APPLY_GOVERNANCE_CONTROLS = "APPLY_GOVERNANCE_CONTROLS"
    MODIFY_CAPACITY_TARGETS = "MODIFY_CAPACITY_TARGETS"
    ENABLE_CONSERVATIVE_MODE = "ENABLE_CONSERVATIVE_MODE"
    ENABLE_AGGRESSIVE_OPTIMIZATION = "ENABLE_AGGRESSIVE_OPTIMIZATION"
    GENERATE_GLOBAL_PLAN = "GENERATE_GLOBAL_PLAN"
    RUN_OPTIMIZER = "RUN_OPTIMIZER"
    RUN_CAPACITY_ANALYSIS = "RUN_CAPACITY_ANALYSIS"
    RUN_PROVIDER_ANALYSIS = "RUN_PROVIDER_ANALYSIS"
    RUN_TENANT_INTELLIGENCE = "RUN_TENANT_INTELLIGENCE"
    SAVE_EXECUTIVE_SNAPSHOT = "SAVE_EXECUTIVE_SNAPSHOT"
    SAVE_CONTROL_TOWER_SNAPSHOT = "SAVE_CONTROL_TOWER_SNAPSHOT"


class ExecutionActionSeverity(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ExecutionActionStatus(str, Enum):
    PENDING = "PENDING"
    READY = "READY"
    REQUIRES_APPROVAL = "REQUIRES_APPROVAL"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass(frozen=True)
class ExecutionPlannerPolicy:
    policy_id: str = field(default_factory=lambda: f"execpol_{uuid.uuid4().hex}")
    name: str = "Default Autonomous Execution Planner Policy"
    enabled: bool = True

    allow_autonomous_scaling: bool = False
    allow_autonomous_provider_rebalance: bool = False
    allow_autonomous_universe_pause: bool = False
    allow_autonomous_batch_adjustment: bool = True
    allow_autonomous_governance_controls: bool = False
    allow_autonomous_snapshots: bool = True

    high_impact_approval_threshold: float = 0.75
    critical_impact_approval_threshold: float = 0.90
    min_confidence_for_autonomous_action: float = 0.80
    max_worker_scale_delta_without_approval: int = 5
    max_batch_size_multiplier_without_approval: float = 2.0

    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutableAnalyticsAction:
    action_id: str
    action_type: str
    title: str
    description: str
    severity: str
    status: str = ExecutionActionStatus.PENDING.value
    priority: str = "NORMAL"
    requires_approval: bool = True
    autonomous_allowed: bool = False
    expected_impact: float = 0.0
    confidence_score: float = 0.0
    tenant_id: Optional[str] = None
    universe_id: Optional[str] = None
    provider: Optional[str] = None
    worker_id: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    source_recommendation_id: Optional[str] = None
    generated_at: str = field(default_factory=utc_now_iso)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AutonomousExecutionPlan:
    plan_id: str
    state: str
    title: str
    description: str
    actions: List[ExecutableAnalyticsAction]
    approved_actions: int
    pending_approval_actions: int
    blocked_actions: int
    estimated_impact: float
    readiness_score: float
    generated_at: str = field(default_factory=utc_now_iso)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExecutionPlanResult:
    execution_id: str
    plan_id: str
    status: str
    actions_attempted: int
    actions_completed: int
    actions_failed: int
    results: List[Dict[str, Any]]
    started_at: str
    completed_at: str
    error: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExecutionPlannerSummary:
    plans_generated: int
    plans_approved: int
    plans_executed: int
    actions_generated: int
    actions_completed: int
    actions_failed: int
    pending_approval_actions: int
    generated_at: str = field(default_factory=utc_now_iso)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AutonomousExecutionPlanner:
    """
    Converts forecast optimizer recommendations into executable Analytics Fabric
    action plans.

    This planner does not require direct infrastructure privileges. It creates a
    deterministic execution plan and can optionally invoke safe local fabric
    methods when available.
    """

    def __init__(
            self,
            *,
            policy: Optional[ExecutionPlannerPolicy] = None,
            analytics_fabric: Optional[Any] = None,
            forecast_optimizer: Optional[Any] = None,
            forecasting_engine: Optional[Any] = None,
            persistence_engine: Optional[Any] = None,
            snapshot_scheduler: Optional[Any] = None,
    ) -> None:
        self.policy = policy or ExecutionPlannerPolicy()
        self.analytics_fabric = analytics_fabric
        self.forecast_optimizer = forecast_optimizer
        self.forecasting_engine = forecasting_engine
        self.persistence_engine = persistence_engine
        self.snapshot_scheduler = snapshot_scheduler

        self.plan_history: List[AutonomousExecutionPlan] = []
        self.execution_history: List[ExecutionPlanResult] = []
        self.action_history: List[ExecutableAnalyticsAction] = []

    # ------------------------------------------------------------------
    # Plan Generation
    # ------------------------------------------------------------------

    def build_execution_plan_from_optimizer(
            self,
            optimization_report: Optional[Any] = None,
    ) -> AutonomousExecutionPlan:
        if optimization_report is None:
            if self.forecast_optimizer is None:
                raise ValueError("forecast_optimizer is required when optimization_report is not provided.")
            optimization_report = self.forecast_optimizer.generate_optimization_report()

        report = self._as_dict(optimization_report)
        recommendations = report.get("recommendations", [])

        actions: List[ExecutableAnalyticsAction] = []

        actions.extend(
            self._actions_from_capacity_plan(
                report.get("capacity_plan", {})
            )
        )

        actions.extend(
            self._actions_from_provider_plan(
                report.get("provider_plan", {})
            )
        )

        actions.extend(
            self._actions_from_queue_plan(
                report.get("queue_plan", {})
            )
        )

        actions.extend(
            self._actions_from_governance_plan(
                report.get("governance_plan", {})
            )
        )

        actions.extend(
            self._actions_from_growth_plans(
                tenant_plan=report.get("tenant_plan", {}),
                universe_plan=report.get("universe_plan", {}),
            )
        )

        actions.extend(
            self._actions_from_health_plan(
                report.get("health_plan", {})
            )
        )

        actions.extend(
            self._actions_from_recommendations(
                recommendations
            )
        )

        deduped_actions = self._deduplicate_actions(actions)
        normalized_actions = [
            self._apply_policy_to_action(action)
            for action in deduped_actions
        ]

        approved_actions = len(
            [
                action for action in normalized_actions
                if action.status in {
                ExecutionActionStatus.READY.value,
                ExecutionActionStatus.APPROVED.value,
            }
                   and not action.requires_approval
            ]
        )

        pending_approval_actions = len(
            [
                action for action in normalized_actions
                if action.requires_approval
            ]
        )

        blocked_actions = len(
            [
                action for action in normalized_actions
                if action.status == ExecutionActionStatus.REQUIRES_APPROVAL.value
            ]
        )

        estimated_impact = round(
            sum(action.expected_impact for action in normalized_actions),
            4,
        )

        readiness_score = self._calculate_readiness_score(normalized_actions)

        state = ExecutionPlanState.READY.value

        if pending_approval_actions:
            state = ExecutionPlanState.REQUIRES_APPROVAL.value

        if not normalized_actions:
            state = ExecutionPlanState.DRAFT.value

        plan = AutonomousExecutionPlan(
            plan_id=f"aexecplan_{uuid.uuid4().hex}",
            state=state,
            title="Autonomous Analytics Execution Plan",
            description="Execution plan generated from forecast optimization recommendations.",
            actions=normalized_actions,
            approved_actions=approved_actions,
            pending_approval_actions=pending_approval_actions,
            blocked_actions=blocked_actions,
            estimated_impact=estimated_impact,
            readiness_score=readiness_score,
            metadata={
                "source_report_id": report.get("report_id"),
                "overall_optimization_score": report.get("overall_score"),
            },
        )

        self.plan_history.append(plan)
        self.action_history.extend(normalized_actions)
        self._trim_history()

        return plan

    def build_execution_plan_from_recommendations(
            self,
            recommendations: Iterable[Any],
            *,
            title: str = "Autonomous Analytics Recommendation Execution Plan",
            description: str = "Execution plan generated from recommendation list.",
    ) -> AutonomousExecutionPlan:
        actions = self._actions_from_recommendations(
            [self._as_dict(r) for r in recommendations]
        )

        normalized_actions = [
            self._apply_policy_to_action(action)
            for action in self._deduplicate_actions(actions)
        ]

        pending = len([a for a in normalized_actions if a.requires_approval])
        ready = len([a for a in normalized_actions if not a.requires_approval])
        blocked = len([a for a in normalized_actions if a.status == ExecutionActionStatus.REQUIRES_APPROVAL.value])

        state = ExecutionPlanState.READY.value if not pending else ExecutionPlanState.REQUIRES_APPROVAL.value

        plan = AutonomousExecutionPlan(
            plan_id=f"aexecplan_{uuid.uuid4().hex}",
            state=state,
            title=title,
            description=description,
            actions=normalized_actions,
            approved_actions=ready,
            pending_approval_actions=pending,
            blocked_actions=blocked,
            estimated_impact=round(sum(a.expected_impact for a in normalized_actions), 4),
            readiness_score=self._calculate_readiness_score(normalized_actions),
        )

        self.plan_history.append(plan)
        self.action_history.extend(normalized_actions)
        self._trim_history()

        return plan

    # ------------------------------------------------------------------
    # Action Builders
    # ------------------------------------------------------------------

    def _actions_from_capacity_plan(
            self,
            capacity_plan: Dict[str, Any],
    ) -> List[ExecutableAnalyticsAction]:
        actions = []
        plan_actions = capacity_plan.get("actions", [])
        current = float(capacity_plan.get("current_capacity", 0) or 0)
        recommended = float(capacity_plan.get("recommended_capacity", current) or current)
        delta = max(0.0, recommended - current)

        if "SCALE_UP_WORKERS" in plan_actions:
            actions.append(
                self._action(
                    action_type=ExecutionActionType.SCALE_WORKERS,
                    title="Scale analytics worker fleet",
                    description="Increase worker capacity based on forecasted capacity pressure.",
                    severity=ExecutionActionSeverity.HIGH if delta > 10 else ExecutionActionSeverity.MEDIUM,
                    expected_impact=0.85,
                    confidence_score=0.90,
                    parameters={
                        "current_capacity": current,
                        "recommended_capacity": recommended,
                        "capacity_delta": delta,
                        "direction": "UP",
                    },
                )
            )

        if "SCALE_DOWN_WORKERS" in plan_actions:
            actions.append(
                self._action(
                    action_type=ExecutionActionType.SCALE_WORKERS,
                    title="Scale down analytics worker fleet",
                    description="Reduce worker capacity where forecasted demand does not require current capacity.",
                    severity=ExecutionActionSeverity.LOW,
                    expected_impact=0.40,
                    confidence_score=0.75,
                    parameters={
                        "current_capacity": current,
                        "recommended_capacity": recommended,
                        "direction": "DOWN",
                    },
                )
            )

        if "ADD_EXECUTION_NODES" in plan_actions:
            actions.append(
                self._action(
                    action_type=ExecutionActionType.ADD_EXECUTION_NODES,
                    title="Add analytics execution nodes",
                    description="Add execution nodes to increase processing throughput.",
                    severity=ExecutionActionSeverity.HIGH,
                    expected_impact=0.80,
                    confidence_score=0.88,
                    parameters={
                        "recommended_capacity": recommended,
                        "capacity_delta": delta,
                    },
                )
            )

        return actions

    def _actions_from_provider_plan(
            self,
            provider_plan: Dict[str, Any],
    ) -> List[ExecutableAnalyticsAction]:
        actions = []
        plan_actions = provider_plan.get("actions", [])
        current_spend = float(provider_plan.get("current_spend", 0) or 0)
        target_spend = float(provider_plan.get("target_spend", current_spend) or current_spend)

        if "REDUCE_PROVIDER_SPEND" in plan_actions:
            actions.append(
                self._action(
                    action_type=ExecutionActionType.REDUCE_PROVIDER_SPEND,
                    title="Reduce provider spend",
                    description="Reduce provider cost through routing and usage optimization.",
                    severity=ExecutionActionSeverity.MEDIUM,
                    expected_impact=0.75,
                    confidence_score=0.85,
                    parameters={
                        "current_spend": current_spend,
                        "target_spend": target_spend,
                        "estimated_savings": max(0.0, current_spend - target_spend),
                    },
                )
            )

        if "SHIFT_PROVIDER_ALLOCATION" in plan_actions:
            actions.append(
                self._action(
                    action_type=ExecutionActionType.SHIFT_PROVIDER_ALLOCATION,
                    title="Shift provider allocation",
                    description="Reallocate analytics workload toward lower-cost or higher-performing providers.",
                    severity=ExecutionActionSeverity.MEDIUM,
                    expected_impact=0.72,
                    confidence_score=0.82,
                    parameters={
                        "current_spend": current_spend,
                        "target_spend": target_spend,
                    },
                )
            )

        if "ADD_PROVIDER_CAPACITY" in plan_actions:
            actions.append(
                self._action(
                    action_type=ExecutionActionType.REBALANCE_PROVIDERS,
                    title="Add provider capacity",
                    description="Increase provider capacity or quotas for forecasted demand.",
                    severity=ExecutionActionSeverity.HIGH,
                    expected_impact=0.78,
                    confidence_score=0.80,
                    parameters=provider_plan,
                )
            )

        return actions

    def _actions_from_queue_plan(
            self,
            queue_plan: Dict[str, Any],
    ) -> List[ExecutableAnalyticsAction]:
        actions = []
        plan_actions = queue_plan.get("actions", [])

        current_queue = float(queue_plan.get("current_queue", 0) or 0)
        target_queue = float(queue_plan.get("target_queue", current_queue) or current_queue)

        if "INCREASE_BATCH_SIZE" in plan_actions:
            actions.append(
                self._action(
                    action_type=ExecutionActionType.INCREASE_BATCH_SIZE,
                    title="Increase analytics batch size",
                    description="Increase queue processing batch size to reduce backlog.",
                    severity=ExecutionActionSeverity.MEDIUM,
                    expected_impact=0.80,
                    confidence_score=0.88,
                    parameters={
                        "current_queue": current_queue,
                        "target_queue": target_queue,
                        "batch_direction": "INCREASE",
                    },
                )
            )

        if "DECREASE_BATCH_SIZE" in plan_actions:
            actions.append(
                self._action(
                    action_type=ExecutionActionType.DECREASE_BATCH_SIZE,
                    title="Decrease analytics batch size",
                    description="Decrease batch size to reduce pressure or improve stability.",
                    severity=ExecutionActionSeverity.LOW,
                    expected_impact=0.50,
                    confidence_score=0.75,
                    parameters={
                        "current_queue": current_queue,
                        "target_queue": target_queue,
                        "batch_direction": "DECREASE",
                    },
                )
            )

        if "ADD_EXECUTION_NODES" in plan_actions:
            actions.append(
                self._action(
                    action_type=ExecutionActionType.ADD_EXECUTION_NODES,
                    title="Add execution capacity for queue reduction",
                    description="Add execution nodes to reduce projected queue growth.",
                    severity=ExecutionActionSeverity.HIGH,
                    expected_impact=0.82,
                    confidence_score=0.86,
                    parameters={
                        "current_queue": current_queue,
                        "target_queue": target_queue,
                    },
                )
            )

        return actions

    def _actions_from_governance_plan(
            self,
            governance_plan: Dict[str, Any],
    ) -> List[ExecutableAnalyticsAction]:
        actions = []
        plan_actions = governance_plan.get("actions", [])

        current_risk = float(governance_plan.get("current_risk", 0) or 0)
        target_risk = float(governance_plan.get("target_risk", current_risk) or current_risk)

        if "ENABLE_CONSERVATIVE_MODE" in plan_actions:
            actions.append(
                self._action(
                    action_type=ExecutionActionType.ENABLE_CONSERVATIVE_MODE,
                    title="Enable conservative governance mode",
                    description="Apply stricter execution controls to reduce projected governance risk.",
                    severity=ExecutionActionSeverity.HIGH,
                    expected_impact=0.70,
                    confidence_score=0.84,
                    parameters={
                        "current_risk": current_risk,
                        "target_risk": target_risk,
                    },
                )
            )

        if "PAUSE_LOW_PRIORITY_UNIVERSES" in plan_actions:
            actions.append(
                self._action(
                    action_type=ExecutionActionType.PAUSE_LOW_PRIORITY_UNIVERSES,
                    title="Pause low-priority universes",
                    description="Pause lower-priority analytics universes to reduce governance or capacity risk.",
                    severity=ExecutionActionSeverity.HIGH,
                    expected_impact=0.72,
                    confidence_score=0.82,
                    parameters={
                        "current_risk": current_risk,
                        "target_risk": target_risk,
                    },
                )
            )

        if "APPLY_GOVERNANCE_CONTROLS" in plan_actions:
            actions.append(
                self._action(
                    action_type=ExecutionActionType.APPLY_GOVERNANCE_CONTROLS,
                    title="Apply analytics governance controls",
                    description="Apply additional execution governance safeguards.",
                    severity=ExecutionActionSeverity.MEDIUM,
                    expected_impact=0.68,
                    confidence_score=0.80,
                    parameters=governance_plan,
                )
            )

        return actions

    def _actions_from_growth_plans(
            self,
            *,
            tenant_plan: Dict[str, Any],
            universe_plan: Dict[str, Any],
    ) -> List[ExecutableAnalyticsAction]:
        actions = []

        if "ENABLE_AGGRESSIVE_OPTIMIZATION" in tenant_plan.get("actions", []):
            actions.append(
                self._action(
                    action_type=ExecutionActionType.ENABLE_AGGRESSIVE_OPTIMIZATION,
                    title="Enable aggressive tenant growth optimization",
                    description="Increase optimization posture to support projected tenant growth.",
                    severity=ExecutionActionSeverity.MEDIUM,
                    expected_impact=0.65,
                    confidence_score=0.78,
                    parameters=tenant_plan,
                )
            )

        if "ENABLE_AGGRESSIVE_OPTIMIZATION" in universe_plan.get("actions", []):
            actions.append(
                self._action(
                    action_type=ExecutionActionType.GENERATE_GLOBAL_PLAN,
                    title="Generate expanded global universe plan",
                    description="Generate a global execution plan for projected universe growth.",
                    severity=ExecutionActionSeverity.MEDIUM,
                    expected_impact=0.66,
                    confidence_score=0.78,
                    parameters=universe_plan,
                )
            )

        return actions

    def _actions_from_health_plan(
            self,
            health_plan: Dict[str, Any],
    ) -> List[ExecutableAnalyticsAction]:
        actions = []

        for action_name in health_plan.get("actions", []):
            if action_name == "ENABLE_CONSERVATIVE_MODE":
                action_type = ExecutionActionType.ENABLE_CONSERVATIVE_MODE
                title = "Enable conservative mode for fabric health"
                severity = ExecutionActionSeverity.HIGH
            elif action_name == "ENABLE_AGGRESSIVE_OPTIMIZATION":
                action_type = ExecutionActionType.ENABLE_AGGRESSIVE_OPTIMIZATION
                title = "Enable aggressive optimization for healthy fabric"
                severity = ExecutionActionSeverity.MEDIUM
            elif action_name == "REDUCE_PROVIDER_SPEND":
                action_type = ExecutionActionType.REDUCE_PROVIDER_SPEND
                title = "Reduce provider spend for fabric health"
                severity = ExecutionActionSeverity.MEDIUM
            elif action_name == "PAUSE_LOW_PRIORITY_UNIVERSES":
                action_type = ExecutionActionType.PAUSE_LOW_PRIORITY_UNIVERSES
                title = "Pause low-priority universes for health recovery"
                severity = ExecutionActionSeverity.HIGH
            else:
                continue

            actions.append(
                self._action(
                    action_type=action_type,
                    title=title,
                    description="Action generated from fabric health optimization plan.",
                    severity=severity,
                    expected_impact=0.70,
                    confidence_score=0.80,
                    parameters=health_plan,
                )
            )

        return actions

    def _actions_from_recommendations(
            self,
            recommendations: Iterable[Dict[str, Any]],
    ) -> List[ExecutableAnalyticsAction]:
        actions = []

        for recommendation in recommendations:
            rec_type = str(
                recommendation.get("recommendation_type", "")
            ).upper()

            action_type = self._map_recommendation_type(rec_type)

            if action_type is None:
                continue

            actions.append(
                self._action(
                    action_type=action_type,
                    title=recommendation.get("title", rec_type),
                    description=recommendation.get("description", ""),
                    severity=self._severity_from_priority(
                        recommendation.get("priority", "NORMAL")
                    ),
                    expected_impact=float(recommendation.get("expected_impact", 0.0) or 0.0),
                    confidence_score=float(recommendation.get("confidence_score", 0.0) or 0.0),
                    parameters={
                        "recommendation": recommendation,
                    },
                    source_recommendation_id=recommendation.get("recommendation_id"),
                )
            )

        return actions

    def _map_recommendation_type(
            self,
            recommendation_type: str,
    ) -> Optional[ExecutionActionType]:
        mapping = {
            "SCALE_UP_WORKERS": ExecutionActionType.SCALE_WORKERS,
            "SCALE_DOWN_WORKERS": ExecutionActionType.SCALE_WORKERS,
            "ADD_PROVIDER_CAPACITY": ExecutionActionType.REBALANCE_PROVIDERS,
            "SHIFT_PROVIDER_ALLOCATION": ExecutionActionType.SHIFT_PROVIDER_ALLOCATION,
            "REDUCE_PROVIDER_SPEND": ExecutionActionType.REDUCE_PROVIDER_SPEND,
            "PAUSE_LOW_PRIORITY_UNIVERSES": ExecutionActionType.PAUSE_LOW_PRIORITY_UNIVERSES,
            "INCREASE_BATCH_SIZE": ExecutionActionType.INCREASE_BATCH_SIZE,
            "DECREASE_BATCH_SIZE": ExecutionActionType.DECREASE_BATCH_SIZE,
            "ADD_EXECUTION_NODES": ExecutionActionType.ADD_EXECUTION_NODES,
            "ENABLE_AGGRESSIVE_OPTIMIZATION": ExecutionActionType.ENABLE_AGGRESSIVE_OPTIMIZATION,
            "ENABLE_CONSERVATIVE_MODE": ExecutionActionType.ENABLE_CONSERVATIVE_MODE,
        }

        return mapping.get(recommendation_type)

    # ------------------------------------------------------------------
    # Approval / Execution
    # ------------------------------------------------------------------

    def approve_plan(
            self,
            plan: AutonomousExecutionPlan,
    ) -> AutonomousExecutionPlan:
        approved_actions = []

        for action in plan.actions:
            approved_actions.append(
                self._replace_action(
                    action,
                    status=ExecutionActionStatus.APPROVED.value,
                    requires_approval=False,
                    autonomous_allowed=True,
                )
            )

        approved = AutonomousExecutionPlan(
            plan_id=plan.plan_id,
            state=ExecutionPlanState.APPROVED.value,
            title=plan.title,
            description=plan.description,
            actions=approved_actions,
            approved_actions=len(approved_actions),
            pending_approval_actions=0,
            blocked_actions=0,
            estimated_impact=plan.estimated_impact,
            readiness_score=self._calculate_readiness_score(approved_actions),
            generated_at=plan.generated_at,
            metadata={**plan.metadata, "approved_at": utc_now_iso()},
        )

        self.plan_history.append(approved)
        return approved

    def execute_plan(
            self,
            plan: AutonomousExecutionPlan,
            *,
            dry_run: bool = True,
    ) -> ExecutionPlanResult:
        started_at = utc_now_iso()
        results: List[Dict[str, Any]] = []
        completed = 0
        failed = 0

        for action in plan.actions:
            if action.requires_approval and not dry_run:
                results.append(
                    {
                        "action_id": action.action_id,
                        "action_type": action.action_type,
                        "status": "SKIPPED",
                        "reason": "Action requires approval.",
                    }
                )
                continue

            try:
                result = self.execute_action(action, dry_run=dry_run)
                results.append(result)

                if result.get("status") == "COMPLETED":
                    completed += 1
                else:
                    failed += 1

            except Exception as exc:
                failed += 1
                results.append(
                    {
                        "action_id": action.action_id,
                        "action_type": action.action_type,
                        "status": "FAILED",
                        "error": str(exc),
                    }
                )

        execution = ExecutionPlanResult(
            execution_id=f"aexec_{uuid.uuid4().hex}",
            plan_id=plan.plan_id,
            status=ExecutionPlanState.COMPLETED.value if failed == 0 else ExecutionPlanState.FAILED.value,
            actions_attempted=len(plan.actions),
            actions_completed=completed,
            actions_failed=failed,
            results=results,
            started_at=started_at,
            completed_at=utc_now_iso(),
        )

        self.execution_history.append(execution)
        self._trim_history()
        return execution

    def execute_action(
            self,
            action: ExecutableAnalyticsAction,
            *,
            dry_run: bool = True,
    ) -> Dict[str, Any]:
        if dry_run:
            return {
                "action_id": action.action_id,
                "action_type": action.action_type,
                "status": "COMPLETED",
                "dry_run": True,
                "message": "Dry-run execution completed.",
                "parameters": action.parameters,
            }

        if action.action_type == ExecutionActionType.RUN_OPTIMIZER.value:
            optimizer = self.forecast_optimizer
            if optimizer is not None:
                report = optimizer.generate_optimization_report()
                return {
                    "action_id": action.action_id,
                    "action_type": action.action_type,
                    "status": "COMPLETED",
                    "result": self._as_dict(report),
                }

        if action.action_type == ExecutionActionType.RUN_CAPACITY_ANALYSIS.value:
            fabric = self.analytics_fabric
            if fabric is not None:
                summary = fabric.worker_capacity_model.capacity_summary()
                return {
                    "action_id": action.action_id,
                    "action_type": action.action_type,
                    "status": "COMPLETED",
                    "result": summary,
                }

        if action.action_type == ExecutionActionType.RUN_PROVIDER_ANALYSIS.value:
            fabric = self.analytics_fabric
            if fabric is not None:
                summary = fabric.provider_cost_intelligence.summary()
                return {
                    "action_id": action.action_id,
                    "action_type": action.action_type,
                    "status": "COMPLETED",
                    "result": summary,
                }

        if action.action_type == ExecutionActionType.RUN_TENANT_INTELLIGENCE.value:
            fabric = self.analytics_fabric
            if fabric is not None:
                summary = fabric.tenant_universe_intelligence.intelligence_summary()
                return {
                    "action_id": action.action_id,
                    "action_type": action.action_type,
                    "status": "COMPLETED",
                    "result": summary,
                }

        if action.action_type == ExecutionActionType.GENERATE_GLOBAL_PLAN.value:
            fabric = self.analytics_fabric
            if fabric is not None:
                queue_metrics = fabric.execution_queue.queue_metrics()
                plan = fabric.global_planner.build_execution_plan(
                    queue_metrics=queue_metrics,
                    worker_report=None,
                    provider_profiles=list(
                        getattr(
                            fabric.provider_cost_intelligence,
                            "provider_profiles",
                            {},
                        ).values()
                    ),
                    tenant_metrics={},
                    universe_metrics={},
                )
                return {
                    "action_id": action.action_id,
                    "action_type": action.action_type,
                    "status": "COMPLETED",
                    "result": plan.as_dict(),
                }

        if action.action_type == ExecutionActionType.SAVE_EXECUTIVE_SNAPSHOT.value:
            if self.persistence_engine is not None and self.analytics_fabric is not None:
                record_id = self.persistence_engine.save_executive_snapshot(
                    snapshot_name="execution_planner_snapshot",
                    payload={
                        "fabric_summary": self.analytics_fabric.summary(),
                        "action": action.as_dict(),
                    },
                )
                return {
                    "action_id": action.action_id,
                    "action_type": action.action_type,
                    "status": "COMPLETED",
                    "record_id": record_id,
                }

        if action.action_type == ExecutionActionType.SAVE_CONTROL_TOWER_SNAPSHOT.value:
            if self.persistence_engine is not None and self.analytics_fabric is not None:
                record_id = self.persistence_engine.save_control_tower_snapshot(
                    {
                        "fabric_summary": self.analytics_fabric.summary(),
                        "action": action.as_dict(),
                    }
                )
                return {
                    "action_id": action.action_id,
                    "action_type": action.action_type,
                    "status": "COMPLETED",
                    "record_id": record_id,
                }

        return {
            "action_id": action.action_id,
            "action_type": action.action_type,
            "status": "COMPLETED",
            "message": "Action recorded. External infrastructure execution is not implemented in this planner.",
            "parameters": action.parameters,
        }

    # ------------------------------------------------------------------
    # Direct Plan Helpers
    # ------------------------------------------------------------------

    def create_scale_workers_plan(
            self,
            *,
            current_capacity: float,
            target_capacity: float,
    ) -> AutonomousExecutionPlan:
        action = self._action(
            action_type=ExecutionActionType.SCALE_WORKERS,
            title="Scale analytics workers",
            description="Scale worker fleet to the requested target capacity.",
            severity=ExecutionActionSeverity.HIGH if target_capacity > current_capacity else ExecutionActionSeverity.LOW,
            expected_impact=0.80,
            confidence_score=0.85,
            parameters={
                "current_capacity": current_capacity,
                "target_capacity": target_capacity,
                "delta": target_capacity - current_capacity,
            },
        )

        return self.build_execution_plan_from_recommendations(
            [
                {
                    "recommendation_id": action.action_id,
                    "recommendation_type": "SCALE_UP_WORKERS" if target_capacity > current_capacity else "SCALE_DOWN_WORKERS",
                    "priority": "HIGH",
                    "title": action.title,
                    "description": action.description,
                    "expected_impact": action.expected_impact,
                    "confidence_score": action.confidence_score,
                }
            ],
            title="Scale Workers Execution Plan",
            description="Direct execution plan for worker scaling.",
        )

    def create_provider_rebalance_plan(
            self,
            *,
            provider: Optional[str] = None,
    ) -> AutonomousExecutionPlan:
        recommendation = {
            "recommendation_id": f"rec_{uuid.uuid4().hex}",
            "recommendation_type": "SHIFT_PROVIDER_ALLOCATION",
            "priority": "MEDIUM",
            "title": "Rebalance analytics providers",
            "description": "Rebalance provider allocation for performance, cost, or quota reasons.",
            "expected_impact": 0.72,
            "confidence_score": 0.82,
            "provider": provider,
        }

        return self.build_execution_plan_from_recommendations(
            [recommendation],
            title="Provider Rebalance Execution Plan",
            description="Direct execution plan for provider reallocation.",
        )

    def create_governance_controls_plan(
            self,
    ) -> AutonomousExecutionPlan:
        recommendation = {
            "recommendation_id": f"rec_{uuid.uuid4().hex}",
            "recommendation_type": "ENABLE_CONSERVATIVE_MODE",
            "priority": "HIGH",
            "title": "Enable conservative analytics governance",
            "description": "Apply stricter analytics execution controls.",
            "expected_impact": 0.70,
            "confidence_score": 0.84,
        }

        return self.build_execution_plan_from_recommendations(
            [recommendation],
            title="Governance Controls Execution Plan",
            description="Direct execution plan for stricter governance controls.",
        )

    # ------------------------------------------------------------------
    # Policy / Scoring
    # ------------------------------------------------------------------

    def _apply_policy_to_action(
            self,
            action: ExecutableAnalyticsAction,
    ) -> ExecutableAnalyticsAction:
        autonomous_allowed = self._is_autonomous_allowed(action)
        requires_approval = not autonomous_allowed

        if action.expected_impact >= self.policy.critical_impact_approval_threshold:
            requires_approval = True

        elif action.expected_impact >= self.policy.high_impact_approval_threshold:
            requires_approval = True

        if action.confidence_score < self.policy.min_confidence_for_autonomous_action:
            requires_approval = True

        status = (
            ExecutionActionStatus.READY.value
            if not requires_approval
            else ExecutionActionStatus.REQUIRES_APPROVAL.value
        )

        return self._replace_action(
            action,
            autonomous_allowed=autonomous_allowed,
            requires_approval=requires_approval,
            status=status,
        )

