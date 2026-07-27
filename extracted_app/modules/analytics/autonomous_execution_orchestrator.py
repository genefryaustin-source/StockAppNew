"""
modules/analytics/autonomous_execution_orchestrator.py
"""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class OrchestrationState(str, Enum):
    PENDING = "PENDING"
    VALIDATING = "VALIDATING"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ROLLING_BACK = "ROLLING_BACK"
    ROLLED_BACK = "ROLLED_BACK"
    RECOVERING = "RECOVERING"
    CANCELLED = "CANCELLED"


class ExecutionStageType(str, Enum):
    GOVERNANCE_VALIDATION = "GOVERNANCE_VALIDATION"
    CAPACITY_PREPARATION = "CAPACITY_PREPARATION"
    PROVIDER_COORDINATION = "PROVIDER_COORDINATION"
    QUEUE_OPTIMIZATION = "QUEUE_OPTIMIZATION"
    WORKER_SCALING = "WORKER_SCALING"
    UNIVERSE_REBALANCING = "UNIVERSE_REBALANCING"
    HEALTH_VERIFICATION = "HEALTH_VERIFICATION"
    SNAPSHOT_CREATION = "SNAPSHOT_CREATION"
    COMPLETION_VERIFICATION = "COMPLETION_VERIFICATION"


class ExecutionTaskStatus(str, Enum):
    PENDING = "PENDING"
    READY = "READY"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    ROLLED_BACK = "ROLLED_BACK"


@dataclass(frozen=True)
class ExecutionDependency:
    dependency_id: str
    source_task_id: str
    target_task_id: str
    dependency_type: str = "REQUIRES_COMPLETION"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionTask:
    task_id: str
    action_id: str
    action_type: str
    stage_type: str
    status: str = ExecutionTaskStatus.PENDING.value
    title: str = ""
    description: str = ""
    requires_approval: bool = False
    autonomous_allowed: bool = False
    parameters: Dict[str, Any] = field(default_factory=dict)
    result: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    created_at: str = field(default_factory=utc_now_iso)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


@dataclass
class ExecutionStage:
    stage_id: str
    stage_type: str
    title: str
    status: str = OrchestrationState.PENDING.value
    tasks: List[ExecutionTask] = field(default_factory=list)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionSession:
    session_id: str
    plan_id: str
    state: str
    stages: List[ExecutionStage]
    started_at: str = field(default_factory=utc_now_iso)
    completed_at: Optional[str] = None
    paused_at: Optional[str] = None
    cancelled_at: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExecutionResult:
    execution_id: str
    session_id: str
    plan_id: str
    status: str
    tasks_total: int
    tasks_completed: int
    tasks_failed: int
    tasks_skipped: int
    runtime_ms: float
    results: List[Dict[str, Any]]
    started_at: str
    completed_at: str
    error: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExecutionAuditRecord:
    audit_id: str
    session_id: str
    event_type: str
    message: str
    severity: str = "INFO"
    payload: Dict[str, Any] = field(default_factory=dict)
    generated_at: str = field(default_factory=utc_now_iso)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OrchestratorMetrics:
    executions_started: int = 0
    executions_completed: int = 0
    executions_failed: int = 0
    executions_cancelled: int = 0
    rollbacks_triggered: int = 0
    recoveries_triggered: int = 0
    total_execution_time_ms: float = 0.0

    def as_dict(self) -> Dict[str, Any]:
        total_finished = self.executions_completed + self.executions_failed
        return {
            "executions_started": self.executions_started,
            "executions_completed": self.executions_completed,
            "executions_failed": self.executions_failed,
            "executions_cancelled": self.executions_cancelled,
            "rollbacks_triggered": self.rollbacks_triggered,
            "recoveries_triggered": self.recoveries_triggered,
            "average_execution_time_ms": (
                round(self.total_execution_time_ms / total_finished, 4)
                if total_finished
                else 0.0
            ),
            "success_rate": (
                round(self.executions_completed / total_finished, 4)
                if total_finished
                else 1.0
            ),
            "generated_at": utc_now_iso(),
        }


