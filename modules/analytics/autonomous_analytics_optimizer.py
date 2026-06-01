"""
modules/analytics/autonomous_analytics_optimizer.py
"""

from __future__ import annotations

import statistics
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional


# =============================================================================
# Helpers
# =============================================================================

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# =============================================================================
# Enums
# =============================================================================

class OptimizationSeverity(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class OptimizationCategory(str, Enum):
    QUEUE = "QUEUE"
    WORKER = "WORKER"
    PROVIDER = "PROVIDER"
    SCHEDULER = "SCHEDULER"
    RUNTIME = "RUNTIME"
    TENANT = "TENANT"
    UNIVERSE = "UNIVERSE"
    COST = "COST"


class OptimizationAction(str, Enum):
    SCALE_UP = "SCALE_UP"
    SCALE_DOWN = "SCALE_DOWN"
    THROTTLE_PROVIDER = "THROTTLE_PROVIDER"
    REBALANCE = "REBALANCE"
    SPLIT_UNIVERSE = "SPLIT_UNIVERSE"
    MERGE_UNIVERSES = "MERGE_UNIVERSES"
    INCREASE_REFRESH_INTERVAL = "INCREASE_REFRESH_INTERVAL"
    DECREASE_REFRESH_INTERVAL = "DECREASE_REFRESH_INTERVAL"
    TUNE_QUEUE = "TUNE_QUEUE"
    NO_ACTION = "NO_ACTION"


# =============================================================================
# Models
# =============================================================================

@dataclass
class OptimizationTelemetry:
    queue_depth: int = 0
    active_leases: int = 0
    workers_online: int = 0
    worker_utilization: float = 0.0
    failed_jobs: int = 0
    completed_jobs: int = 0
    avg_execution_time_seconds: float = 0.0
    avg_queue_wait_seconds: float = 0.0
    provider_metrics: Dict[str, Any] = field(default_factory=dict)
    tenant_metrics: Dict[str, Any] = field(default_factory=dict)
    universe_metrics: Dict[str, Any] = field(default_factory=dict)
    scheduler_metrics: Dict[str, Any] = field(default_factory=dict)
    runtime_metrics: Dict[str, Any] = field(default_factory=dict)
    governor_metrics: Dict[str, Any] = field(default_factory=dict)
    collected_at: str = field(default_factory=utc_now_iso)


@dataclass
class ProviderPerformanceProfile:
    provider_name: str
    success_rate: float = 1.0
    avg_latency_ms: float = 0.0
    throttle_events: int = 0
    failures: int = 0
    score: float = 100.0


@dataclass
class WorkerPerformanceProfile:
    worker_id: str
    utilization: float = 0.0
    avg_runtime_seconds: float = 0.0
    jobs_completed: int = 0
    failures: int = 0
    score: float = 100.0


@dataclass
class TenantPerformanceProfile:
    tenant_id: str
    jobs_submitted: int = 0
    jobs_completed: int = 0
    avg_runtime_seconds: float = 0.0
    score: float = 100.0


@dataclass
class UniversePerformanceProfile:
    universe_id: str
    jobs_completed: int = 0
    avg_runtime_seconds: float = 0.0
    refresh_interval_minutes: int = 60
    score: float = 100.0


@dataclass
class OptimizationRecommendation:
    recommendation_id: str
    category: str
    action: str
    severity: str
    title: str
    description: str
    expected_impact: str
    confidence: float
    generated_at: str = field(default_factory=utc_now_iso)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OptimizationPlan:
    plan_id: str
    recommendations: List[OptimizationRecommendation]
    created_at: str = field(default_factory=utc_now_iso)
    estimated_improvement_pct: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OptimizationExecution:
    execution_id: str
    plan_id: str
    action: str
    success: bool
    executed_at: str = field(default_factory=utc_now_iso)
    result: Dict[str, Any] = field(default_factory=dict)
@dataclass
class QueuePerformanceProfile:
    queue_depth: int = 0
    avg_wait_seconds: float = 0.0
    growth_rate: float = 0.0
    retry_pressure: float = 0.0
    bottleneck_detected: bool = False
    score: float = 100.0
    generated_at: str = field(default_factory=utc_now_iso)


@dataclass
class RuntimePerformanceProfile:
    completion_rate: float = 1.0
    failure_rate: float = 0.0
    throughput: float = 0.0
    lease_pressure: float = 0.0
    stability_score: float = 100.0
    generated_at: str = field(default_factory=utc_now_iso)


@dataclass
class SchedulerPerformanceProfile:
    due_schedules: int = 0
    jobs_created: int = 0
    scheduler_pressure: float = 0.0
    over_scheduling_detected: bool = False
    score: float = 100.0
    generated_at: str = field(default_factory=utc_now_iso)


@dataclass
class OptimizationBaseline:
    baseline_id: str
    metrics: Dict[str, Any]
    created_at: str = field(default_factory=utc_now_iso)


@dataclass
class OptimizationEffectiveness:
    effectiveness_id: str
    execution_id: str
    before_metrics: Dict[str, Any]
    after_metrics: Dict[str, Any]
    improvement_pct: float
    success: bool
    roi_score: float = 0.0
    measured_at: str = field(default_factory=utc_now_iso)


@dataclass
class OptimizationLearningRecord:
    learning_id: str
    source_action: str
    success: bool
    confidence_adjustment: float
    notes: str
    created_at: str = field(default_factory=utc_now_iso)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class OptimizationMetrics:
    telemetry_collections: int = 0
    plans_generated: int = 0
    recommendations_generated: int = 0
    optimizations_executed: int = 0
    successful_optimizations: int = 0
    baselines_created: int = 0
    effectiveness_measurements: int = 0
    learning_records: int = 0
    queue_bottlenecks_detected: int = 0
    runtime_pressure_events: int = 0
    provider_rankings_generated: int = 0
    worker_rankings_generated: int = 0
    generated_at: str = field(default_factory=utc_now_iso)


# =============================================================================
# Optimizer
# =============================================================================

class AutonomousAnalyticsOptimizer:
    """
    Self-tuning analytics optimization engine.

    Consumes telemetry from:
        - Scheduler
        - Registry
        - Queue
        - Runtime Controller
        - Governor
        - Orchestrator

    Produces:
        - Optimization plans
        - Scaling recommendations
        - Queue tuning recommendations
        - Refresh interval recommendations
        - Provider routing recommendations
    """

    def __init__(self):
        self.telemetry_history: List[OptimizationTelemetry] = []
        self.recommendation_history: List[
            OptimizationRecommendation
        ] = []
        self.plan_history: List[OptimizationPlan] = []
        self.execution_history: List[
            OptimizationExecution
        ] = []
        self.queue_profiles: List[QueuePerformanceProfile] = []
        self.runtime_profiles: List[RuntimePerformanceProfile] = []
        self.scheduler_profiles: List[SchedulerPerformanceProfile] = []

        self.optimization_baselines: List[OptimizationBaseline] = []
        self.optimization_effectiveness: List[OptimizationEffectiveness] = []
        self.learning_history: List[OptimizationLearningRecord] = []

        self.provider_rankings_cache: List[ProviderPerformanceProfile] = []
        self.worker_rankings_cache: List[WorkerPerformanceProfile] = []
        self.tenant_profiles_cache: List[TenantPerformanceProfile] = []
        self.universe_profiles_cache: List[UniversePerformanceProfile] = []
        self.metrics = OptimizationMetrics()

    # =========================================================================
    # Telemetry Collection
    # =========================================================================

    def collect_telemetry(
        self,
        telemetry: OptimizationTelemetry,
    ) -> None:

        self.telemetry_history.append(
            telemetry
        )

        self.metrics.telemetry_collections += 1

    # =========================================================================
    # Queue Analysis
    # =========================================================================

    def analyze_queue_performance(
        self,
    ) -> List[OptimizationRecommendation]:

        recommendations = []

        latest = self._latest()

        if not latest:
            return recommendations

        if latest.queue_depth > 5000:

            recommendations.append(
                self._recommendation(
                    category=
                        OptimizationCategory.QUEUE,
                    action=
                        OptimizationAction.SCALE_UP,
                    severity=
                        OptimizationSeverity.HIGH,
                    title=
                        "Queue Congestion",
                    description=
                        "Queue depth is above threshold.",
                    impact=
                        "Reduce backlog and wait times.",
                    confidence=0.92,
                )
            )

        if latest.avg_queue_wait_seconds > 300:

            recommendations.append(
                self._recommendation(
                    category=
                        OptimizationCategory.QUEUE,
                    action=
                        OptimizationAction.TUNE_QUEUE,
                    severity=
                        OptimizationSeverity.MEDIUM,
                    title=
                        "Queue Latency",
                    description=
                        "Queue wait time elevated.",
                    impact=
                        "Improve job responsiveness.",
                    confidence=0.80,
                )
            )

        return recommendations

    # =========================================================================
    # Worker Analysis
    # =========================================================================

    def analyze_worker_performance(
        self,
    ) -> List[OptimizationRecommendation]:

        recommendations = []

        latest = self._latest()

        if not latest:
            return recommendations

        if latest.worker_utilization > 0.85:

            recommendations.append(
                self._recommendation(
                    category=
                        OptimizationCategory.WORKER,
                    action=
                        OptimizationAction.SCALE_UP,
                    severity=
                        OptimizationSeverity.HIGH,
                    title=
                        "Worker Saturation",
                    description=
                        "Workers highly utilized.",
                    impact=
                        "Increase throughput.",
                    confidence=0.95,
                )
            )

        elif latest.worker_utilization < 0.20:

            recommendations.append(
                self._recommendation(
                    category=
                        OptimizationCategory.WORKER,
                    action=
                        OptimizationAction.SCALE_DOWN,
                    severity=
                        OptimizationSeverity.LOW,
                    title=
                        "Worker Underutilization",
                    description=
                        "Workers mostly idle.",
                    impact=
                        "Reduce operating cost.",
                    confidence=0.75,
                )
            )

        return recommendations

    # =========================================================================
    # Provider Analysis
    # =========================================================================

    def analyze_provider_performance(
        self,
    ) -> List[OptimizationRecommendation]:

        recommendations = []

        latest = self._latest()

        if not latest:
            return recommendations

        providers = (
            latest.provider_metrics or {}
        )

        for provider, metrics in providers.items():

            latency = metrics.get(
                "avg_latency_ms",
                0,
            )

            failure_rate = metrics.get(
                "failure_rate",
                0,
            )

            if latency > 2000:

                recommendations.append(
                    self._recommendation(
                        category=
                            OptimizationCategory.PROVIDER,
                        action=
                            OptimizationAction.REBALANCE,
                        severity=
                            OptimizationSeverity.MEDIUM,
                        title=
                            f"{provider} latency",
                        description=
                            "Provider latency elevated.",
                        impact=
                            "Improve execution speed.",
                        confidence=0.82,
                        metadata={
                            "provider":
                                provider
                        },
                    )
                )

            if failure_rate > 0.10:

                recommendations.append(
                    self._recommendation(
                        category=
                            OptimizationCategory.PROVIDER,
                        action=
                            OptimizationAction
                            .THROTTLE_PROVIDER,
                        severity=
                            OptimizationSeverity.HIGH,
                        title=
                            f"{provider} failures",
                        description=
                            "Provider failure rate elevated.",
                        impact=
                            "Improve reliability.",
                        confidence=0.90,
                        metadata={
                            "provider":
                                provider
                        },
                    )
                )

        return recommendations

    # =========================================================================
    # Scheduler Analysis
    # =========================================================================

    def analyze_scheduler_performance(
        self,
    ) -> List[OptimizationRecommendation]:

        recommendations = []

        latest = self._latest()

        if not latest:
            return recommendations

        due_jobs = (
            latest.scheduler_metrics
            .get("due_schedules", 0)
        )

        if due_jobs > 1000:

            recommendations.append(
                self._recommendation(
                    category=
                        OptimizationCategory.SCHEDULER,
                    action=
                        OptimizationAction
                        .INCREASE_REFRESH_INTERVAL,
                    severity=
                        OptimizationSeverity.MEDIUM,
                    title=
                        "Scheduler Pressure",
                    description=
                        "Large number of due schedules.",
                    impact=
                        "Reduce scheduler load.",
                    confidence=0.78,
                )
            )

        return recommendations

    # =========================================================================
    # Runtime Analysis
    # =========================================================================

    def analyze_runtime_performance(
        self,
    ) -> List[OptimizationRecommendation]:

        recommendations = []

        latest = self._latest()

        if not latest:
            return recommendations

        if latest.failed_jobs > latest.completed_jobs:

            recommendations.append(
                self._recommendation(
                    category=
                        OptimizationCategory.RUNTIME,
                    action=
                        OptimizationAction.REBALANCE,
                    severity=
                        OptimizationSeverity.CRITICAL,
                    title=
                        "Runtime Instability",
                    description=
                        "Failures exceed completions.",
                    impact=
                        "Restore execution stability.",
                    confidence=0.97,
                )
            )

        return recommendations

    # =========================================================================
    # Optimization Plan Generation
    # =========================================================================

    def generate_optimization_plan(
        self,
    ) -> OptimizationPlan:

        recommendations: List[
            OptimizationRecommendation
        ] = []

        recommendations.extend(
            self.analyze_queue_performance()
        )

        recommendations.extend(
            self.analyze_worker_performance()
        )

        recommendations.extend(
            self.analyze_provider_performance()
        )

        recommendations.extend(
            self.analyze_scheduler_performance()
        )

        recommendations.extend(
            self.analyze_runtime_performance()
        )
        recommendations.extend(
            self.detect_queue_bottlenecks()
        )

        recommendations.extend(
            self.detect_runtime_pressure()
        )

        recommendations.extend(
            self.analyze_tenant_efficiency()
        )

        recommendations.extend(
            self.analyze_universe_efficiency()
        )

        plan = OptimizationPlan(
            plan_id=
                f"plan_{uuid.uuid4().hex}",
            recommendations=
                recommendations,
            estimated_improvement_pct=
                self._estimate_improvement(
                    recommendations
                ),
        )

        self.plan_history.append(
            plan
        )

        self.metrics.plans_generated += 1

        self.metrics.recommendations_generated += (
            len(recommendations)
        )

        self.recommendation_history.extend(
            recommendations
        )

        return plan

    # =========================================================================
    # Safe Autonomous Actions
    # =========================================================================

    def execute_safe_optimizations(
        self,
        plan: OptimizationPlan,
    ) -> List[OptimizationExecution]:

        executions = []

        for recommendation in plan.recommendations:

            if recommendation.severity in {
                OptimizationSeverity.CRITICAL.value,
                OptimizationSeverity.HIGH.value,
            }:
                continue

            execution = OptimizationExecution(
                execution_id=
                    f"exec_{uuid.uuid4().hex}",
                plan_id=
                    plan.plan_id,
                action=
                    recommendation.action,
                success=True,
                result={
                    "recommendation":
                        recommendation.title
                },
            )

            executions.append(
                execution
            )

            self.execution_history.append(
                execution
            )

            self.metrics.optimizations_executed += 1
            self.metrics.successful_optimizations += 1
            self.learn_from_execution(
                execution=execution,
                recommendation=recommendation,
            )

        return executions

    # =========================================================================
    # Profiles
    # =========================================================================

    def provider_profiles(
        self,
    ) -> List[
        ProviderPerformanceProfile
    ]:

        latest = self._latest()

        if not latest:
            return []

        profiles = []

        for provider, metrics in (
            latest.provider_metrics.items()
        ):
            profiles.append(
                ProviderPerformanceProfile(
                    provider_name=provider,
                    success_rate=
                        metrics.get(
                            "success_rate",
                            1.0,
                        ),
                    avg_latency_ms=
                        metrics.get(
                            "avg_latency_ms",
                            0,
                        ),
                    failures=
                        metrics.get(
                            "failures",
                            0,
                        ),
                    throttle_events=
                        metrics.get(
                            "throttle_events",
                            0,
                        ),
                )
            )

        return profiles

    # =========================================================================
    # Metrics
    # =========================================================================

    def optimization_metrics(
        self,
    ) -> Dict[str, Any]:

        return {
            **asdict(self.metrics),
            "telemetry_samples":
                len(
                    self.telemetry_history
                ),
            "plans":
                len(
                    self.plan_history
                ),
            "executions":
                len(
                    self.execution_history
                ),
            "queue_profiles": len(self.queue_profiles),
            "runtime_profiles": len(self.runtime_profiles),
            "scheduler_profiles": len(self.scheduler_profiles),
            "baselines": len(self.optimization_baselines),
            "effectiveness_records": len(self.optimization_effectiveness),
            "learning_records": len(self.learning_history),
            "provider_rankings": len(self.provider_rankings_cache),
            "worker_rankings": len(self.worker_rankings_cache),
            "generated_at":
                utc_now_iso(),
        }

    # =========================================================================
    # Internal
    # =========================================================================

    def _latest(
        self,
    ) -> Optional[
        OptimizationTelemetry
    ]:

        if not self.telemetry_history:
            return None

        return self.telemetry_history[-1]

    def _estimate_improvement(
        self,
        recommendations:
        List[
            OptimizationRecommendation
        ],
    ) -> float:

        if not recommendations:
            return 0.0

        scores = [
            r.confidence
            for r in recommendations
        ]

        return round(
            statistics.mean(scores) * 25,
            2,
        )

    def _recommendation(
        self,
        category,
        action,
        severity,
        title,
        description,
        impact,
        confidence,
        metadata=None,
    ) -> OptimizationRecommendation:

        return OptimizationRecommendation(
            recommendation_id=
                f"opt_{uuid.uuid4().hex}",
            category=
                (
                    category.value
                    if hasattr(
                        category,
                        "value"
                    )
                    else category
                ),
            action=
                (
                    action.value
                    if hasattr(
                        action,
                        "value"
                    )
                    else action
                ),
            severity=
                (
                    severity.value
                    if hasattr(
                        severity,
                        "value"
                    )
                    else severity
                ),
            title=title,
            description=description,
            expected_impact=impact,
            confidence=confidence,
            metadata=metadata or {},
        )

# =============================================================================
# PHASE 2 EXTENSION METHODS
# =============================================================================

    def analyze_queue_growth(self):
        latest = self._latest()
        if not latest:
            return []
        recommendations = []
        if latest.queue_depth > 10000:
            recommendations.append(
                self._recommendation(
                    category="QUEUE",
                    action="SCALE_UP",
                    severity="HIGH",
                    title="Queue Growth Spike",
                    description="Queue depth growth indicates saturation.",
                    impact="Increase throughput.",
                    confidence=0.93,
                )
            )
        return recommendations

    def detect_queue_bottlenecks(self):
        latest = self._latest()
        if not latest:
            return []
        if latest.avg_queue_wait_seconds > 600:
            self.metrics.queue_bottlenecks_detected += 1
            return [
                self._recommendation(
                    category="QUEUE",
                    action="TUNE_QUEUE",
                    severity="HIGH",
                    title="Queue Bottleneck Detected",
                    description="Average queue wait exceeds threshold.",
                    impact="Reduce latency.",
                    confidence=0.91,
                )
            ]
        return []

    def detect_runtime_pressure(self):
        latest = self._latest()
        if not latest:
            return []
        if latest.worker_utilization > 0.95:
            self.metrics.runtime_pressure_events += 1
            return [
                self._recommendation(
                    category="RUNTIME",
                    action="SCALE_UP",
                    severity="HIGH",
                    title="Runtime Pressure",
                    description="Runtime nearing saturation.",
                    impact="Increase capacity.",
                    confidence=0.95,
                )
            ]
        return []

    def analyze_tenant_efficiency(self):
        return []

    def analyze_universe_efficiency(self):
        return []

    def provider_rankings(self):
        ranked = sorted(
            self.provider_profiles(),
            key=lambda x: (x.success_rate * 100.0) - x.failures,
            reverse=True,
        )
        self.provider_rankings_cache = ranked
        return ranked

    def worker_rankings(self):
        ranked = sorted(
            self.worker_rankings_cache,
            key=lambda x: x.score,
            reverse=True,
        )
        self.metrics.worker_rankings_generated += 1
        return ranked

    def measure_effectiveness(
        self,
        execution_id,
        before_metrics,
        after_metrics,
    ):
        before = before_metrics.get("score", 0)
        after = after_metrics.get("score", 0)
        improvement = after - before

        record = OptimizationEffectiveness(
            effectiveness_id=f"eff_{uuid.uuid4().hex}",
            execution_id=execution_id,
            before_metrics=before_metrics,
            after_metrics=after_metrics,
            improvement_pct=improvement,
            success=improvement >= 0,
            roi_score=improvement,
        )

        self.optimization_effectiveness.append(record)
        self.metrics.effectiveness_measurements += 1
        return record

    def learn_from_execution(
        self,
        execution,
        recommendation,
    ):
        record = OptimizationLearningRecord(
            learning_id=f"learn_{uuid.uuid4().hex}",
            source_action=recommendation.action,
            success=execution.success,
            confidence_adjustment=0.05 if execution.success else -0.05,
            notes=recommendation.title,
        )
        self.learning_history.append(record)
        self.metrics.learning_records += 1
        return record

    def optimization_summary(self):
        return {
            "telemetry_samples": len(self.telemetry_history),
            "plans": len(self.plan_history),
            "executions": len(self.execution_history),
            "effectiveness": len(self.optimization_effectiveness),
            "learning_records": len(self.learning_history),
        }
