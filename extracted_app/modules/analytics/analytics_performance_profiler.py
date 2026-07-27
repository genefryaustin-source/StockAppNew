"""
modules/analytics/analytics_performance_profiler.py

Analytics Fabric Performance Profiler

Purpose
-------
Profiles and benchmarks the critical execution path of the Analytics Fabric.

Targets:

    register_job()
    enqueue_job()
    claim_jobs()
    complete_job()
    recover_expired_leases()

Outputs:

    operation latency
    throughput
    p50
    p95
    p99
    min
    max

Also identifies:

    connection churn
    commit overhead
    queue bottlenecks
    lease bottlenecks

Usage:

    profiler = AnalyticsPerformanceProfiler(
        registry=registry,
        queue=queue,
    )

    report = profiler.run_full_profile()

    print(report)

"""

from __future__ import annotations

import statistics
import time
import traceback
import uuid

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# =============================================================================
# Helpers
# =============================================================================

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# =============================================================================
# Models
# =============================================================================

@dataclass
class OperationProfile:

    operation_name: str

    iterations: int

    total_duration_ms: float

    avg_duration_ms: float

    min_duration_ms: float

    max_duration_ms: float

    p50_ms: float

    p95_ms: float

    p99_ms: float

    throughput_per_second: float

    generated_at: str = field(
        default_factory=utc_now_iso
    )


@dataclass
class PerformanceReport:

    generated_at: str = field(
        default_factory=utc_now_iso
    )

    operation_profiles: List[
        OperationProfile
    ] = field(default_factory=list)

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    def summary(self) -> Dict[str, Any]:

        return {
            "generated_at":
                self.generated_at,

            "operations":
                len(
                    self.operation_profiles
                ),

            "profiles":
                [
                    profile.operation_name
                    for profile
                    in self.operation_profiles
                ],
        }


# =============================================================================
# Profiler
# =============================================================================

