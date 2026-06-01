"""
modules/analytics/worker_capacity_model.py

Worker Capacity Model

Purpose
-------
Capacity intelligence layer for the Analytics Fabric.

This module analyzes worker throughput, utilization, saturation, failures,
queue pressure, lease pressure, and scaling requirements.

It is intentionally independent from Streamlit/UI code and can be used by:

    - autonomous_analytics_optimizer.py
    - analytics_resource_governor.py
    - universe_runtime_controller.py
    - analytics_operations_center.py
    - analytics_optimizer_dashboard.py

Design Rules
------------
- No global mutable state.
- Explicit input telemetry.
- Deterministic scoring.
- Tenant-aware and worker-aware modeling.
- No direct dependency on Streamlit.
- No background threads.
- No direct provider calls.
"""

from __future__ import annotations

import math
import statistics
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Sequence


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    try:
        if denominator == 0:
            return default
        return float(numerator) / float(denominator)
    except Exception:
        return default


def mean_or_zero(values: Sequence[float]) -> float:
    cleaned = [float(v) for v in values if v is not None]
    return statistics.mean(cleaned) if cleaned else 0.0


def p95_or_zero(values: Sequence[float]) -> float:
    cleaned = sorted(float(v) for v in values if v is not None)
    if not cleaned:
        return 0.0
    idx = min(len(cleaned) - 1, int(len(cleaned) * 0.95))
    return cleaned[idx]


class WorkerCapacityState(str, Enum):
    HEALTHY = "HEALTHY"
    UNDERUTILIZED = "UNDERUTILIZED"
    SATURATED = "SATURATED"
    DEGRADED = "DEGRADED"
    OVERLOADED = "OVERLOADED"
    OFFLINE = "OFFLINE"
    UNKNOWN = "UNKNOWN"


class CapacityRecommendationAction(str, Enum):
    HOLD = "HOLD"
    SCALE_UP = "SCALE_UP"
    SCALE_DOWN = "SCALE_DOWN"
    REBALANCE = "REBALANCE"
    QUARANTINE_WORKER = "QUARANTINE_WORKER"
    DRAIN_WORKER = "DRAIN_WORKER"
    INCREASE_LEASE_SECONDS = "INCREASE_LEASE_SECONDS"
    DECREASE_LEASE_SECONDS = "DECREASE_LEASE_SECONDS"


class CapacitySeverity(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class WorkerTelemetrySample:
    worker_id: str
    tenant_id: Optional[str] = None
    state: str = "ONLINE"
    capacity: int = 1
    active_jobs: int = 0
    completed_jobs: int = 0
    failed_jobs: int = 0
    avg_runtime_seconds: float = 0.0
    p95_runtime_seconds: float = 0.0
    heartbeat_age_seconds: float = 0.0
    queue_depth_seen: int = 0
    active_leases: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    collected_at: str = field(default_factory=utc_now_iso)


@dataclass(frozen=True)
class WorkerCapacityProfile:
    worker_id: str
    tenant_id: Optional[str]
    state: str
    capacity: int
    active_jobs: int
    available_capacity: int
    utilization: float
    completion_rate: float
    failure_rate: float
    throughput_per_minute: float
    avg_runtime_seconds: float
    p95_runtime_seconds: float
    heartbeat_age_seconds: float
    saturation_score: float
    reliability_score: float
    efficiency_score: float
    health_score: float
    generated_at: str = field(default_factory=utc_now_iso)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkerFleetProfile:
    fleet_id: str
    tenant_id: Optional[str]
    workers_total: int
    workers_online: int
    workers_offline: int
    workers_degraded: int
    total_capacity: int
    active_jobs: int
    available_capacity: int
    avg_utilization: float
    p95_utilization: float
    avg_failure_rate: float
    avg_throughput_per_minute: float
    queue_depth: int
    active_leases: int
    saturation_score: float
    reliability_score: float
    health_score: float
    generated_at: str = field(default_factory=utc_now_iso)


@dataclass(frozen=True)
class WorkerCapacityForecast:
    forecast_id: str
    tenant_id: Optional[str]
    current_workers: int
    current_capacity: int
    current_active_jobs: int
    current_queue_depth: int
    projected_required_workers: int
    projected_worker_delta: int
    projected_capacity_needed: int
    projected_minutes_to_clear_queue: float
    confidence: float
    generated_at: str = field(default_factory=utc_now_iso)
    assumptions: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkerScalingRecommendation:
    recommendation_id: str
    action: str
    severity: str
    title: str
    description: str
    tenant_id: Optional[str] = None
    worker_id: Optional[str] = None
    recommended_worker_delta: int = 0
    confidence: float = 0.0
    generated_at: str = field(default_factory=utc_now_iso)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkerCapacityReport:
    report_id: str
    fleet_profile: WorkerFleetProfile
    worker_profiles: List[WorkerCapacityProfile]
    forecast: WorkerCapacityForecast
    recommendations: List[WorkerScalingRecommendation]
    generated_at: str = field(default_factory=utc_now_iso)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "fleet_profile": asdict(self.fleet_profile),
            "worker_profiles": [asdict(p) for p in self.worker_profiles],
            "forecast": asdict(self.forecast),
            "recommendations": [asdict(r) for r in self.recommendations],
            "generated_at": self.generated_at,
        }


