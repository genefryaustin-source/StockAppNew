"""
modules/analytics/analytics_micro_benchmark.py

Analytics Fabric Micro Benchmark V2

Purpose
-------
Benchmark ONLY public Analytics Fabric APIs.

No raw SQL.
No schema assumptions.
No foreign-key issues.

Benchmarks
----------

registry.register_job()

registry.mark_queued()

queue.enqueue_job()

queue.claim_jobs()

queue.complete_job()

Outputs
-------

avg latency
p50
p95
p99
throughput/sec

Usage
-----

benchmark = AnalyticsMicroBenchmark(
    registry=registry,
    queue=queue,
)

results = benchmark.run_all(
    iterations=1000
)

print_benchmark_results(results)

"""

from __future__ import annotations

import statistics
import time

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict


# =============================================================================
# Helpers
# =============================================================================

def utc_now_iso() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


# =============================================================================
# Results
# =============================================================================

@dataclass
class BenchmarkResult:

    benchmark_name: str

    iterations: int

    avg_ms: float

    min_ms: float

    max_ms: float

    p50_ms: float

    p95_ms: float

    p99_ms: float

    total_ms: float

    throughput_per_second: float

    generated_at: str = field(
        default_factory=utc_now_iso
    )


# =============================================================================
# Benchmark
# =============================================================================

class AnalyticsMicroBenchmark:

    def __init__(
        self,
        *,
        registry,
        queue,
    ):
        self.registry = registry
        self.queue = queue

    # =========================================================================
    # Runner
    # =========================================================================

    def run_all(
        self,
        iterations: int = 1000,
    ) -> Dict[str, BenchmarkResult]:

        return {

            "registry_register_job":
                self.registry_register_job(
                    iterations
                ),

            "registry_mark_queued":
                self.registry_mark_queued(
                    iterations
                ),

            "queue_enqueue_job":
                self.queue_enqueue_job(
                    iterations
                ),

            "queue_claim_jobs":
                self.queue_claim_jobs(
                    iterations
                ),

            "queue_complete_job":
                self.queue_complete_job(
                    iterations
                ),
        }

    # =========================================================================
    # Internal Benchmark Runner
    # =========================================================================

    def _run(
        self,
        name: str,
        iterations: int,
        func: Callable[[], None],
    ) -> BenchmarkResult:

        timings = []

        start_total = time.perf_counter()

        for _ in range(iterations):

            start = time.perf_counter()

            func()

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

        timings_sorted = sorted(
            timings
        )

        return BenchmarkResult(

            benchmark_name=name,

            iterations=iterations,

            avg_ms=round(
                statistics.mean(
                    timings
                ),
                4,
            ),

            min_ms=round(
                min(
                    timings
                ),
                4,
            ),

            max_ms=round(
                max(
                    timings
                ),
                4,
            ),

            p50_ms=round(
                timings_sorted[
                    int(
                        iterations * 0.50
                    )
                ],
                4,
            ),

            p95_ms=round(
                timings_sorted[
                    int(
                        iterations * 0.95
                    )
                ],
                4,
            ),

            p99_ms=round(
                timings_sorted[
                    int(
                        iterations * 0.99
                    )
                ],
                4,
            ),

            total_ms=round(
                total_ms,
                4,
            ),

            throughput_per_second=round(
                iterations
                /
                (
                    total_ms / 1000
                ),
                2,
            ),
        )

    # =========================================================================
    # registry.register_job()
    # =========================================================================

    def registry_register_job(
        self,
        iterations: int,
    ):

        def op():

            self.registry.register_job(
                tenant_id="BENCH",
                universe_id="BENCH",
                job_type="TEST",
                payload={},
            )

        return self._run(
            "registry.register_job",
            iterations,
            op,
        )

    # =========================================================================
    # registry.mark_queued()
    # =========================================================================

    def registry_mark_queued(
        self,
        iterations: int,
    ):

        jobs = []

        for _ in range(iterations):

            job = (
                self.registry.register_job(
                    tenant_id="BENCH",
                    universe_id="BENCH",
                    job_type="TEST",
                    payload={},
                )
            )

            jobs.append(
                job.job_id
            )

        idx = [0]

        def op():

            job_id = jobs[
                idx[0]
            ]

            idx[0] += 1

            self.registry.mark_queued(
                tenant_id="BENCH",
                job_id=job_id,
            )

        return self._run(
            "registry.mark_queued",
            iterations,
            op,
        )

    # =========================================================================
    # queue.enqueue_job()
    # =========================================================================

    def queue_enqueue_job(
        self,
        iterations: int,
    ):

        jobs = []

        for _ in range(iterations):

            job = (
                self.registry.register_job(
                    tenant_id="BENCH",
                    universe_id="BENCH",
                    job_type="TEST",
                    payload={},
                )
            )

            jobs.append(
                job.job_id
            )

        idx = [0]

        def op():

            job_id = jobs[
                idx[0]
            ]

            idx[0] += 1

            self.queue.enqueue_job(
                tenant_id="BENCH",
                job_id=job_id,
                priority="NORMAL",
            )

        return self._run(
            "queue.enqueue_job",
            iterations,
            op,
        )

    # =========================================================================
    # queue.claim_jobs()
    # =========================================================================

    def queue_claim_jobs(
        self,
        iterations: int,
    ):

        for _ in range(iterations):

            job = (
                self.registry.register_job(
                    tenant_id="BENCH",
                    universe_id="BENCH",
                    job_type="TEST",
                    payload={},
                )
            )

            self.queue.enqueue_job(
                tenant_id="BENCH",
                job_id=job.job_id,
                priority="NORMAL",
            )

        def op():

            self.queue.claim_jobs(
                worker_id="BENCH_WORKER",
                limit=1,
            )

        return self._run(
            "queue.claim_jobs",
            iterations,
            op,
        )

    # =========================================================================
    # queue.complete_job()
    # =========================================================================

    def queue_complete_job(
        self,
        iterations: int,
    ):

        lease_ids = []

        for _ in range(iterations):

            job = (
                self.registry.register_job(
                    tenant_id="BENCH",
                    universe_id="BENCH",
                    job_type="TEST",
                    payload={},
                )
            )

            self.queue.enqueue_job(
                tenant_id="BENCH",
                job_id=job.job_id,
                priority="NORMAL",
            )

            leases = (
                self.queue.claim_jobs(
                    worker_id="BENCH_WORKER",
                    limit=1,
                )
            )

            if leases:
                lease_ids.append(
                    leases[0].lease_id
                )

        idx = [0]

        def op():

            lease_id = lease_ids[
                idx[0]
            ]

            idx[0] += 1

            self.queue.complete_job(
                lease_id=lease_id,
                result_ref="BENCHMARK",
            )

        return self._run(
            "queue.complete_job",
            len(lease_ids),
            op,
        )


# =============================================================================
# Output
# =============================================================================

def print_benchmark_results(
    results: Dict[
        str,
        BenchmarkResult
    ]
):

    print(
        "\n=== ANALYTICS MICRO BENCHMARK V2 ===\n"
    )

    for result in results.values():

        print(
            f"{result.benchmark_name:35}"
            f"{result.throughput_per_second:12.2f}"
            f" ops/sec"
        )

        print(
            f"   avg={result.avg_ms:.3f}ms "
            f"p95={result.p95_ms:.3f}ms "
            f"p99={result.p99_ms:.3f}ms"
        )

        print()