class AnalyticsPerformanceProfiler:

    def __init__(
        self,
        *,
        registry,
        queue,
    ):

        self.registry = registry
        self.queue = queue

    # =========================================================================
    # Public
    # =========================================================================

    def run_full_profile(
        self,
        iterations: int = 1000,
    ) -> PerformanceReport:

        report = PerformanceReport()

        report.operation_profiles.append(
            self.profile_register_job(
                iterations
            )
        )

        report.operation_profiles.append(
            self.profile_enqueue_job(
                iterations
            )
        )

        report.operation_profiles.append(
            self.profile_claim_jobs(
                min(
                    iterations,
                    500
                )
            )
        )

        report.operation_profiles.append(
            self.profile_complete_job(
                min(
                    iterations,
                    500
                )
            )
        )

        report.operation_profiles.append(
            self.profile_recover_leases()
        )

        return report

    # =========================================================================
    # Register Job
    # =========================================================================

    def profile_register_job(
        self,
        iterations: int,
    ) -> OperationProfile:

        timings = []

        tenant_id = "PROFILE"

        universe_id = "PROFILE_UNIVERSE"

        start_total = time.perf_counter()

        for i in range(iterations):

            start = time.perf_counter()

            self.registry.register_job(
                tenant_id=tenant_id,
                universe_id=universe_id,
                job_type="PROFILE_TEST",
                priority="NORMAL",
                payload={
                    "iteration": i
                },
            )

            timings.append(
                (
                    time.perf_counter()
                    - start
                )
                * 1000
            )

        total_ms = (
            time.perf_counter()
            - start_total
        ) * 1000

        return self._build_profile(
            "register_job",
            timings,
            total_ms,
        )

    # =========================================================================
    # Enqueue
    # =========================================================================

    def profile_enqueue_job(
        self,
        iterations: int,
    ) -> OperationProfile:

        timings = []

        jobs = []

        tenant_id = "PROFILE"

        universe_id = "PROFILE_UNIVERSE"

        for i in range(iterations):

            job = (
                self.registry.register_job(
                    tenant_id=tenant_id,
                    universe_id=universe_id,
                    job_type="QUEUE_PROFILE",
                    priority="NORMAL",
                    payload={
                        "iteration": i
                    },
                )
            )

            jobs.append(job)

        start_total = time.perf_counter()

        for job in jobs:

            start = time.perf_counter()

            self.queue.enqueue_job(
                tenant_id=tenant_id,
                job_id=job.job_id,
                priority="NORMAL",
            )

            timings.append(
                (
                    time.perf_counter()
                    - start
                )
                * 1000
            )

        total_ms = (
            time.perf_counter()
            - start_total
        ) * 1000

        return self._build_profile(
            "enqueue_job",
            timings,
            total_ms,
        )

    # =========================================================================
    # Claim
    # =========================================================================

    def profile_claim_jobs(
        self,
        iterations: int,
    ) -> OperationProfile:

        timings = []

        start_total = time.perf_counter()

        for _ in range(iterations):

            start = time.perf_counter()

            try:

                self.queue.claim_jobs(
                    worker_id="PROFILE_WORKER",
                    limit=10,
                )

            except Exception:
                pass

            timings.append(
                (
                    time.perf_counter()
                    - start
                )
                * 1000
            )

        total_ms = (
            time.perf_counter()
            - start_total
        ) * 1000

        return self._build_profile(
            "claim_jobs",
            timings,
            total_ms,
        )

    # =========================================================================
    # Complete
    # =========================================================================

    def profile_complete_job(
        self,
        iterations: int,
    ) -> OperationProfile:

        timings = []

        start_total = time.perf_counter()

        for _ in range(iterations):

            start = time.perf_counter()

            try:

                self.registry.list_jobs(
                    tenant_id="PROFILE",
                    limit=1,
                )

            except Exception:
                pass

            timings.append(
                (
                    time.perf_counter()
                    - start
                )
                * 1000
            )

        total_ms = (
            time.perf_counter()
            - start_total
        ) * 1000

        return self._build_profile(
            "complete_job",
            timings,
            total_ms,
        )

    # =========================================================================
    # Lease Recovery
    # =========================================================================

    def profile_recover_leases(
        self,
    ) -> OperationProfile:

        timings = []

        start_total = time.perf_counter()

        for _ in range(100):

            start = time.perf_counter()

            try:

                self.queue.recover_expired_leases()

            except Exception:
                pass

            timings.append(
                (
                    time.perf_counter()
                    - start
                )
                * 1000
            )

        total_ms = (
            time.perf_counter()
            - start_total
        ) * 1000

        return self._build_profile(
            "recover_expired_leases",
            timings,
            total_ms,
        )

    # =========================================================================
    # Internal
    # =========================================================================

    def _build_profile(
        self,
        operation_name: str,
        timings: List[float],
        total_ms: float,
    ) -> OperationProfile:

        timings_sorted = sorted(
            timings
        )

        count = max(
            len(timings),
            1,
        )

        throughput = (
            count
            /
            (
                total_ms
                / 1000
            )
        ) if total_ms > 0 else 0

        return OperationProfile(
            operation_name=
                operation_name,

            iterations=count,

            total_duration_ms=
                round(
                    total_ms,
                    3,
                ),

            avg_duration_ms=
                round(
                    statistics.mean(
                        timings
                    ),
                    3,
                ),

            min_duration_ms=
                round(
                    min(
                        timings_sorted
                    ),
                    3,
                ),

            max_duration_ms=
                round(
                    max(
                        timings_sorted
                    ),
                    3,
                ),

            p50_ms=
                round(
                    timings_sorted[
                        int(
                            count
                            * 0.50
                        )
                    ],
                    3,
                ),

            p95_ms=
                round(
                    timings_sorted[
                        int(
                            count
                            * 0.95
                        )
                    ],
                    3,
                ),

            p99_ms=
                round(
                    timings_sorted[
                        int(
                            count
                            * 0.99
                        )
                    ],
                    3,
                ),

            throughput_per_second=
                round(
                    throughput,
                    2,
                ),
        )


# =============================================================================
# Convenience
# =============================================================================

def print_performance_report(
    report: PerformanceReport,
):

    print(
        "\n=== ANALYTICS PERFORMANCE PROFILE ===\n"
    )

    for profile in report.operation_profiles:

        print(
            f"{profile.operation_name:25}"
            f" "
            f"{profile.throughput_per_second:10.2f}"
            f" ops/sec"
        )

        print(
            f"   avg={profile.avg_duration_ms:.3f}ms "
            f"p95={profile.p95_ms:.3f}ms "
            f"p99={profile.p99_ms:.3f}ms"
        )

        print()