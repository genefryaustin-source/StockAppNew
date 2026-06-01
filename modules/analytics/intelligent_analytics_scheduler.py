"""
modules/analytics/intelligent_analytics_scheduler.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Iterable
import uuid

from modules.analytics.universe_job_registry import (
    UniverseJobRegistry,
    UniverseJobPriority,
    UniverseJobType,
)


# =============================================================================
# Helpers
# =============================================================================

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


# =============================================================================
# Enums
# =============================================================================

class ScheduleType(str, Enum):
    ONCE = "ONCE"
    HOURLY = "HOURLY"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MARKET_OPEN = "MARKET_OPEN"
    MARKET_CLOSE = "MARKET_CLOSE"
    CONTINUOUS = "CONTINUOUS"
    EVENT_DRIVEN = "EVENT_DRIVEN"


class ScheduleState(str, Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    DISABLED = "DISABLED"


class AnalyticsTrigger(str, Enum):
    UNIVERSE_REFRESH = "UNIVERSE_REFRESH"
    SIGNAL_REFRESH = "SIGNAL_REFRESH"
    FUNDAMENTAL_REFRESH = "FUNDAMENTAL_REFRESH"
    TECHNICAL_REFRESH = "TECHNICAL_REFRESH"
    RANKING_REFRESH = "RANKING_REFRESH"
    RISK_REFRESH = "RISK_REFRESH"
    PORTFOLIO_REFRESH = "PORTFOLIO_REFRESH"
    BACKTEST_REFRESH = "BACKTEST_REFRESH"
    MANUAL = "MANUAL"


# =============================================================================
# Dataclasses
# =============================================================================

@dataclass(frozen=True)
class AnalyticsSchedule:
    schedule_id: str
    tenant_id: str
    universe_id: str
    schedule_name: str
    job_type: str
    schedule_type: str
    priority: str
    enabled: bool = True
    interval_minutes: int = 60
    next_run_at: Optional[str] = None
    last_run_at: Optional[str] = None
    market_hours_only: bool = False
    provider_affinity: Optional[str] = None
    max_concurrent_jobs: int = 1
    payload: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SchedulingDecision:
    decision_id: str
    schedule_id: str
    tenant_id: str
    universe_id: str
    action: str
    reason: str
    generated_at: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SchedulerMetrics:
    active_schedules: int
    due_schedules: int
    jobs_created: int
    skipped_schedules: int
    generated_at: str


# =============================================================================
# Scheduler
# =============================================================================

class IntelligentAnalyticsScheduler:
    """
    Autonomous scheduling layer for analytics workloads.

    Responsibilities:
        - Determine which analytics need execution.
        - Refresh universes automatically.
        - Generate jobs into the registry.
        - Respect tenant quotas.
        - Support future market-aware execution.
        - Support future resource governance integration.

    Does NOT:
        - Execute jobs.
        - Lease jobs.
        - Manage workers.
        - Balance workloads.

    Those are handled by:
        UniverseExecutionQueue
        UniverseRuntimeController
        UniverseWorkloadBalancer
    """

    def __init__(
        self,
        registry: UniverseJobRegistry,
        tenant_job_limit: int = 5000,
    ):
        self.registry = registry
        self.tenant_job_limit = tenant_job_limit

        self._schedules: Dict[str, AnalyticsSchedule] = {}

    # =========================================================================
    # Schedule Management
    # =========================================================================

    def register_schedule(
        self,
        tenant_id: str,
        universe_id: str,
        schedule_name: str,
        job_type: str,
        schedule_type: str = ScheduleType.HOURLY.value,
        priority: str = UniverseJobPriority.NORMAL.value,
        interval_minutes: int = 60,
        market_hours_only: bool = False,
        provider_affinity: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AnalyticsSchedule:

        schedule = AnalyticsSchedule(
            schedule_id=f"sched_{uuid.uuid4().hex}",
            tenant_id=tenant_id,
            universe_id=universe_id,
            schedule_name=schedule_name,
            job_type=job_type,
            schedule_type=schedule_type,
            priority=priority,
            interval_minutes=max(1, interval_minutes),
            market_hours_only=market_hours_only,
            provider_affinity=provider_affinity,
            payload=payload or {},
            metadata=metadata or {},
            next_run_at=utc_now_iso(),
        )

        self._schedules[schedule.schedule_id] = schedule

        return schedule

    def remove_schedule(self, schedule_id: str) -> bool:
        return self._schedules.pop(schedule_id, None) is not None

    def get_schedule(
        self,
        schedule_id: str,
    ) -> Optional[AnalyticsSchedule]:
        return self._schedules.get(schedule_id)

    def list_schedules(
        self,
        tenant_id: Optional[str] = None,
        universe_id: Optional[str] = None,
    ) -> List[AnalyticsSchedule]:

        schedules = list(self._schedules.values())

        if tenant_id:
            schedules = [
                s for s in schedules
                if s.tenant_id == tenant_id
            ]

        if universe_id:
            schedules = [
                s for s in schedules
                if s.universe_id == universe_id
            ]

        return schedules

    # =========================================================================
    # Main Scheduling Engine
    # =========================================================================

    def run_scheduler_cycle(
        self,
    ) -> Dict[str, Any]:

        now = utc_now()

        jobs_created = 0
        skipped = 0
        decisions: List[SchedulingDecision] = []

        due_schedules = self._get_due_schedules(now)

        for schedule in due_schedules:

            allowed, reason = self._validate_schedule(schedule)

            if not allowed:

                skipped += 1

                decisions.append(
                    SchedulingDecision(
                        decision_id=f"dec_{uuid.uuid4().hex}",
                        schedule_id=schedule.schedule_id,
                        tenant_id=schedule.tenant_id,
                        universe_id=schedule.universe_id,
                        action="SKIPPED",
                        reason=reason,
                        generated_at=utc_now_iso(),
                    )
                )

                continue

            self._create_job_from_schedule(schedule)

            jobs_created += 1

            decisions.append(
                SchedulingDecision(
                    decision_id=f"dec_{uuid.uuid4().hex}",
                    schedule_id=schedule.schedule_id,
                    tenant_id=schedule.tenant_id,
                    universe_id=schedule.universe_id,
                    action="JOB_CREATED",
                    reason="Schedule due for execution.",
                    generated_at=utc_now_iso(),
                )
            )

            self._advance_schedule(schedule)

        return {
            "jobs_created": jobs_created,
            "skipped": skipped,
            "due_schedules": len(due_schedules),
            "decisions": decisions,
            "generated_at": utc_now_iso(),
        }

    # =========================================================================
    # Due Schedule Detection
    # =========================================================================

    def _get_due_schedules(
        self,
        now: datetime,
    ) -> List[AnalyticsSchedule]:

        due = []

        for schedule in self._schedules.values():

            if not schedule.enabled:
                continue

            if not schedule.next_run_at:
                continue

            try:
                next_run = datetime.fromisoformat(
                    schedule.next_run_at
                )
            except Exception:
                continue

            if next_run <= now:
                due.append(schedule)

        return due

    # =========================================================================
    # Validation
    # =========================================================================

    def _validate_schedule(
        self,
        schedule: AnalyticsSchedule,
    ) -> tuple[bool, str]:

        if schedule.market_hours_only:
            if not self._is_market_hours():
                return False, "Outside market hours."

        active_jobs = self.registry.list_jobs(
            tenant_id=schedule.tenant_id,
            universe_id=schedule.universe_id,
            limit=self.tenant_job_limit,
        )

        if len(active_jobs) >= self.tenant_job_limit:
            return False, "Tenant job quota exceeded."

        return True, "Approved"

    # =========================================================================
    # Job Generation
    # =========================================================================

    def _create_job_from_schedule(
        self,
        schedule: AnalyticsSchedule,
    ) -> None:

        payload = {
            **schedule.payload,
            "schedule_id": schedule.schedule_id,
            "schedule_name": schedule.schedule_name,
            "generated_by_scheduler": True,
            "scheduled_at": utc_now_iso(),
        }

        self.registry.register_job(
            tenant_id=schedule.tenant_id,
            universe_id=schedule.universe_id,
            job_type=schedule.job_type,
            priority=schedule.priority,
            provider=schedule.provider_affinity,
            payload=payload,
            correlation_id=schedule.schedule_id,
            tags=[
                "scheduler",
                schedule.schedule_type.lower(),
            ],
        )

    # =========================================================================
    # Schedule Advancement
    # =========================================================================

    def _advance_schedule(
        self,
        schedule: AnalyticsSchedule,
    ) -> None:

        now = utc_now()

        next_run = now + timedelta(
            minutes=schedule.interval_minutes
        )

        updated = AnalyticsSchedule(
            schedule_id=schedule.schedule_id,
            tenant_id=schedule.tenant_id,
            universe_id=schedule.universe_id,
            schedule_name=schedule.schedule_name,
            job_type=schedule.job_type,
            schedule_type=schedule.schedule_type,
            priority=schedule.priority,
            enabled=schedule.enabled,
            interval_minutes=schedule.interval_minutes,
            next_run_at=next_run.isoformat(),
            last_run_at=now.isoformat(),
            market_hours_only=schedule.market_hours_only,
            provider_affinity=schedule.provider_affinity,
            max_concurrent_jobs=schedule.max_concurrent_jobs,
            payload=schedule.payload,
            metadata=schedule.metadata,
        )

        self._schedules[schedule.schedule_id] = updated

    # =========================================================================
    # Metrics
    # =========================================================================

    def scheduler_metrics(self) -> SchedulerMetrics:

        now = utc_now()

        due = len(
            self._get_due_schedules(now)
        )

        active = len(
            [
                s for s in self._schedules.values()
                if s.enabled
            ]
        )

        return SchedulerMetrics(
            active_schedules=active,
            due_schedules=due,
            jobs_created=0,
            skipped_schedules=0,
            generated_at=utc_now_iso(),
        )

    # =========================================================================
    # Intelligent Refresh Builders
    # =========================================================================

    def create_universe_refresh_schedule(
        self,
        tenant_id: str,
        universe_id: str,
        interval_minutes: int = 60,
    ) -> AnalyticsSchedule:

        return self.register_schedule(
            tenant_id=tenant_id,
            universe_id=universe_id,
            schedule_name="Universe Refresh",
            job_type=UniverseJobType.UNIVERSE_REFRESH.value,
            schedule_type=ScheduleType.HOURLY.value,
            priority=UniverseJobPriority.NORMAL.value,
            interval_minutes=interval_minutes,
        )

    def create_signal_refresh_schedule(
        self,
        tenant_id: str,
        universe_id: str,
        interval_minutes: int = 15,
    ) -> AnalyticsSchedule:

        return self.register_schedule(
            tenant_id=tenant_id,
            universe_id=universe_id,
            schedule_name="Signal Refresh",
            job_type=UniverseJobType.SIGNAL_GENERATION.value,
            schedule_type=ScheduleType.CONTINUOUS.value,
            priority=UniverseJobPriority.HIGH.value,
            interval_minutes=interval_minutes,
            market_hours_only=True,
        )

    def create_ranking_refresh_schedule(
        self,
        tenant_id: str,
        universe_id: str,
        interval_minutes: int = 30,
    ) -> AnalyticsSchedule:

        return self.register_schedule(
            tenant_id=tenant_id,
            universe_id=universe_id,
            schedule_name="Ranking Refresh",
            job_type=UniverseJobType.RANKING.value,
            schedule_type=ScheduleType.CONTINUOUS.value,
            priority=UniverseJobPriority.HIGH.value,
            interval_minutes=interval_minutes,
            market_hours_only=True,
        )

    # =========================================================================
    # Market Calendar Hooks
    # =========================================================================

    def _is_market_hours(self) -> bool:
        """
        Placeholder.

        Future:
            Polygon calendar
            NYSE holidays
            NASDAQ holidays
            Extended hours support
            Futures schedules
            Crypto 24x7 schedules
        """
        return True

    # =========================================================================
    # Forecasting
    # =========================================================================

    def estimate_next_cycle_workload(self) -> Dict[str, Any]:

        now = utc_now()

        due = self._get_due_schedules(now)

        by_job_type: Dict[str, int] = {}

        for schedule in due:
            by_job_type[schedule.job_type] = (
                by_job_type.get(schedule.job_type, 0)
                + 1
            )

        return {
            "due_jobs": len(due),
            "job_type_breakdown": by_job_type,
            "generated_at": utc_now_iso(),
        }