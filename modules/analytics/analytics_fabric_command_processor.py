"""
modules/analytics/analytics_fabric_command_processor.py
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AnalyticsCommandType(str, Enum):
    START_RUNTIME = "START_RUNTIME"
    STOP_RUNTIME = "STOP_RUNTIME"
    PAUSE_RUNTIME = "PAUSE_RUNTIME"
    RESUME_RUNTIME = "RESUME_RUNTIME"

    RUN_FORECAST = "RUN_FORECAST"
    RUN_OPTIMIZATION = "RUN_OPTIMIZATION"
    RUN_PLANNING = "RUN_PLANNING"
    RUN_EXECUTION = "RUN_EXECUTION"
    RUN_AUTONOMOUS_CYCLE = "RUN_AUTONOMOUS_CYCLE"
    RUN_RECOVERY = "RUN_RECOVERY"

    CREATE_SNAPSHOT = "CREATE_SNAPSHOT"
    RUN_SUPERVISOR_CYCLE = "RUN_SUPERVISOR_CYCLE"
    RUN_CONTINUOUS_RUNTIME_TICK = "RUN_CONTINUOUS_RUNTIME_TICK"

    EXPORT_STATE = "EXPORT_STATE"
    EXPORT_METRICS = "EXPORT_METRICS"
    EXPORT_EXECUTIVE_PACKAGE = "EXPORT_EXECUTIVE_PACKAGE"


class AnalyticsCommandStatus(str, Enum):
    RECEIVED = "RECEIVED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AnalyticsCommandSeverity(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class AnalyticsCommand:
    command_id: str
    command_type: str
    requested_by: str = "system"
    status: str = AnalyticsCommandStatus.RECEIVED.value
    severity: str = AnalyticsCommandSeverity.INFO.value
    requires_approval: bool = False
    payload: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    approved_at: Optional[str] = None
    rejected_at: Optional[str] = None
    executed_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AnalyticsCommandResult:
    result_id: str
    command_id: str
    command_type: str
    status: str
    result: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    started_at: str = field(default_factory=utc_now_iso)
    completed_at: str = field(default_factory=utc_now_iso)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AnalyticsCommandBatch:
    batch_id: str
    commands: List[AnalyticsCommand]
    status: str = AnalyticsCommandStatus.RECEIVED.value
    created_at: str = field(default_factory=utc_now_iso)
    completed_at: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "status": self.status,
            "commands": [c.as_dict() for c in self.commands],
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


@dataclass
class AnalyticsCommandAudit:
    audit_id: str
    command_id: Optional[str]
    event_type: str
    message: str
    severity: str = AnalyticsCommandSeverity.INFO.value
    payload: Dict[str, Any] = field(default_factory=dict)
    generated_at: str = field(default_factory=utc_now_iso)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AnalyticsCommandApproval:
    approval_id: str
    command_id: str
    approved: bool
    approved_by: str
    reason: str = ""
    generated_at: str = field(default_factory=utc_now_iso)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AnalyticsCommandExecution:
    execution_id: str
    command_id: str
    command_type: str
    status: str
    started_at: str
    completed_at: Optional[str] = None
    result_id: Optional[str] = None
    error: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AnalyticsCommandMetrics:
    commands_received: int = 0
    commands_executed: int = 0
    commands_failed: int = 0
    commands_approved: int = 0
    commands_rejected: int = 0
    batch_commands_executed: int = 0

    def as_dict(self) -> Dict[str, Any]:
        total_finished = self.commands_executed + self.commands_failed
        return {
            "commands_received": self.commands_received,
            "commands_executed": self.commands_executed,
            "commands_failed": self.commands_failed,
            "commands_approved": self.commands_approved,
            "commands_rejected": self.commands_rejected,
            "batch_commands_executed": self.batch_commands_executed,
            "success_rate": (
                round(self.commands_executed / total_finished, 4)
                if total_finished
                else 1.0
            ),
            "generated_at": utc_now_iso(),
        }


class AnalyticsFabricCommandProcessor:
    """
    Central command bus for the Analytics Fabric control plane.

    Dashboards should submit commands here instead of directly calling runtime
    services. This provides consistent audit, approval, metrics, and execution
    history.
    """

    def __init__(
        self,
        *,
        continuous_runtime_engine: Optional[Any] = None,
        supervisor: Optional[Any] = None,
        runtime_controller: Optional[Any] = None,
        orchestrator: Optional[Any] = None,
        persistence_engine: Optional[Any] = None,
        require_approval_for_runtime_stop: bool = True,
        require_approval_for_real_execution: bool = True,
        require_approval_for_recovery: bool = False,
    ) -> None:
        self.continuous_runtime_engine = continuous_runtime_engine
        self.supervisor = supervisor
        self.runtime_controller = runtime_controller
        self.orchestrator = orchestrator
        self.persistence_engine = persistence_engine

        self.require_approval_for_runtime_stop = require_approval_for_runtime_stop
        self.require_approval_for_real_execution = require_approval_for_real_execution
        self.require_approval_for_recovery = require_approval_for_recovery

        self.commands: Dict[str, AnalyticsCommand] = {}
        self.command_results: Dict[str, AnalyticsCommandResult] = {}
        self.batches: Dict[str, AnalyticsCommandBatch] = {}
        self.approvals: List[AnalyticsCommandApproval] = []
        self.audit_log: List[AnalyticsCommandAudit] = []
        self.executions: List[AnalyticsCommandExecution] = []
        self.metrics = AnalyticsCommandMetrics()

    # ------------------------------------------------------------------
    # Submission
    # ------------------------------------------------------------------

    def submit_command(
        self,
        command_type: str,
        *,
        requested_by: str = "system",
        payload: Optional[Dict[str, Any]] = None,
        severity: str = AnalyticsCommandSeverity.INFO.value,
        requires_approval: Optional[bool] = None,
        execute_immediately: bool = False,
    ) -> AnalyticsCommand:
        normalized_type = self._normalize_command_type(command_type)

        if requires_approval is None:
            requires_approval = self._requires_approval(normalized_type, payload or {})

        status = (
            AnalyticsCommandStatus.PENDING_APPROVAL.value
            if requires_approval
            else AnalyticsCommandStatus.RECEIVED.value
        )

        command = AnalyticsCommand(
            command_id=f"cmd_{uuid.uuid4().hex}",
            command_type=normalized_type,
            requested_by=requested_by,
            status=status,
            severity=severity,
            requires_approval=requires_approval,
            payload=payload or {},
        )

        self.commands[command.command_id] = command
        self.metrics.commands_received += 1

        self._audit(
            command.command_id,
            "COMMAND_RECEIVED",
            f"Command received: {normalized_type}",
            payload=command.as_dict(),
        )

        self._persist_command(command)

        if execute_immediately and not requires_approval:
            self.execute_command(command.command_id)

        return command

    def submit_batch(
        self,
        commands: Iterable[Dict[str, Any]],
        *,
        requested_by: str = "system",
        execute_immediately: bool = False,
    ) -> AnalyticsCommandBatch:
        submitted: List[AnalyticsCommand] = []

        for item in commands:
            submitted.append(
                self.submit_command(
                    item.get("command_type") or item.get("type"),
                    requested_by=item.get("requested_by", requested_by),
                    payload=item.get("payload", {}),
                    severity=item.get("severity", AnalyticsCommandSeverity.INFO.value),
                    requires_approval=item.get("requires_approval"),
                    execute_immediately=False,
                )
            )

        batch = AnalyticsCommandBatch(
            batch_id=f"batch_{uuid.uuid4().hex}",
            commands=submitted,
        )

        self.batches[batch.batch_id] = batch

        self._audit(
            None,
            "COMMAND_BATCH_RECEIVED",
            f"Command batch received: {batch.batch_id}",
            payload=batch.as_dict(),
        )

        self._persist_command_batch(batch)

        if execute_immediately:
            self.execute_batch(batch.batch_id)

        return batch

    # ------------------------------------------------------------------
    # Approval
    # ------------------------------------------------------------------

    def approve_command(
        self,
        command_id: str,
        *,
        approved_by: str = "operator",
        reason: str = "",
        execute_after_approval: bool = False,
    ) -> AnalyticsCommand:
        command = self._get_command_or_raise(command_id)

        command.status = AnalyticsCommandStatus.APPROVED.value
        command.approved_at = utc_now_iso()
        command.requires_approval = False

        approval = AnalyticsCommandApproval(
            approval_id=f"approval_{uuid.uuid4().hex}",
            command_id=command_id,
            approved=True,
            approved_by=approved_by,
            reason=reason,
        )

        self.approvals.append(approval)
        self.metrics.commands_approved += 1

        self._audit(
            command_id,
            "COMMAND_APPROVED",
            "Command approved.",
            payload=approval.as_dict(),
        )

        if execute_after_approval:
            self.execute_command(command_id)

        return command

    def reject_command(
        self,
        command_id: str,
        *,
        rejected_by: str = "operator",
        reason: str = "",
    ) -> AnalyticsCommand:
        command = self._get_command_or_raise(command_id)

        command.status = AnalyticsCommandStatus.REJECTED.value
        command.rejected_at = utc_now_iso()

        approval = AnalyticsCommandApproval(
            approval_id=f"approval_{uuid.uuid4().hex}",
            command_id=command_id,
            approved=False,
            approved_by=rejected_by,
            reason=reason,
        )

        self.approvals.append(approval)
        self.metrics.commands_rejected += 1

        self._audit(
            command_id,
            "COMMAND_REJECTED",
            "Command rejected.",
            severity=AnalyticsCommandSeverity.MEDIUM.value,
            payload=approval.as_dict(),
        )

        return command

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute_command(
        self,
        command_id: str,
    ) -> AnalyticsCommandResult:
        command = self._get_command_or_raise(command_id)

        if command.status == AnalyticsCommandStatus.REJECTED.value:
            raise PermissionError("Rejected command cannot be executed.")

        if command.requires_approval:
            raise PermissionError("Command requires approval before execution.")

        command.status = AnalyticsCommandStatus.EXECUTING.value
        command.executed_at = utc_now_iso()

        execution = AnalyticsCommandExecution(
            execution_id=f"cmdexec_{uuid.uuid4().hex}",
            command_id=command.command_id,
            command_type=command.command_type,
            status=AnalyticsCommandStatus.EXECUTING.value,
            started_at=utc_now_iso(),
        )

        self.executions.append(execution)

        try:
            result_payload = self._dispatch_command(command)

            command.status = AnalyticsCommandStatus.COMPLETED.value
            command.completed_at = utc_now_iso()

            result = AnalyticsCommandResult(
                result_id=f"cmdres_{uuid.uuid4().hex}",
                command_id=command.command_id,
                command_type=command.command_type,
                status=AnalyticsCommandStatus.COMPLETED.value,
                result=result_payload,
                started_at=execution.started_at,
                completed_at=utc_now_iso(),
            )

            execution.status = AnalyticsCommandStatus.COMPLETED.value
            execution.completed_at = result.completed_at
            execution.result_id = result.result_id

            self.command_results[result.result_id] = result
            self.metrics.commands_executed += 1

            self._audit(
                command.command_id,
                "COMMAND_COMPLETED",
                f"Command completed: {command.command_type}",
                payload=result.as_dict(),
            )

            self._persist_command_result(result)
            return result

        except Exception as exc:
            command.status = AnalyticsCommandStatus.FAILED.value
            command.completed_at = utc_now_iso()
            command.error = str(exc)

            result = AnalyticsCommandResult(
                result_id=f"cmdres_{uuid.uuid4().hex}",
                command_id=command.command_id,
                command_type=command.command_type,
                status=AnalyticsCommandStatus.FAILED.value,
                result={},
                error=str(exc),
                started_at=execution.started_at,
                completed_at=utc_now_iso(),
            )

            execution.status = AnalyticsCommandStatus.FAILED.value
            execution.completed_at = result.completed_at
            execution.error = str(exc)
            execution.result_id = result.result_id

            self.command_results[result.result_id] = result
            self.metrics.commands_failed += 1

            self._audit(
                command.command_id,
                "COMMAND_FAILED",
                str(exc),
                severity=AnalyticsCommandSeverity.HIGH.value,
                payload=result.as_dict(),
            )

            self._persist_command_result(result)
            return result

    def execute_batch(
        self,
        batch_id: str,
    ) -> Dict[str, Any]:
        batch = self.batches.get(batch_id)

        if batch is None:
            raise KeyError(f"Command batch not found: {batch_id}")

        batch.status = AnalyticsCommandStatus.EXECUTING.value

        results = []

        for command in batch.commands:
            if command.requires_approval:
                results.append(
                    {
                        "command_id": command.command_id,
                        "status": "SKIPPED",
                        "reason": "Command requires approval.",
                    }
                )
                continue

            result = self.execute_command(command.command_id)
            results.append(result.as_dict())
            self.metrics.batch_commands_executed += 1

        failed = [r for r in results if r.get("status") == AnalyticsCommandStatus.FAILED.value]

        batch.status = (
            AnalyticsCommandStatus.FAILED.value
            if failed
            else AnalyticsCommandStatus.COMPLETED.value
        )
        batch.completed_at = utc_now_iso()

        payload = {
            "batch_id": batch_id,
            "status": batch.status,
            "results": results,
            "completed_at": batch.completed_at,
        }

        self._audit(
            None,
            "COMMAND_BATCH_COMPLETED",
            f"Command batch completed: {batch_id}",
            payload=payload,
        )

        return payload

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def _dispatch_command(
        self,
        command: AnalyticsCommand,
    ) -> Dict[str, Any]:
        command_type = command.command_type
        payload = command.payload or {}

        if command_type == AnalyticsCommandType.START_RUNTIME.value:
            target = self.continuous_runtime_engine or self.runtime_controller
            return self._call_target(target, "start_runtime")

        if command_type == AnalyticsCommandType.STOP_RUNTIME.value:
            target = self.continuous_runtime_engine or self.runtime_controller
            return self._call_target(target, "stop_runtime")

        if command_type == AnalyticsCommandType.PAUSE_RUNTIME.value:
            target = self.continuous_runtime_engine or self.runtime_controller
            return self._call_target(target, "pause_runtime")

        if command_type == AnalyticsCommandType.RESUME_RUNTIME.value:
            target = self.continuous_runtime_engine or self.runtime_controller
            return self._call_target(target, "resume_runtime")

        if command_type == AnalyticsCommandType.RUN_FORECAST.value:
            return self._call_target(self.runtime_controller, "run_forecasting_cycle")

        if command_type == AnalyticsCommandType.RUN_OPTIMIZATION.value:
            return self._call_target(self.runtime_controller, "run_optimization_cycle")

        if command_type == AnalyticsCommandType.RUN_PLANNING.value:
            return self._call_target(self.runtime_controller, "run_planning_cycle")

        if command_type == AnalyticsCommandType.RUN_EXECUTION.value:
            return self._call_target(self.runtime_controller, "run_execution_cycle")

        if command_type == AnalyticsCommandType.RUN_AUTONOMOUS_CYCLE.value:
            if self.continuous_runtime_engine is not None:
                return self._call_target(self.continuous_runtime_engine, "run_supervisor_cycle", force=True)
            if self.supervisor is not None:
                return self._call_target(self.supervisor, "run_autonomous_cycle")
            return self._call_target(self.runtime_controller, "run_autonomous_cycle")

        if command_type == AnalyticsCommandType.RUN_RECOVERY.value:
            if self.continuous_runtime_engine is not None:
                return self._call_target(self.continuous_runtime_engine, "run_recovery_cycle")
            if self.supervisor is not None:
                return self._call_target(self.supervisor, "run_recovery_cycle")
            return self._call_target(self.runtime_controller, "run_recovery_cycle")

        if command_type == AnalyticsCommandType.CREATE_SNAPSHOT.value:
            if self.continuous_runtime_engine is not None:
                return self._call_target(self.continuous_runtime_engine, "run_snapshot_cycle")
            if self.supervisor is not None:
                snapshot = self.supervisor.supervisor_snapshot()
                return self._as_dict(snapshot)
            snapshot = self.runtime_controller.runtime_snapshot()
            return self._as_dict(snapshot)

        if command_type == AnalyticsCommandType.RUN_SUPERVISOR_CYCLE.value:
            return self._call_target(
                self.supervisor,
                "run_supervisor_cycle",
                force=bool(payload.get("force", False)),
            )

        if command_type == AnalyticsCommandType.RUN_CONTINUOUS_RUNTIME_TICK.value:
            return self._call_target(
                self.continuous_runtime_engine,
                "run_once",
                force=bool(payload.get("force", False)),
            )

        if command_type == AnalyticsCommandType.EXPORT_STATE.value:
            return self.export_state()

        if command_type == AnalyticsCommandType.EXPORT_METRICS.value:
            return self.command_metrics()

        if command_type == AnalyticsCommandType.EXPORT_EXECUTIVE_PACKAGE.value:
            return self.export_executive_package()

        raise ValueError(f"Unsupported command type: {command_type}")

    # ------------------------------------------------------------------
    # Status / History / Metrics
    # ------------------------------------------------------------------

    def command_status(
        self,
        command_id: str,
    ) -> Dict[str, Any]:
        command = self._get_command_or_raise(command_id)
        results = [
            result.as_dict()
            for result in self.command_results.values()
            if result.command_id == command_id
        ]

        return {
            "command": command.as_dict(),
            "results": results,
            "generated_at": utc_now_iso(),
        }

    def command_history(
        self,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        commands = sorted(
            self.commands.values(),
            key=lambda item: item.created_at,
            reverse=True,
        )
        return [command.as_dict() for command in commands[:limit]]

    def command_result_history(
        self,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        results = sorted(
            self.command_results.values(),
            key=lambda item: item.completed_at,
            reverse=True,
        )
        return [result.as_dict() for result in results[:limit]]

    def command_audit_history(
        self,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        return [record.as_dict() for record in self.audit_log[-limit:]]

    def command_execution_history(
        self,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        return [execution.as_dict() for execution in self.executions[-limit:]]

    def command_batch_history(
        self,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        batches = sorted(
            self.batches.values(),
            key=lambda item: item.created_at,
            reverse=True,
        )
        return [batch.as_dict() for batch in batches[:limit]]

    def command_metrics(self) -> Dict[str, Any]:
        pending = len(
            [
                command for command in self.commands.values()
                if command.status == AnalyticsCommandStatus.PENDING_APPROVAL.value
            ]
        )

        return {
            **self.metrics.as_dict(),
            "commands_total": len(self.commands),
            "pending_approval": pending,
            "results_total": len(self.command_results),
            "batches_total": len(self.batches),
            "audit_records": len(self.audit_log),
            "executions_total": len(self.executions),
            "generated_at": utc_now_iso(),
        }

    def export_command_history(self) -> Dict[str, Any]:
        return {
            "commands": self.command_history(limit=10000),
            "results": self.command_result_history(limit=10000),
            "batches": self.command_batch_history(limit=10000),
            "approvals": [approval.as_dict() for approval in self.approvals],
            "audit": self.command_audit_history(limit=10000),
            "executions": self.command_execution_history(limit=10000),
            "metrics": self.command_metrics(),
            "generated_at": utc_now_iso(),
        }

    def export_state(self) -> Dict[str, Any]:
        return {
            "command_processor": self.export_command_history(),
            "continuous_runtime": self._safe_export(self.continuous_runtime_engine),
            "supervisor": self._safe_status(self.supervisor, "supervisor_status"),
            "runtime_controller": self._safe_status(self.runtime_controller, "runtime_status"),
            "generated_at": utc_now_iso(),
        }

    def export_executive_package(self) -> Dict[str, Any]:
        return {
            "metrics": self.command_metrics(),
            "recent_commands": self.command_history(limit=100),
            "recent_results": self.command_result_history(limit=100),
            "recent_audit": self.command_audit_history(limit=100),
            "continuous_runtime": self._safe_status(self.continuous_runtime_engine, "runtime_summary"),
            "supervisor": self._safe_status(self.supervisor, "supervisor_status"),
            "runtime_controller": self._safe_status(self.runtime_controller, "runtime_summary"),
            "generated_at": utc_now_iso(),
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save_command(
        self,
        command: AnalyticsCommand,
    ) -> None:
        self._persist_command(command)

    def save_command_result(
        self,
        result: AnalyticsCommandResult,
    ) -> None:
        self._persist_command_result(result)

    def save_command_audit(
        self,
        audit: AnalyticsCommandAudit,
    ) -> None:
        self._persist_audit(audit)

    def save_command_batch(
        self,
        batch: AnalyticsCommandBatch,
    ) -> None:
        self._persist_command_batch(batch)

    def _persist_command(
        self,
        command: AnalyticsCommand,
    ) -> None:
        if self.persistence_engine is None:
            return

        try:
            self.persistence_engine.save_executive_snapshot(
                snapshot_name="analytics_command",
                payload=command.as_dict(),
            )
        except Exception:
            pass

    def _persist_command_result(
        self,
        result: AnalyticsCommandResult,
    ) -> None:
        if self.persistence_engine is None:
            return

        try:
            self.persistence_engine.save_executive_snapshot(
                snapshot_name="analytics_command_result",
                payload=result.as_dict(),
            )
        except Exception:
            pass

    def _persist_audit(
        self,
        audit: AnalyticsCommandAudit,
    ) -> None:
        if self.persistence_engine is None:
            return

        try:
            self.persistence_engine.save_governance_decision(
                decision_type="analytics_command_audit",
                severity=audit.severity,
                payload=audit.as_dict(),
            )
        except Exception:
            pass

    def _persist_command_batch(
        self,
        batch: AnalyticsCommandBatch,
    ) -> None:
        if self.persistence_engine is None:
            return

        try:
            self.persistence_engine.save_executive_snapshot(
                snapshot_name="analytics_command_batch",
                payload=batch.as_dict(),
            )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _requires_approval(
        self,
        command_type: str,
        payload: Dict[str, Any],
    ) -> bool:
        if command_type == AnalyticsCommandType.STOP_RUNTIME.value:
            return self.require_approval_for_runtime_stop

        if command_type == AnalyticsCommandType.RUN_EXECUTION.value:
            return self.require_approval_for_real_execution

        if command_type == AnalyticsCommandType.RUN_RECOVERY.value:
            return self.require_approval_for_recovery

        if payload.get("requires_approval") is True:
            return True

        return False

    def _normalize_command_type(
        self,
        command_type: str,
    ) -> str:
        normalized = str(command_type).strip().upper()

        valid = {item.value for item in AnalyticsCommandType}

        if normalized not in valid:
            raise ValueError(f"Unsupported command type: {command_type}")

        return normalized

    def _get_command_or_raise(
        self,
        command_id: str,
    ) -> AnalyticsCommand:
        command = self.commands.get(command_id)

        if command is None:
            raise KeyError(f"Command not found: {command_id}")

        return command

    def _audit(
        self,
        command_id: Optional[str],
        event_type: str,
        message: str,
        *,
        severity: str = AnalyticsCommandSeverity.INFO.value,
        payload: Optional[Dict[str, Any]] = None,
    ) -> AnalyticsCommandAudit:
        audit = AnalyticsCommandAudit(
            audit_id=f"cmdaudit_{uuid.uuid4().hex}",
            command_id=command_id,
            event_type=event_type,
            message=message,
            severity=severity,
            payload=payload or {},
        )

        self.audit_log.append(audit)

        if len(self.audit_log) > 10000:
            self.audit_log = self.audit_log[-10000:]

        self._persist_audit(audit)
        return audit

    def _call_target(
        self,
        target: Any,
        method_name: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        if target is None:
            raise RuntimeError(f"No target available for method: {method_name}")

        method = getattr(target, method_name, None)

        if method is None:
            raise AttributeError(f"Target does not support method: {method_name}")

        result = method(**kwargs)
        return self._as_dict(result)

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

    @staticmethod
    def _safe_status(
        target: Any,
        method_name: str,
    ) -> Dict[str, Any]:
        if target is None:
            return {"status": "NOT_AVAILABLE"}

        try:
            method = getattr(target, method_name)
            result = method()
            if hasattr(result, "as_dict"):
                return result.as_dict()
            if hasattr(result, "__dataclass_fields__"):
                return asdict(result)
            if isinstance(result, dict):
                return result
            return {"value": str(result)}
        except Exception as exc:
            return {"status": "ERROR", "error": str(exc)}

    @staticmethod
    def _safe_export(
        target: Any,
    ) -> Dict[str, Any]:
        if target is None:
            return {"status": "NOT_AVAILABLE"}

        try:
            if hasattr(target, "export_state"):
                return target.export_state()
            if hasattr(target, "runtime_status"):
                return target.runtime_status()
            return {"status": "AVAILABLE"}
        except Exception as exc:
            return {"status": "ERROR", "error": str(exc)}

    def to_json(self) -> str:
        return json.dumps(
            self.export_state(),
            indent=2,
            default=str,
        )


def create_analytics_fabric_command_processor(
    *,
    continuous_runtime_engine: Optional[Any] = None,
    supervisor: Optional[Any] = None,
    runtime_controller: Optional[Any] = None,
    orchestrator: Optional[Any] = None,
    persistence_engine: Optional[Any] = None,
    require_approval_for_runtime_stop: bool = True,
    require_approval_for_real_execution: bool = True,
    require_approval_for_recovery: bool = False,
) -> AnalyticsFabricCommandProcessor:
    return AnalyticsFabricCommandProcessor(
        continuous_runtime_engine=continuous_runtime_engine,
        supervisor=supervisor,
        runtime_controller=runtime_controller,
        orchestrator=orchestrator,
        persistence_engine=persistence_engine,
        require_approval_for_runtime_stop=require_approval_for_runtime_stop,
        require_approval_for_real_execution=require_approval_for_real_execution,
        require_approval_for_recovery=require_approval_for_recovery,
    )