class AutonomousExecutionOrchestrator:
    """
    Coordinates approved autonomous execution plans across the Analytics Fabric.

    This orchestrator is intentionally conservative:
    - dry-run by default through execution planner behavior
    - approval-aware
    - audit-first
    - rollback-aware
    - persistence-aware
    """

    def __init__(
        self,
        *,
        execution_planner: Optional[Any] = None,
        analytics_fabric: Optional[Any] = None,
        execution_governor: Optional[Any] = None,
        persistence_engine: Optional[Any] = None,
        snapshot_scheduler: Optional[Any] = None,
        require_approval_for_real_execution: bool = True,
    ) -> None:
        self.execution_planner = execution_planner
        self.analytics_fabric = analytics_fabric
        self.execution_governor = execution_governor
        self.persistence_engine = persistence_engine
        self.snapshot_scheduler = snapshot_scheduler
        self.require_approval_for_real_execution = require_approval_for_real_execution

        self.sessions: Dict[str, ExecutionSession] = {}
        self.execution_results: List[ExecutionResult] = []
        self.audit_log: List[ExecutionAuditRecord] = []
        self.metrics = OrchestratorMetrics()

    def start_execution(
        self,
        plan: Any,
        *,
        dry_run: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ExecutionSession:
        plan_dict = self._as_dict(plan)
        plan_id = plan_dict.get("plan_id", f"plan_{uuid.uuid4().hex}")

        stages = self._build_stages_from_plan(plan)

        session = ExecutionSession(
            session_id=f"aorch_{uuid.uuid4().hex}",
            plan_id=plan_id,
            state=OrchestrationState.PENDING.value,
            stages=stages,
            metadata={
                "dry_run": dry_run,
                **(metadata or {}),
            },
        )

        self.sessions[session.session_id] = session
        self.metrics.executions_started += 1

        self._audit(
            session.session_id,
            "EXECUTION_STARTED",
            "Autonomous execution session started.",
            payload={"plan_id": plan_id, "dry_run": dry_run},
        )

        return session

    def execute_plan(
        self,
        plan: Any,
        *,
        dry_run: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:
        session = self.start_execution(
            plan,
            dry_run=dry_run,
            metadata=metadata,
        )

        started = time.perf_counter()
        started_at = utc_now_iso()
        task_results: List[Dict[str, Any]] = []

        try:
            self._validate_session(session, plan, dry_run=dry_run)
            session.state = OrchestrationState.EXECUTING.value

            for stage in session.stages:
                if session.state == OrchestrationState.CANCELLED.value:
                    break

                if session.state == OrchestrationState.PAUSED.value:
                    self._audit(
                        session.session_id,
                        "EXECUTION_PAUSED",
                        "Execution paused before stage execution.",
                        severity="WARN",
                    )
                    break

                stage_result = self.execute_stage(
                    session=session,
                    stage=stage,
                    dry_run=dry_run,
                )
                task_results.extend(stage_result)

                if any(result.get("status") == ExecutionTaskStatus.FAILED.value for result in stage_result):
                    raise RuntimeError(f"Stage failed: {stage.stage_type}")

            if session.state not in {OrchestrationState.PAUSED.value, OrchestrationState.CANCELLED.value}:
                session.state = OrchestrationState.COMPLETED.value
                session.completed_at = utc_now_iso()
                self.metrics.executions_completed += 1

            runtime_ms = round((time.perf_counter() - started) * 1000.0, 4)
            self.metrics.total_execution_time_ms += runtime_ms

            result = ExecutionResult(
                execution_id=f"aorchres_{uuid.uuid4().hex}",
                session_id=session.session_id,
                plan_id=session.plan_id,
                status=session.state,
                tasks_total=self._count_tasks(session),
                tasks_completed=self._count_tasks_by_status(session, ExecutionTaskStatus.COMPLETED.value),
                tasks_failed=self._count_tasks_by_status(session, ExecutionTaskStatus.FAILED.value),
                tasks_skipped=self._count_tasks_by_status(session, ExecutionTaskStatus.SKIPPED.value),
                runtime_ms=runtime_ms,
                results=task_results,
                started_at=started_at,
                completed_at=utc_now_iso(),
            )

            self.execution_results.append(result)

            self._audit(
                session.session_id,
                "EXECUTION_COMPLETED",
                "Autonomous execution session completed.",
                payload=result.as_dict(),
            )

            self._persist_execution_result(result)

            return result

        except Exception as exc:
            session.state = OrchestrationState.FAILED.value
            session.error = str(exc)
            session.completed_at = utc_now_iso()
            self.metrics.executions_failed += 1

            runtime_ms = round((time.perf_counter() - started) * 1000.0, 4)
            self.metrics.total_execution_time_ms += runtime_ms

            self._audit(
                session.session_id,
                "EXECUTION_FAILED",
                str(exc),
                severity="ERROR",
                payload={"plan_id": session.plan_id},
            )

            rollback = self.rollback_execution(session.session_id)

            result = ExecutionResult(
                execution_id=f"aorchres_{uuid.uuid4().hex}",
                session_id=session.session_id,
                plan_id=session.plan_id,
                status=OrchestrationState.FAILED.value,
                tasks_total=self._count_tasks(session),
                tasks_completed=self._count_tasks_by_status(session, ExecutionTaskStatus.COMPLETED.value),
                tasks_failed=self._count_tasks_by_status(session, ExecutionTaskStatus.FAILED.value),
                tasks_skipped=self._count_tasks_by_status(session, ExecutionTaskStatus.SKIPPED.value),
                runtime_ms=runtime_ms,
                results=[
                    *task_results,
                    {"rollback": rollback},
                ],
                started_at=started_at,
                completed_at=utc_now_iso(),
                error=str(exc),
            )

            self.execution_results.append(result)
            self._persist_execution_result(result)

            return result

    def execute_stage(
        self,
        *,
        session: ExecutionSession,
        stage: ExecutionStage,
        dry_run: bool = True,
    ) -> List[Dict[str, Any]]:
        stage.status = OrchestrationState.EXECUTING.value
        stage.started_at = utc_now_iso()

        self._audit(
            session.session_id,
            "STAGE_STARTED",
            f"Stage started: {stage.stage_type}",
            payload={"stage_id": stage.stage_id},
        )

        results: List[Dict[str, Any]] = []

        for task in stage.tasks:
            result = self.execute_task(
                session=session,
                task=task,
                dry_run=dry_run,
            )
            results.append(result)

            if result.get("status") == ExecutionTaskStatus.FAILED.value:
                stage.status = OrchestrationState.FAILED.value
                stage.completed_at = utc_now_iso()
                return results

        stage.status = OrchestrationState.COMPLETED.value
        stage.completed_at = utc_now_iso()

        self._audit(
            session.session_id,
            "STAGE_COMPLETED",
            f"Stage completed: {stage.stage_type}",
            payload={"stage_id": stage.stage_id, "tasks": len(stage.tasks)},
        )

        return results

    def execute_task(
        self,
        *,
        session: ExecutionSession,
        task: ExecutionTask,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        task.status = ExecutionTaskStatus.EXECUTING.value
        task.started_at = utc_now_iso()

        try:
            if task.requires_approval and not dry_run:
                task.status = ExecutionTaskStatus.SKIPPED.value
                task.completed_at = utc_now_iso()
                task.result = {"reason": "Task requires approval."}
                return self._task_result(task)

            result = self.execute_action(task, dry_run=dry_run)

            task.status = ExecutionTaskStatus.COMPLETED.value
            task.completed_at = utc_now_iso()
            task.result = result

            self._audit(
                session.session_id,
                "TASK_COMPLETED",
                f"Task completed: {task.action_type}",
                payload={"task_id": task.task_id, "result": result},
            )

            return self._task_result(task)

        except Exception as exc:
            task.status = ExecutionTaskStatus.FAILED.value
            task.completed_at = utc_now_iso()
            task.error = str(exc)

            self._audit(
                session.session_id,
                "TASK_FAILED",
                str(exc),
                severity="ERROR",
                payload={"task_id": task.task_id, "action_type": task.action_type},
            )

            return self._task_result(task)

    def execute_action(
        self,
        task: ExecutionTask,
        *,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        if self.execution_planner is not None:
            action_like = self._task_to_action_like(task)
            return self.execution_planner.execute_action(action_like, dry_run=dry_run)

        return {
            "task_id": task.task_id,
            "action_type": task.action_type,
            "status": ExecutionTaskStatus.COMPLETED.value,
            "dry_run": dry_run,
            "message": "Task recorded by orchestrator. No execution planner attached.",
            "parameters": task.parameters,
        }

    def pause_execution(self, session_id: str) -> bool:
        session = self.sessions.get(session_id)
        if not session:
            return False

        session.state = OrchestrationState.PAUSED.value
        session.paused_at = utc_now_iso()

        self._audit(session_id, "EXECUTION_PAUSED", "Execution paused.")
        return True

    def resume_execution(self, session_id: str, *, dry_run: bool = True) -> Optional[ExecutionResult]:
        session = self.sessions.get(session_id)
        if not session:
            return None

        session.state = OrchestrationState.EXECUTING.value
        self._audit(session_id, "EXECUTION_RESUMED", "Execution resumed.")

        return self._resume_session(session, dry_run=dry_run)

    def cancel_execution(self, session_id: str, reason: str = "Cancelled by operator.") -> bool:
        session = self.sessions.get(session_id)
        if not session:
            return False

        session.state = OrchestrationState.CANCELLED.value
        session.cancelled_at = utc_now_iso()
        session.completed_at = utc_now_iso()
        self.metrics.executions_cancelled += 1

        self._audit(
            session_id,
            "EXECUTION_CANCELLED",
            reason,
            severity="WARN",
        )

        return True

    def rollback_execution(self, session_id: str) -> Dict[str, Any]:
        session = self.sessions.get(session_id)
        if not session:
            return {"status": "NOT_FOUND", "session_id": session_id}

        session.state = OrchestrationState.ROLLING_BACK.value
        self.metrics.rollbacks_triggered += 1

        rolled_back_tasks = []

        for stage in reversed(session.stages):
            for task in reversed(stage.tasks):
                if task.status == ExecutionTaskStatus.COMPLETED.value:
                    task.status = ExecutionTaskStatus.ROLLED_BACK.value
                    rolled_back_tasks.append(task.task_id)

        session.state = OrchestrationState.ROLLED_BACK.value

        result = {
            "status": "ROLLED_BACK",
            "session_id": session_id,
            "rolled_back_tasks": rolled_back_tasks,
            "generated_at": utc_now_iso(),
        }

        self._audit(
            session_id,
            "EXECUTION_ROLLED_BACK",
            "Rollback completed.",
            severity="WARN",
            payload=result,
        )

        return result

    def recover_execution(self, session_id: str) -> Dict[str, Any]:
        session = self.sessions.get(session_id)
        if not session:
            return {"status": "NOT_FOUND", "session_id": session_id}

        session.state = OrchestrationState.RECOVERING.value
        self.metrics.recoveries_triggered += 1

        for stage in session.stages:
            if stage.status == OrchestrationState.FAILED.value:
                stage.status = OrchestrationState.PENDING.value

            for task in stage.tasks:
                if task.status == ExecutionTaskStatus.FAILED.value:
                    task.status = ExecutionTaskStatus.PENDING.value
                    task.error = None

        session.state = OrchestrationState.PENDING.value

        result = {
            "status": "RECOVERED",
            "session_id": session_id,
            "generated_at": utc_now_iso(),
        }

        self._audit(
            session_id,
            "EXECUTION_RECOVERED",
            "Execution recovered and reset to pending.",
            payload=result,
        )

        return result

    def execution_status(self, session_id: str) -> Dict[str, Any]:
        session = self.sessions.get(session_id)
        if not session:
            return {"status": "NOT_FOUND", "session_id": session_id}

        return session.as_dict()

    def execution_summary(self) -> Dict[str, Any]:
        active_sessions = len(
            [
                s for s in self.sessions.values()
                if s.state in {
                    OrchestrationState.PENDING.value,
                    OrchestrationState.VALIDATING.value,
                    OrchestrationState.EXECUTING.value,
                    OrchestrationState.PAUSED.value,
                    OrchestrationState.RECOVERING.value,
                }
            ]
        )

        return {
            **self.metrics.as_dict(),
            "sessions_total": len(self.sessions),
            "active_sessions": active_sessions,
            "audit_records": len(self.audit_log),
            "results": len(self.execution_results),
            "generated_at": utc_now_iso(),
        }

    def audit_history(self, limit: int = 1000) -> List[Dict[str, Any]]:
        return [record.as_dict() for record in self.audit_log[-limit:]]

    def result_history(self, limit: int = 1000) -> List[Dict[str, Any]]:
        return [result.as_dict() for result in self.execution_results[-limit:]]

    def session_registry(self) -> List[Dict[str, Any]]:
        return [session.as_dict() for session in self.sessions.values()]

    def _validate_session(self, session: ExecutionSession, plan: Any, *, dry_run: bool) -> None:
        session.state = OrchestrationState.VALIDATING.value

        plan_dict = self._as_dict(plan)

        if not dry_run and self.require_approval_for_real_execution:
            state = str(plan_dict.get("state", "")).upper()
            if state not in {"APPROVED", "READY"}:
                raise PermissionError("Plan must be approved or ready before real execution.")

        pending = int(plan_dict.get("pending_approval_actions", 0) or 0)

        if pending > 0 and not dry_run:
            raise PermissionError("Plan contains approval-required actions.")

        session.state = OrchestrationState.APPROVED.value

        self._audit(
            session.session_id,
            "GOVERNANCE_VALIDATED",
            "Execution session passed validation.",
            payload={"dry_run": dry_run},
        )

    def _build_stages_from_plan(self, plan: Any) -> List[ExecutionStage]:
        plan_dict = self._as_dict(plan)
        actions = plan_dict.get("actions", [])

        stage_map: Dict[str, ExecutionStage] = {
            stage.value: ExecutionStage(
                stage_id=f"stage_{uuid.uuid4().hex}",
                stage_type=stage.value,
                title=stage.value.replace("_", " ").title(),
            )
            for stage in ExecutionStageType
        }

        for action in actions:
            action_dict = self._as_dict(action)
            stage_type = self._stage_for_action(action_dict.get("action_type", ""))

            task = ExecutionTask(
                task_id=f"task_{uuid.uuid4().hex}",
                action_id=action_dict.get("action_id", f"action_{uuid.uuid4().hex}"),
                action_type=action_dict.get("action_type", "UNKNOWN"),
                stage_type=stage_type,
                title=action_dict.get("title", ""),
                description=action_dict.get("description", ""),
                requires_approval=bool(action_dict.get("requires_approval", True)),
                autonomous_allowed=bool(action_dict.get("autonomous_allowed", False)),
                parameters=action_dict.get("parameters", {}),
            )

            stage_map[stage_type].tasks.append(task)

        return [stage for stage in stage_map.values() if stage.tasks]

    def _stage_for_action(self, action_type: str) -> str:
        action_type = str(action_type).upper()

        if "GOVERNANCE" in action_type or "CONSERVATIVE" in action_type:
            return ExecutionStageType.GOVERNANCE_VALIDATION.value

        if "CAPACITY" in action_type or "BATCH" in action_type:
            return ExecutionStageType.CAPACITY_PREPARATION.value

        if "PROVIDER" in action_type or "SPEND" in action_type:
            return ExecutionStageType.PROVIDER_COORDINATION.value

        if "QUEUE" in action_type:
            return ExecutionStageType.QUEUE_OPTIMIZATION.value

        if "WORKER" in action_type or "NODE" in action_type:
            return ExecutionStageType.WORKER_SCALING.value

        if "UNIVERSE" in action_type or "GLOBAL_PLAN" in action_type:
            return ExecutionStageType.UNIVERSE_REBALANCING.value

        if "SNAPSHOT" in action_type:
            return ExecutionStageType.SNAPSHOT_CREATION.value

        if "HEALTH" in action_type:
            return ExecutionStageType.HEALTH_VERIFICATION.value

        return ExecutionStageType.COMPLETION_VERIFICATION.value

    def _resume_session(self, session: ExecutionSession, *, dry_run: bool) -> ExecutionResult:
        started = time.perf_counter()
        started_at = utc_now_iso()
        results = []

        failed = 0
        completed = 0

        for stage in session.stages:
            if stage.status == OrchestrationState.COMPLETED.value:
                continue

            stage_result = self.execute_stage(session=session, stage=stage, dry_run=dry_run)
            results.extend(stage_result)

            if any(r.get("status") == ExecutionTaskStatus.FAILED.value for r in stage_result):
                failed += 1
                break

            completed += len(stage_result)

        session.state = OrchestrationState.COMPLETED.value if failed == 0 else OrchestrationState.FAILED.value
        session.completed_at = utc_now_iso()

        runtime_ms = round((time.perf_counter() - started) * 1000.0, 4)

        result = ExecutionResult(
            execution_id=f"aorchres_{uuid.uuid4().hex}",
            session_id=session.session_id,
            plan_id=session.plan_id,
            status=session.state,
            tasks_total=self._count_tasks(session),
            tasks_completed=self._count_tasks_by_status(session, ExecutionTaskStatus.COMPLETED.value),
            tasks_failed=self._count_tasks_by_status(session, ExecutionTaskStatus.FAILED.value),
            tasks_skipped=self._count_tasks_by_status(session, ExecutionTaskStatus.SKIPPED.value),
            runtime_ms=runtime_ms,
            results=results,
            started_at=started_at,
            completed_at=utc_now_iso(),
        )

        self.execution_results.append(result)
        return result

    def _task_result(self, task: ExecutionTask) -> Dict[str, Any]:
        return {
            "task_id": task.task_id,
            "action_id": task.action_id,
            "action_type": task.action_type,
            "stage_type": task.stage_type,
            "status": task.status,
            "result": task.result,
            "error": task.error,
            "started_at": task.started_at,
            "completed_at": task.completed_at,
        }

    def _task_to_action_like(self, task: ExecutionTask) -> Any:
        class ActionLike:
            pass

        action = ActionLike()
        action.action_id = task.action_id
        action.action_type = task.action_type
        action.title = task.title
        action.description = task.description
        action.requires_approval = task.requires_approval
        action.autonomous_allowed = task.autonomous_allowed
        action.parameters = task.parameters
        return action

    def _audit(
        self,
        session_id: str,
        event_type: str,
        message: str,
        *,
        severity: str = "INFO",
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.audit_log.append(
            ExecutionAuditRecord(
                audit_id=f"audit_{uuid.uuid4().hex}",
                session_id=session_id,
                event_type=event_type,
                message=message,
                severity=severity,
                payload=payload or {},
            )
        )

        if len(self.audit_log) > 10000:
            self.audit_log = self.audit_log[-10000:]

    def _persist_execution_result(self, result: ExecutionResult) -> None:
        if self.persistence_engine is None:
            return

        try:
            self.persistence_engine.save_executive_snapshot(
                snapshot_name="autonomous_execution_result",
                payload=result.as_dict(),
            )
        except Exception:
            pass

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

    @staticmethod
    def _count_tasks(session: ExecutionSession) -> int:
        return sum(len(stage.tasks) for stage in session.stages)

    @staticmethod
    def _count_tasks_by_status(session: ExecutionSession, status: str) -> int:
        return sum(
            len([task for task in stage.tasks if task.status == status])
            for stage in session.stages
        )


def create_autonomous_execution_orchestrator(
    *,
    execution_planner: Optional[Any] = None,
    analytics_fabric: Optional[Any] = None,
    execution_governor: Optional[Any] = None,
    persistence_engine: Optional[Any] = None,
    snapshot_scheduler: Optional[Any] = None,
    require_approval_for_real_execution: bool = True,
) -> AutonomousExecutionOrchestrator:
    return AutonomousExecutionOrchestrator(
        execution_planner=execution_planner,
        analytics_fabric=analytics_fabric,
        execution_governor=execution_governor,
        persistence_engine=persistence_engine,
        snapshot_scheduler=snapshot_scheduler,
        require_approval_for_real_execution=require_approval_for_real_execution,
    )