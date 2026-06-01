"""
modules/analytics/analytics_fabric_continuous_runtime_engine.py
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ContinuousRuntimeState(str, Enum):
    INITIALIZED = "INITIALIZED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"


class ContinuousRuntimeEventType(str, Enum):
    ENGINE_STARTED = "ENGINE_STARTED"
    ENGINE_STOPPED = "ENGINE_STOPPED"
    ENGINE_PAUSED = "ENGINE_PAUSED"
    ENGINE_RESUMED = "ENGINE_RESUMED"
    LOOP_TICK = "LOOP_TICK"
    SUPERVISOR_CYCLE = "SUPERVISOR_CYCLE"
    HEALTH_CHECK = "HEALTH_CHECK"
    RECOVERY_CYCLE = "RECOVERY_CYCLE"
    SNAPSHOT_CYCLE = "SNAPSHOT_CYCLE"
    GOVERNANCE_ENFORCEMENT = "GOVERNANCE_ENFORCEMENT"
    HEARTBEAT = "HEARTBEAT"
    ERROR = "ERROR"


@dataclass
class ContinuousRuntimeConfig:
    loop_interval_seconds: float = 5.0
    heartbeat_interval_seconds: float = 30.0
    health_check_interval_seconds: float = 60.0
    recovery_interval_seconds: float = 120.0
    snapshot_interval_seconds: float = 300.0
    governance_interval_seconds: float = 120.0

    run_supervisor_each_tick: bool = True
    run_health_each_tick: bool = False
    run_recovery_on_degraded: bool = True
    run_snapshot_on_start: bool = True
    enable_threaded_loop: bool = False

    max_consecutive_errors: int = 5
    auto_pause_on_error_threshold: bool = True
    auto_recover_on_error: bool = True

    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RuntimeHeartbeat:
    heartbeat_id: str
    state: str
    loop_count: int
    uptime_seconds: float
    generated_at: str = field(default_factory=utc_now_iso)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ContinuousRuntimeEvent:
    event_id: str
    event_type: str
    severity: str
    message: str
    payload: Dict[str, Any] = field(default_factory=dict)
    generated_at: str = field(default_factory=utc_now_iso)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ContinuousRuntimeTickResult:
    tick_id: str
    status: str
    loop_count: int
    started_at: str
    completed_at: str
    runtime_ms: float
    supervisor_result: Dict[str, Any] = field(default_factory=dict)
    health_result: Dict[str, Any] = field(default_factory=dict)
    recovery_result: Dict[str, Any] = field(default_factory=dict)
    snapshot_result: Dict[str, Any] = field(default_factory=dict)
    governance_result: Dict[str, Any] = field(default_factory=dict)
    heartbeat: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ContinuousRuntimeMetrics:
    loops_started: int = 0
    loops_completed: int = 0
    loops_failed: int = 0
    supervisor_cycles: int = 0
    health_checks: int = 0
    recovery_cycles: int = 0
    snapshot_cycles: int = 0
    governance_cycles: int = 0
    heartbeats: int = 0
    consecutive_errors: int = 0
    total_runtime_ms: float = 0.0
    started_at: Optional[str] = None
    stopped_at: Optional[str] = None
    last_tick_at: Optional[str] = None
    last_heartbeat_at: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        avg_runtime_ms = (
            self.total_runtime_ms / self.loops_completed
            if self.loops_completed
            else 0.0
        )

        return {
            "loops_started": self.loops_started,
            "loops_completed": self.loops_completed,
            "loops_failed": self.loops_failed,
            "supervisor_cycles": self.supervisor_cycles,
            "health_checks": self.health_checks,
            "recovery_cycles": self.recovery_cycles,
            "snapshot_cycles": self.snapshot_cycles,
            "governance_cycles": self.governance_cycles,
            "heartbeats": self.heartbeats,
            "consecutive_errors": self.consecutive_errors,
            "average_tick_runtime_ms": round(avg_runtime_ms, 4),
            "total_runtime_ms": round(self.total_runtime_ms, 4),
            "started_at": self.started_at,
            "stopped_at": self.stopped_at,
            "last_tick_at": self.last_tick_at,
            "last_heartbeat_at": self.last_heartbeat_at,
            "generated_at": utc_now_iso(),
        }


class AnalyticsFabricContinuousRuntimeEngine:
    """
    Always-on Analytics Fabric runtime loop.

    This engine is deterministic and can run either:
      - manually via run_once()
      - synchronously via run_for_iterations()
      - optionally in a managed background thread via start_background_loop()

    In Streamlit, prefer manual or short synchronous execution.
    In a worker/service process, threaded mode can be enabled.
    """

    def __init__(
        self,
        *,
        supervisor: Optional[Any] = None,
        runtime_controller: Optional[Any] = None,
        snapshot_scheduler: Optional[Any] = None,
        persistence_engine: Optional[Any] = None,
        config: Optional[ContinuousRuntimeConfig] = None,
    ) -> None:
        self.supervisor = supervisor
        self.runtime_controller = runtime_controller
        self.snapshot_scheduler = snapshot_scheduler
        self.persistence_engine = persistence_engine
        self.config = config or ContinuousRuntimeConfig()

        self.state = ContinuousRuntimeState.INITIALIZED.value
        self.metrics = ContinuousRuntimeMetrics()
        self.events: List[ContinuousRuntimeEvent] = []
        self.tick_history: List[ContinuousRuntimeTickResult] = []
        self.heartbeat_history: List[RuntimeHeartbeat] = []

        self._started_monotonic: Optional[float] = None
        self._last_heartbeat_monotonic: float = 0.0
        self._last_health_monotonic: float = 0.0
        self._last_recovery_monotonic: float = 0.0
        self._last_snapshot_monotonic: float = 0.0
        self._last_governance_monotonic: float = 0.0

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start_runtime(self) -> Dict[str, Any]:
        self.state = ContinuousRuntimeState.STARTING.value
        self.metrics.started_at = self.metrics.started_at or utc_now_iso()
        self._started_monotonic = self._started_monotonic or time.monotonic()
        self._stop_event.clear()

        if self.supervisor is not None:
            try:
                self.supervisor.start_supervisor()
            except Exception as exc:
                self._record_event(
                    ContinuousRuntimeEventType.ERROR.value,
                    "ERROR",
                    "Supervisor failed to start.",
                    {"error": str(exc)},
                )

        self.state = ContinuousRuntimeState.RUNNING.value

        self._record_event(
            ContinuousRuntimeEventType.ENGINE_STARTED.value,
            "INFO",
            "Continuous runtime engine started.",
        )

        if self.config.run_snapshot_on_start:
            try:
                self.run_snapshot_cycle()
            except Exception as exc:
                self._record_event(
                    ContinuousRuntimeEventType.ERROR.value,
                    "ERROR",
                    "Startup snapshot failed.",
                    {"error": str(exc)},
                )

        if self.config.enable_threaded_loop:
            self.start_background_loop()

        return self.runtime_status()

    def stop_runtime(self) -> Dict[str, Any]:
        self.state = ContinuousRuntimeState.STOPPING.value
        self._stop_event.set()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=max(1.0, self.config.loop_interval_seconds * 2))

        if self.supervisor is not None:
            try:
                self.supervisor.stop_supervisor()
            except Exception:
                pass

        self.state = ContinuousRuntimeState.STOPPED.value
        self.metrics.stopped_at = utc_now_iso()

        self._record_event(
            ContinuousRuntimeEventType.ENGINE_STOPPED.value,
            "INFO",
            "Continuous runtime engine stopped.",
        )

        return self.runtime_status()

    def pause_runtime(self) -> Dict[str, Any]:
        self.state = ContinuousRuntimeState.PAUSED.value

        if self.supervisor is not None:
            try:
                self.supervisor.pause_supervisor()
            except Exception:
                pass

        self._record_event(
            ContinuousRuntimeEventType.ENGINE_PAUSED.value,
            "INFO",
            "Continuous runtime engine paused.",
        )

        return self.runtime_status()

    def resume_runtime(self) -> Dict[str, Any]:
        self.state = ContinuousRuntimeState.RUNNING.value

        if self.supervisor is not None:
            try:
                self.supervisor.resume_supervisor()
            except Exception:
                pass

        self._record_event(
            ContinuousRuntimeEventType.ENGINE_RESUMED.value,
            "INFO",
            "Continuous runtime engine resumed.",
        )

        return self.runtime_status()

    def start_background_loop(self) -> Dict[str, Any]:
        if self._thread and self._thread.is_alive():
            return {
                "status": "ALREADY_RUNNING",
                "state": self.state,
                "generated_at": utc_now_iso(),
            }

        self._stop_event.clear()

        self._thread = threading.Thread(
            target=self._background_loop,
            name="analytics-fabric-continuous-runtime",
            daemon=True,
        )
        self._thread.start()

        return {
            "status": "STARTED",
            "threaded": True,
            "generated_at": utc_now_iso(),
        }

    def _background_loop(self) -> None:
        while not self._stop_event.is_set():
            if self.state == ContinuousRuntimeState.RUNNING.value:
                self.run_once()

            time.sleep(max(0.1, self.config.loop_interval_seconds))

    # ------------------------------------------------------------------
    # Runtime Loop
    # ------------------------------------------------------------------

    def run_once(self, *, force: bool = False) -> ContinuousRuntimeTickResult:
        started = time.perf_counter()
        started_at = utc_now_iso()

        if self.state == ContinuousRuntimeState.INITIALIZED.value:
            self.start_runtime()

        if self.state in {
            ContinuousRuntimeState.STOPPED.value,
            ContinuousRuntimeState.STOPPING.value,
        }:
            return ContinuousRuntimeTickResult(
                tick_id=f"tick_{uuid.uuid4().hex}",
                status="SKIPPED",
                loop_count=self.metrics.loops_started,
                started_at=started_at,
                completed_at=utc_now_iso(),
                runtime_ms=0.0,
                error=f"Runtime state is {self.state}.",
            )

        if self.state == ContinuousRuntimeState.PAUSED.value:
            return ContinuousRuntimeTickResult(
                tick_id=f"tick_{uuid.uuid4().hex}",
                status="PAUSED",
                loop_count=self.metrics.loops_started,
                started_at=started_at,
                completed_at=utc_now_iso(),
                runtime_ms=0.0,
            )

        self.metrics.loops_started += 1
        loop_count = self.metrics.loops_started

        supervisor_result: Dict[str, Any] = {}
        health_result: Dict[str, Any] = {}
        recovery_result: Dict[str, Any] = {}
        snapshot_result: Dict[str, Any] = {}
        governance_result: Dict[str, Any] = {}
        heartbeat_payload: Optional[Dict[str, Any]] = None

        try:
            self._record_event(
                ContinuousRuntimeEventType.LOOP_TICK.value,
                "INFO",
                "Continuous runtime loop tick started.",
                {"loop_count": loop_count},
            )

            if self.config.run_supervisor_each_tick or force:
                supervisor_result = self.run_supervisor_cycle(force=force)
                self.metrics.supervisor_cycles += 1

            if self.config.run_health_each_tick or force or self._interval_due(
                self._last_health_monotonic,
                self.config.health_check_interval_seconds,
            ):
                health_result = self.run_health_check()
                self._last_health_monotonic = time.monotonic()
                self.metrics.health_checks += 1

            if force or self._interval_due(
                self._last_governance_monotonic,
                self.config.governance_interval_seconds,
            ):
                governance_result = self.run_governance_cycle()
                self._last_governance_monotonic = time.monotonic()
                self.metrics.governance_cycles += 1

            if force or self._interval_due(
                self._last_recovery_monotonic,
                self.config.recovery_interval_seconds,
            ):
                if self.state == ContinuousRuntimeState.DEGRADED.value or self.config.run_recovery_on_degraded:
                    recovery_result = self.run_recovery_cycle()
                    self._last_recovery_monotonic = time.monotonic()
                    self.metrics.recovery_cycles += 1

            if force or self._interval_due(
                self._last_snapshot_monotonic,
                self.config.snapshot_interval_seconds,
            ):
                snapshot_result = self.run_snapshot_cycle()
                self._last_snapshot_monotonic = time.monotonic()
                self.metrics.snapshot_cycles += 1

            if force or self._interval_due(
                self._last_heartbeat_monotonic,
                self.config.heartbeat_interval_seconds,
            ):
                heartbeat = self.emit_heartbeat()
                heartbeat_payload = heartbeat.as_dict()
                self._last_heartbeat_monotonic = time.monotonic()
                self.metrics.heartbeats += 1

            runtime_ms = round((time.perf_counter() - started) * 1000.0, 4)
            self.metrics.loops_completed += 1
            self.metrics.consecutive_errors = 0
            self.metrics.total_runtime_ms += runtime_ms
            self.metrics.last_tick_at = utc_now_iso()

            result = ContinuousRuntimeTickResult(
                tick_id=f"tick_{uuid.uuid4().hex}",
                status="SUCCESS",
                loop_count=loop_count,
                started_at=started_at,
                completed_at=utc_now_iso(),
                runtime_ms=runtime_ms,
                supervisor_result=supervisor_result,
                health_result=health_result,
                recovery_result=recovery_result,
                snapshot_result=snapshot_result,
                governance_result=governance_result,
                heartbeat=heartbeat_payload,
            )

            self.tick_history.append(result)
            self._trim_history()
            return result

        except Exception as exc:
            runtime_ms = round((time.perf_counter() - started) * 1000.0, 4)
            self.metrics.loops_failed += 1
            self.metrics.consecutive_errors += 1
            self.metrics.total_runtime_ms += runtime_ms
            self.metrics.last_tick_at = utc_now_iso()

            self._record_event(
                ContinuousRuntimeEventType.ERROR.value,
                "ERROR",
                "Continuous runtime loop failed.",
                {
                    "error": str(exc),
                    "consecutive_errors": self.metrics.consecutive_errors,
                },
            )

            if (
                self.config.auto_pause_on_error_threshold
                and self.metrics.consecutive_errors >= self.config.max_consecutive_errors
            ):
                self.state = ContinuousRuntimeState.DEGRADED.value

                if self.config.auto_recover_on_error:
                    try:
                        self.run_recovery_cycle()
                    except Exception:
                        pass

            result = ContinuousRuntimeTickResult(
                tick_id=f"tick_{uuid.uuid4().hex}",
                status="FAILED",
                loop_count=loop_count,
                started_at=started_at,
                completed_at=utc_now_iso(),
                runtime_ms=runtime_ms,
                supervisor_result=supervisor_result,
                health_result=health_result,
                recovery_result=recovery_result,
                snapshot_result=snapshot_result,
                governance_result=governance_result,
                heartbeat=heartbeat_payload,
                error=str(exc),
            )

            self.tick_history.append(result)
            self._trim_history()
            return result

    def run_for_iterations(
        self,
        iterations: int,
        *,
        sleep_between_iterations: bool = False,
        force: bool = False,
    ) -> List[Dict[str, Any]]:
        results = []

        for _ in range(max(0, int(iterations))):
            result = self.run_once(force=force)
            results.append(result.as_dict())

            if sleep_between_iterations:
                time.sleep(max(0.0, self.config.loop_interval_seconds))

        return results

    # ------------------------------------------------------------------
    # Cycle Wrappers
    # ------------------------------------------------------------------

    def run_supervisor_cycle(self, *, force: bool = False) -> Dict[str, Any]:
        self._record_event(
            ContinuousRuntimeEventType.SUPERVISOR_CYCLE.value,
            "INFO",
            "Supervisor cycle requested.",
        )

        if self.supervisor is None:
            return {"status": "NO_SUPERVISOR", "generated_at": utc_now_iso()}

        return self.supervisor.run_supervisor_cycle(force=force)

    def run_health_check(self) -> Dict[str, Any]:
        self._record_event(
            ContinuousRuntimeEventType.HEALTH_CHECK.value,
            "INFO",
            "Health check requested.",
        )

        health = {}

        if self.supervisor is not None:
            health["supervisor"] = self.supervisor.supervisor_health()

        if self.runtime_controller is not None:
            health["runtime"] = self.runtime_controller.runtime_health()

        supervisor_score = (
            health.get("supervisor", {}).get("supervisor_health_score", 100.0)
            if isinstance(health.get("supervisor"), dict)
            else 100.0
        )

        runtime_score = (
            health.get("runtime", {}).get("health_score", 100.0)
            if isinstance(health.get("runtime"), dict)
            else 100.0
        )

        if supervisor_score < 70 or runtime_score < 70:
            self.state = ContinuousRuntimeState.DEGRADED.value
        elif self.state == ContinuousRuntimeState.DEGRADED.value:
            self.state = ContinuousRuntimeState.RUNNING.value

        return {
            "status": "COMPLETED",
            "state": self.state,
            "health": health,
            "generated_at": utc_now_iso(),
        }

    def run_recovery_cycle(self) -> Dict[str, Any]:
        self._record_event(
            ContinuousRuntimeEventType.RECOVERY_CYCLE.value,
            "WARN",
            "Recovery cycle requested.",
        )

        if self.supervisor is not None:
            return self.supervisor.run_recovery_cycle()

        if self.runtime_controller is not None:
            return {
                "status": "RUNTIME_RECOVERY",
                "result": self.runtime_controller.run_recovery_cycle(),
                "generated_at": utc_now_iso(),
            }

        return {"status": "NO_RECOVERY_TARGET", "generated_at": utc_now_iso()}

    def run_snapshot_cycle(self) -> Dict[str, Any]:
        self._record_event(
            ContinuousRuntimeEventType.SNAPSHOT_CYCLE.value,
            "INFO",
            "Snapshot cycle requested.",
        )

        results: Dict[str, Any] = {}

        if self.supervisor is not None:
            try:
                results["supervisor_snapshot"] = self.supervisor.supervisor_snapshot().as_dict()
            except Exception as exc:
                results["supervisor_snapshot_error"] = str(exc)

        if self.runtime_controller is not None:
            try:
                results["runtime_snapshot"] = self.runtime_controller.runtime_snapshot().as_dict()
            except Exception as exc:
                results["runtime_snapshot_error"] = str(exc)

        if self.snapshot_scheduler is not None:
            try:
                results["snapshot_scheduler"] = self.snapshot_scheduler.run_snapshot_cycle()
            except Exception as exc:
                results["snapshot_scheduler_error"] = str(exc)

        return {
            "status": "COMPLETED",
            "results": results,
            "generated_at": utc_now_iso(),
        }

    def run_governance_cycle(self) -> Dict[str, Any]:
        self._record_event(
            ContinuousRuntimeEventType.GOVERNANCE_ENFORCEMENT.value,
            "INFO",
            "Governance enforcement requested.",
        )

        if self.supervisor is not None:
            return self.supervisor.enforce_governance()

        return {
            "status": "NO_SUPERVISOR",
            "generated_at": utc_now_iso(),
        }

    # ------------------------------------------------------------------
    # Heartbeats / Status / Export
    # ------------------------------------------------------------------

    def emit_heartbeat(self) -> RuntimeHeartbeat:
        uptime = 0.0

        if self._started_monotonic is not None:
            uptime = round(time.monotonic() - self._started_monotonic, 2)

        heartbeat = RuntimeHeartbeat(
            heartbeat_id=f"heartbeat_{uuid.uuid4().hex}",
            state=self.state,
            loop_count=self.metrics.loops_started,
            uptime_seconds=uptime,
        )

        self.heartbeat_history.append(heartbeat)
        self.metrics.last_heartbeat_at = heartbeat.generated_at

        self._record_event(
            ContinuousRuntimeEventType.HEARTBEAT.value,
            "INFO",
            "Runtime heartbeat emitted.",
            heartbeat.as_dict(),
        )

        self._persist_heartbeat(heartbeat)
        self._trim_history()

        return heartbeat

    def runtime_status(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "thread_alive": bool(self._thread and self._thread.is_alive()),
            "config": asdict(self.config),
            "metrics": self.metrics.as_dict(),
            "supervisor_status": self._safe_supervisor_status(),
            "runtime_controller_status": self._safe_runtime_controller_status(),
            "generated_at": utc_now_iso(),
        }

    def runtime_summary(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "loops_started": self.metrics.loops_started,
            "loops_completed": self.metrics.loops_completed,
            "loops_failed": self.metrics.loops_failed,
            "consecutive_errors": self.metrics.consecutive_errors,
            "heartbeats": self.metrics.heartbeats,
            "events": len(self.events),
            "ticks": len(self.tick_history),
            "generated_at": utc_now_iso(),
        }

    def runtime_metrics(self) -> Dict[str, Any]:
        return self.metrics.as_dict()

    def event_history(self, limit: int = 1000) -> List[Dict[str, Any]]:
        return [event.as_dict() for event in self.events[-limit:]]

    def heartbeat_records(self, limit: int = 1000) -> List[Dict[str, Any]]:
        return [heartbeat.as_dict() for heartbeat in self.heartbeat_history[-limit:]]

    def tick_records(self, limit: int = 1000) -> List[Dict[str, Any]]:
        return [tick.as_dict() for tick in self.tick_history[-limit:]]

    def export_state(self) -> Dict[str, Any]:
        return {
            "status": self.runtime_status(),
            "summary": self.runtime_summary(),
            "metrics": self.runtime_metrics(),
            "events": self.event_history(),
            "heartbeats": self.heartbeat_records(),
            "ticks": self.tick_records(),
            "generated_at": utc_now_iso(),
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _interval_due(self, last_run: float, interval_seconds: float) -> bool:
        if last_run <= 0:
            return True
        return (time.monotonic() - last_run) >= max(0.0, interval_seconds)

    def _record_event(
        self,
        event_type: str,
        severity: str,
        message: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> ContinuousRuntimeEvent:
        event = ContinuousRuntimeEvent(
            event_id=f"event_{uuid.uuid4().hex}",
            event_type=event_type,
            severity=severity,
            message=message,
            payload=payload or {},
        )

        self.events.append(event)

        if len(self.events) > 10000:
            self.events = self.events[-10000:]

        return event

    def _persist_heartbeat(self, heartbeat: RuntimeHeartbeat) -> None:
        if self.persistence_engine is None:
            return

        try:
            self.persistence_engine.save_executive_snapshot(
                snapshot_name="continuous_runtime_heartbeat",
                payload=heartbeat.as_dict(),
            )
        except Exception:
            pass

    def _safe_supervisor_status(self) -> Dict[str, Any]:
        if self.supervisor is None:
            return {"status": "NO_SUPERVISOR"}

        try:
            return self.supervisor.supervisor_status()
        except Exception as exc:
            return {"status": "ERROR", "error": str(exc)}

    def _safe_runtime_controller_status(self) -> Dict[str, Any]:
        if self.runtime_controller is None:
            return {"status": "NO_RUNTIME_CONTROLLER"}

        try:
            return self.runtime_controller.runtime_status()
        except Exception as exc:
            return {"status": "ERROR", "error": str(exc)}

    def _trim_history(self) -> None:
        if len(self.tick_history) > 10000:
            self.tick_history = self.tick_history[-10000:]

        if len(self.heartbeat_history) > 10000:
            self.heartbeat_history = self.heartbeat_history[-10000:]


def create_analytics_fabric_continuous_runtime_engine(
    *,
    supervisor: Optional[Any] = None,
    runtime_controller: Optional[Any] = None,
    snapshot_scheduler: Optional[Any] = None,
    persistence_engine: Optional[Any] = None,
    config: Optional[ContinuousRuntimeConfig] = None,
) -> AnalyticsFabricContinuousRuntimeEngine:
    return AnalyticsFabricContinuousRuntimeEngine(
        supervisor=supervisor,
        runtime_controller=runtime_controller,
        snapshot_scheduler=snapshot_scheduler,
        persistence_engine=persistence_engine,
        config=config,
    )