class WorkerCapacityModel:
    def __init__(
        self,
        *,
        target_utilization: float = 0.70,
        saturation_threshold: float = 0.85,
        overload_threshold: float = 0.95,
        underutilized_threshold: float = 0.20,
        failure_rate_threshold: float = 0.10,
        stale_heartbeat_seconds: float = 300.0,
        default_worker_capacity: int = 10,
    ) -> None:
        self.target_utilization = clamp(target_utilization)
        self.saturation_threshold = clamp(saturation_threshold)
        self.overload_threshold = clamp(overload_threshold)
        self.underutilized_threshold = clamp(underutilized_threshold)
        self.failure_rate_threshold = clamp(failure_rate_threshold)
        self.stale_heartbeat_seconds = max(1.0, float(stale_heartbeat_seconds))
        self.default_worker_capacity = max(1, int(default_worker_capacity))

        self.sample_history: List[WorkerTelemetrySample] = []
        self.profile_history: List[WorkerCapacityProfile] = []
        self.fleet_history: List[WorkerFleetProfile] = []
        self.forecast_history: List[WorkerCapacityForecast] = []
        self.recommendation_history: List[WorkerScalingRecommendation] = []

    def collect_samples(
        self,
        samples: Iterable[WorkerTelemetrySample],
        *,
        max_history: int = 10000,
    ) -> List[WorkerTelemetrySample]:
        collected = list(samples)
        self.sample_history.extend(collected)
        if len(self.sample_history) > max_history:
            self.sample_history = self.sample_history[-max_history:]
        return collected

    def collect_from_runtime_metrics(
        self,
        *,
        workers: Iterable[Any],
        queue_metrics: Optional[Dict[str, Any]] = None,
        tenant_id: Optional[str] = None,
    ) -> List[WorkerTelemetrySample]:
        queue_metrics = queue_metrics or {}
        samples: List[WorkerTelemetrySample] = []

        for worker in workers:
            is_dict = isinstance(worker, dict)
            worker_id = worker.get("worker_id") if is_dict else getattr(worker, "worker_id", None)
            state = worker.get("state", "ONLINE") if is_dict else getattr(worker, "state", "ONLINE")
            capacity = worker.get("capacity", self.default_worker_capacity) if is_dict else getattr(worker, "capacity", self.default_worker_capacity)
            active_jobs = worker.get("active_jobs", 0) if is_dict else getattr(worker, "active_jobs", 0)
            error_rate = worker.get("error_rate", 0.0) if is_dict else getattr(worker, "error_rate", 0.0)
            avg_runtime = worker.get("avg_runtime_seconds", 0.0) if is_dict else getattr(worker, "avg_runtime_seconds", 0.0)
            w_tenant_id = worker.get("tenant_id", tenant_id) if is_dict else getattr(worker, "tenant_id", tenant_id)
            completed_jobs = worker.get("jobs_completed", 0) if is_dict else getattr(worker, "jobs_completed", 0)
            failed_jobs = worker.get("jobs_failed", 0) if is_dict else getattr(worker, "jobs_failed", 0)

            if not failed_jobs and error_rate:
                completed_jobs = max(1, int(100 * (1.0 - float(error_rate))))
                failed_jobs = max(0, int(100 * float(error_rate)))

            samples.append(
                WorkerTelemetrySample(
                    worker_id=str(worker_id or f"worker_{uuid.uuid4().hex}"),
                    tenant_id=w_tenant_id,
                    state=str(state or "UNKNOWN").upper(),
                    capacity=max(1, int(capacity or self.default_worker_capacity)),
                    active_jobs=max(0, int(active_jobs or 0)),
                    completed_jobs=max(0, int(completed_jobs or 0)),
                    failed_jobs=max(0, int(failed_jobs or 0)),
                    avg_runtime_seconds=max(0.0, float(avg_runtime or 0.0)),
                    p95_runtime_seconds=max(0.0, float(worker.get("p95_runtime_seconds", 0.0) if is_dict else getattr(worker, "p95_runtime_seconds", 0.0))),
                    heartbeat_age_seconds=max(0.0, float(worker.get("heartbeat_age_seconds", 0.0) if is_dict else getattr(worker, "heartbeat_age_seconds", 0.0))),
                    queue_depth_seen=int(queue_metrics.get("queue_depth", 0)),
                    active_leases=int(queue_metrics.get("active_leases", 0)),
                    metadata={"source": "runtime_metrics", "raw_state": str(state)},
                )
            )

        return self.collect_samples(samples)

    def classify_worker_state(
        self,
        sample: WorkerTelemetrySample,
        utilization: float,
        failure_rate: float,
    ) -> str:
        raw_state = str(sample.state or "UNKNOWN").upper()

        if raw_state in {"OFFLINE", "DEAD", "LOST"}:
            return WorkerCapacityState.OFFLINE.value
        if sample.heartbeat_age_seconds >= self.stale_heartbeat_seconds:
            return WorkerCapacityState.OFFLINE.value
        if raw_state in {"DEGRADED", "DRAINING"}:
            return WorkerCapacityState.DEGRADED.value
        if failure_rate >= self.failure_rate_threshold:
            return WorkerCapacityState.DEGRADED.value
        if utilization >= self.overload_threshold:
            return WorkerCapacityState.OVERLOADED.value
        if utilization >= self.saturation_threshold:
            return WorkerCapacityState.SATURATED.value
        if utilization <= self.underutilized_threshold:
            return WorkerCapacityState.UNDERUTILIZED.value
        if raw_state in {"ONLINE", "RUNNING", "ACTIVE"}:
            return WorkerCapacityState.HEALTHY.value
        return WorkerCapacityState.UNKNOWN.value

    def build_worker_profile(self, sample: WorkerTelemetrySample) -> WorkerCapacityProfile:
        capacity = max(1, int(sample.capacity))
        active_jobs = max(0, int(sample.active_jobs))
        available_capacity = max(0, capacity - active_jobs)
        utilization = clamp(safe_divide(active_jobs, capacity))

        total_finished = sample.completed_jobs + sample.failed_jobs
        completion_rate = clamp(safe_divide(sample.completed_jobs, total_finished, 1.0))
        failure_rate = clamp(safe_divide(sample.failed_jobs, total_finished, 0.0))

        avg_runtime = max(0.0, sample.avg_runtime_seconds)
        throughput_per_minute = safe_divide(capacity * 60.0, avg_runtime, float(capacity)) if avg_runtime > 0 else float(capacity)

        stale_penalty = 0.35 if sample.heartbeat_age_seconds >= self.stale_heartbeat_seconds else 0.0
        state = self.classify_worker_state(sample, utilization, failure_rate)

        saturation_score = clamp(utilization)
        reliability_score = clamp(1.0 - failure_rate - stale_penalty)
        efficiency_score = clamp((1.0 - abs(utilization - self.target_utilization)) * 0.70 + reliability_score * 0.30)
        health_score = clamp((reliability_score * 0.45) + ((1.0 - saturation_score) * 0.25) + (efficiency_score * 0.30))

        if state == WorkerCapacityState.OFFLINE.value:
            health_score = min(health_score, 0.05)
        elif state == WorkerCapacityState.DEGRADED.value:
            health_score = min(health_score, 0.55)
        elif state == WorkerCapacityState.OVERLOADED.value:
            health_score = min(health_score, 0.45)

        return WorkerCapacityProfile(
            worker_id=sample.worker_id,
            tenant_id=sample.tenant_id,
            state=state,
            capacity=capacity,
            active_jobs=active_jobs,
            available_capacity=available_capacity,
            utilization=round(utilization, 4),
            completion_rate=round(completion_rate, 4),
            failure_rate=round(failure_rate, 4),
            throughput_per_minute=round(throughput_per_minute, 4),
            avg_runtime_seconds=round(avg_runtime, 4),
            p95_runtime_seconds=round(sample.p95_runtime_seconds, 4),
            heartbeat_age_seconds=round(sample.heartbeat_age_seconds, 4),
            saturation_score=round(saturation_score, 4),
            reliability_score=round(reliability_score, 4),
            efficiency_score=round(efficiency_score, 4),
            health_score=round(health_score, 4),
            metadata=sample.metadata,
        )

    def build_worker_profiles(self, samples: Iterable[WorkerTelemetrySample]) -> List[WorkerCapacityProfile]:
        profiles = [self.build_worker_profile(sample) for sample in samples]
        self.profile_history.extend(profiles)
        if len(self.profile_history) > 10000:
            self.profile_history = self.profile_history[-10000:]
        return profiles

    def build_fleet_profile(
        self,
        profiles: Iterable[WorkerCapacityProfile],
        *,
        queue_depth: int = 0,
        active_leases: int = 0,
        tenant_id: Optional[str] = None,
    ) -> WorkerFleetProfile:
        profiles_list = list(profiles)
        workers_total = len(profiles_list)

        online_states = {
            WorkerCapacityState.HEALTHY.value,
            WorkerCapacityState.UNDERUTILIZED.value,
            WorkerCapacityState.SATURATED.value,
            WorkerCapacityState.OVERLOADED.value,
        }

        workers_online = len([p for p in profiles_list if p.state in online_states])
        workers_offline = len([p for p in profiles_list if p.state == WorkerCapacityState.OFFLINE.value])
        workers_degraded = len([p for p in profiles_list if p.state == WorkerCapacityState.DEGRADED.value])

        total_capacity = sum(p.capacity for p in profiles_list if p.state != WorkerCapacityState.OFFLINE.value)
        active_jobs = sum(p.active_jobs for p in profiles_list if p.state != WorkerCapacityState.OFFLINE.value)
        available_capacity = sum(p.available_capacity for p in profiles_list if p.state != WorkerCapacityState.OFFLINE.value)

        utilizations = [p.utilization for p in profiles_list if p.state != WorkerCapacityState.OFFLINE.value]
        failure_rates = [p.failure_rate for p in profiles_list]
        throughputs = [p.throughput_per_minute for p in profiles_list if p.state != WorkerCapacityState.OFFLINE.value]
        health_scores = [p.health_score for p in profiles_list]

        avg_utilization = mean_or_zero(utilizations)
        p95_utilization = p95_or_zero(utilizations)
        avg_failure_rate = mean_or_zero(failure_rates)
        avg_throughput = sum(throughputs)

        queue_pressure = clamp(safe_divide(queue_depth, max(1, total_capacity)))
        saturation_score = clamp((avg_utilization * 0.55) + (p95_utilization * 0.25) + (queue_pressure * 0.20))
        reliability_score = clamp(1.0 - avg_failure_rate)
        health_score = clamp((mean_or_zero(health_scores) * 0.55) + (reliability_score * 0.25) + ((1.0 - queue_pressure) * 0.20))

        profile = WorkerFleetProfile(
            fleet_id=f"fleet_{uuid.uuid4().hex}",
            tenant_id=tenant_id,
            workers_total=workers_total,
            workers_online=workers_online,
            workers_offline=workers_offline,
            workers_degraded=workers_degraded,
            total_capacity=total_capacity,
            active_jobs=active_jobs,
            available_capacity=available_capacity,
            avg_utilization=round(avg_utilization, 4),
            p95_utilization=round(p95_utilization, 4),
            avg_failure_rate=round(avg_failure_rate, 4),
            avg_throughput_per_minute=round(avg_throughput, 4),
            queue_depth=int(queue_depth),
            active_leases=int(active_leases),
            saturation_score=round(saturation_score, 4),
            reliability_score=round(reliability_score, 4),
            health_score=round(health_score, 4),
        )

        self.fleet_history.append(profile)
        if len(self.fleet_history) > 1000:
            self.fleet_history = self.fleet_history[-1000:]
        return profile

    def forecast_capacity(
        self,
        fleet_profile: WorkerFleetProfile,
        *,
        target_clear_minutes: float = 15.0,
        tenant_id: Optional[str] = None,
    ) -> WorkerCapacityForecast:
        target_clear_minutes = max(1.0, float(target_clear_minutes))
        avg_throughput_per_worker = safe_divide(
            fleet_profile.avg_throughput_per_minute,
            max(1, fleet_profile.workers_online),
            default=float(self.default_worker_capacity),
        )

        queue_work = max(0, fleet_profile.queue_depth)
        current_clear_rate = max(0.001, fleet_profile.avg_throughput_per_minute)
        projected_minutes_to_clear = safe_divide(queue_work, current_clear_rate, 0.0)

        required_total_throughput = safe_divide(queue_work, target_clear_minutes, 0.0)
        required_workers_for_queue = math.ceil(
            safe_divide(required_total_throughput, max(0.001, avg_throughput_per_worker), 0.0)
        )

        required_workers_for_active_load = math.ceil(
            safe_divide(
                fleet_profile.active_jobs,
                max(1, self.default_worker_capacity * self.target_utilization),
                0.0,
            )
        )

        projected_required_workers = max(
            1 if queue_work or fleet_profile.active_jobs else 0,
            required_workers_for_queue,
            required_workers_for_active_load,
        )

        projected_worker_delta = projected_required_workers - fleet_profile.workers_online
        projected_capacity_needed = max(0, projected_required_workers * self.default_worker_capacity)

        confidence = 0.75
        if fleet_profile.workers_online >= 3:
            confidence += 0.10
        if fleet_profile.avg_throughput_per_minute > 0:
            confidence += 0.10
        if fleet_profile.avg_failure_rate > self.failure_rate_threshold:
            confidence -= 0.20
        confidence = clamp(confidence)

        forecast = WorkerCapacityForecast(
            forecast_id=f"wcf_{uuid.uuid4().hex}",
            tenant_id=tenant_id,
            current_workers=fleet_profile.workers_online,
            current_capacity=fleet_profile.total_capacity,
            current_active_jobs=fleet_profile.active_jobs,
            current_queue_depth=fleet_profile.queue_depth,
            projected_required_workers=projected_required_workers,
            projected_worker_delta=projected_worker_delta,
            projected_capacity_needed=projected_capacity_needed,
            projected_minutes_to_clear_queue=round(projected_minutes_to_clear, 4),
            confidence=round(confidence, 4),
            assumptions={
                "target_clear_minutes": target_clear_minutes,
                "avg_throughput_per_worker": round(avg_throughput_per_worker, 4),
                "target_utilization": self.target_utilization,
                "default_worker_capacity": self.default_worker_capacity,
            },
        )

        self.forecast_history.append(forecast)
        if len(self.forecast_history) > 1000:
            self.forecast_history = self.forecast_history[-1000:]
        return forecast

    def recommend_scaling(
        self,
        *,
        fleet_profile: WorkerFleetProfile,
        forecast: WorkerCapacityForecast,
        worker_profiles: Iterable[WorkerCapacityProfile],
    ) -> List[WorkerScalingRecommendation]:
        recommendations: List[WorkerScalingRecommendation] = []
        profiles = list(worker_profiles)

        if fleet_profile.workers_online == 0 and (fleet_profile.queue_depth > 0 or fleet_profile.active_jobs > 0):
            recommendations.append(
                self._recommendation(
                    action=CapacityRecommendationAction.SCALE_UP,
                    severity=CapacitySeverity.CRITICAL,
                    title="No analytics workers online",
                    description="Queue or active workload exists but no workers are online.",
                    tenant_id=fleet_profile.tenant_id,
                    recommended_worker_delta=max(1, forecast.projected_required_workers),
                    confidence=0.98,
                    metadata={"queue_depth": fleet_profile.queue_depth},
                )
            )
            return recommendations

        if forecast.projected_worker_delta > 0:
            severity = CapacitySeverity.HIGH if forecast.projected_worker_delta >= 3 else CapacitySeverity.MEDIUM
            if fleet_profile.saturation_score >= self.overload_threshold:
                severity = CapacitySeverity.CRITICAL

            recommendations.append(
                self._recommendation(
                    action=CapacityRecommendationAction.SCALE_UP,
                    severity=severity,
                    title="Scale up analytics workers",
                    description="Projected queue and active workload exceed target capacity.",
                    tenant_id=fleet_profile.tenant_id,
                    recommended_worker_delta=forecast.projected_worker_delta,
                    confidence=forecast.confidence,
                    metadata={
                        "current_workers": forecast.current_workers,
                        "projected_required_workers": forecast.projected_required_workers,
                        "projected_minutes_to_clear_queue": forecast.projected_minutes_to_clear_queue,
                    },
                )
            )

        if (
            forecast.projected_worker_delta < 0
            and fleet_profile.avg_utilization <= self.underutilized_threshold
            and fleet_profile.queue_depth == 0
            and fleet_profile.workers_online > 1
        ):
            recommendations.append(
                self._recommendation(
                    action=CapacityRecommendationAction.SCALE_DOWN,
                    severity=CapacitySeverity.LOW,
                    title="Scale down idle analytics workers",
                    description="Worker fleet is underutilized with no queue pressure.",
                    tenant_id=fleet_profile.tenant_id,
                    recommended_worker_delta=forecast.projected_worker_delta,
                    confidence=0.80,
                    metadata={
                        "avg_utilization": fleet_profile.avg_utilization,
                        "workers_online": fleet_profile.workers_online,
                    },
                )
            )

        saturated = [p for p in profiles if p.state in {WorkerCapacityState.SATURATED.value, WorkerCapacityState.OVERLOADED.value}]
        underutilized = [p for p in profiles if p.state == WorkerCapacityState.UNDERUTILIZED.value]

        if saturated and underutilized:
            recommendations.append(
                self._recommendation(
                    action=CapacityRecommendationAction.REBALANCE,
                    severity=CapacitySeverity.MEDIUM,
                    title="Rebalance analytics workload",
                    description="Some workers are saturated while others are underutilized.",
                    tenant_id=fleet_profile.tenant_id,
                    confidence=0.86,
                    metadata={
                        "saturated_workers": [p.worker_id for p in saturated[:10]],
                        "underutilized_workers": [p.worker_id for p in underutilized[:10]],
                    },
                )
            )

        for profile in profiles:
            if profile.state == WorkerCapacityState.DEGRADED.value and profile.failure_rate >= self.failure_rate_threshold:
                recommendations.append(
                    self._recommendation(
                        action=CapacityRecommendationAction.QUARANTINE_WORKER,
                        severity=CapacitySeverity.HIGH,
                        title="Quarantine degraded analytics worker",
                        description="Worker failure rate exceeds configured threshold.",
                        tenant_id=profile.tenant_id,
                        worker_id=profile.worker_id,
                        confidence=0.90,
                        metadata={"failure_rate": profile.failure_rate, "health_score": profile.health_score},
                    )
                )

            if profile.state == WorkerCapacityState.OFFLINE.value:
                recommendations.append(
                    self._recommendation(
                        action=CapacityRecommendationAction.DRAIN_WORKER,
                        severity=CapacitySeverity.MEDIUM,
                        title="Drain offline analytics worker",
                        description="Worker heartbeat is stale or worker is offline.",
                        tenant_id=profile.tenant_id,
                        worker_id=profile.worker_id,
                        confidence=0.85,
                        metadata={"heartbeat_age_seconds": profile.heartbeat_age_seconds},
                    )
                )

        self.recommendation_history.extend(recommendations)
        if len(self.recommendation_history) > 5000:
            self.recommendation_history = self.recommendation_history[-5000:]
        return recommendations

    def _recommendation(
        self,
        *,
        action: CapacityRecommendationAction,
        severity: CapacitySeverity,
        title: str,
        description: str,
        tenant_id: Optional[str] = None,
        worker_id: Optional[str] = None,
        recommended_worker_delta: int = 0,
        confidence: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> WorkerScalingRecommendation:
        return WorkerScalingRecommendation(
            recommendation_id=f"wcr_{uuid.uuid4().hex}",
            action=action.value,
            severity=severity.value,
            title=title,
            description=description,
            tenant_id=tenant_id,
            worker_id=worker_id,
            recommended_worker_delta=int(recommended_worker_delta),
            confidence=round(clamp(confidence), 4),
            metadata=metadata or {},
        )

    def analyze(
        self,
        *,
        samples: Iterable[WorkerTelemetrySample],
        queue_depth: int = 0,
        active_leases: int = 0,
        tenant_id: Optional[str] = None,
        target_clear_minutes: float = 15.0,
    ) -> WorkerCapacityReport:
        samples_list = list(samples)
        self.collect_samples(samples_list)

        worker_profiles = self.build_worker_profiles(samples_list)
        fleet_profile = self.build_fleet_profile(
            worker_profiles,
            queue_depth=queue_depth,
            active_leases=active_leases,
            tenant_id=tenant_id,
        )
        forecast = self.forecast_capacity(
            fleet_profile,
            target_clear_minutes=target_clear_minutes,
            tenant_id=tenant_id,
        )
        recommendations = self.recommend_scaling(
            fleet_profile=fleet_profile,
            forecast=forecast,
            worker_profiles=worker_profiles,
        )

        return WorkerCapacityReport(
            report_id=f"wcap_{uuid.uuid4().hex}",
            fleet_profile=fleet_profile,
            worker_profiles=worker_profiles,
            forecast=forecast,
            recommendations=recommendations,
        )

    def analyze_from_runtime(
        self,
        *,
        workers: Iterable[Any],
        queue_metrics: Optional[Dict[str, Any]] = None,
        tenant_id: Optional[str] = None,
        target_clear_minutes: float = 15.0,
    ) -> WorkerCapacityReport:
        queue_metrics = queue_metrics or {}
        samples = self.collect_from_runtime_metrics(
            workers=workers,
            queue_metrics=queue_metrics,
            tenant_id=tenant_id,
        )

        return self.analyze(
            samples=samples,
            queue_depth=int(queue_metrics.get("queue_depth", 0)),
            active_leases=int(queue_metrics.get("active_leases", 0)),
            tenant_id=tenant_id,
            target_clear_minutes=target_clear_minutes,
        )

    def worker_rankings(
        self,
        profiles: Optional[Iterable[WorkerCapacityProfile]] = None,
    ) -> List[WorkerCapacityProfile]:
        profiles_list = list(profiles) if profiles is not None else list(self.profile_history)
        return sorted(
            profiles_list,
            key=lambda p: (
                -p.health_score,
                -p.efficiency_score,
                p.failure_rate,
                p.worker_id,
            ),
        )

    def capacity_summary(self) -> Dict[str, Any]:
        latest_fleet = self.fleet_history[-1] if self.fleet_history else None
        latest_forecast = self.forecast_history[-1] if self.forecast_history else None

        return {
            "samples": len(self.sample_history),
            "worker_profiles": len(self.profile_history),
            "fleet_profiles": len(self.fleet_history),
            "forecasts": len(self.forecast_history),
            "recommendations": len(self.recommendation_history),
            "latest_fleet": asdict(latest_fleet) if latest_fleet else None,
            "latest_forecast": asdict(latest_forecast) if latest_forecast else None,
            "generated_at": utc_now_iso(),
        }


def create_worker_capacity_model(
    *,
    target_utilization: float = 0.70,
    saturation_threshold: float = 0.85,
    overload_threshold: float = 0.95,
    underutilized_threshold: float = 0.20,
    failure_rate_threshold: float = 0.10,
    stale_heartbeat_seconds: float = 300.0,
    default_worker_capacity: int = 10,
) -> WorkerCapacityModel:
    return WorkerCapacityModel(
        target_utilization=target_utilization,
        saturation_threshold=saturation_threshold,
        overload_threshold=overload_threshold,
        underutilized_threshold=underutilized_threshold,
        failure_rate_threshold=failure_rate_threshold,
        stale_heartbeat_seconds=stale_heartbeat_seconds,
        default_worker_capacity=default_worker_capacity,
    )
