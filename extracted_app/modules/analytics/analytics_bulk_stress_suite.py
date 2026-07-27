"""
modules/analytics/analytics_bulk_stress_suite.py

Analytics Bulk Stress Validation Suite

Purpose
-------
Validate and compare:

    Standard Analytics Operations

vs

    AnalyticsBulkOperations

at scale.

This suite exists specifically to prove the value of:

    analytics_bulk_operations.py

by measuring:

    Registry Registration
    Queue Enqueue
    Status Updates
    Completion

using:

    Individual APIs
    Bulk APIs

Outputs
-------

Runtime
Ops/sec
Improvement Ratios

Usage
-----

from modules.analytics.analytics_bulk_stress_suite import (
    AnalyticsBulkStressSuite,
    BulkStressConfig,
)

suite = AnalyticsBulkStressSuite()

results = suite.run()

"""

from __future__ import annotations

import os
import shutil
import tempfile
import time

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Dict, Any, List

from modules.analytics.universe_job_registry import (
    UniverseJobRegistry,
)

from modules.analytics.universe_execution_queue import (
    UniverseExecutionQueue,
)

from modules.analytics.analytics_bulk_operations import (
    AnalyticsBulkOperations,
)


# =============================================================================
# Helpers
# =============================================================================

def utc_now_iso() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


# =============================================================================
# Config
# =============================================================================

@dataclass
class BulkStressConfig:

    db_path: str = (
        "data/analytics_bulk_stress.db"
    )

    reset_db: bool = True

    tenant_id: str = "STRESS"

    universe_id: str = "UNIVERSE"

    job_count: int = 10000

    verbose: bool = True


# =============================================================================
# Result
# =============================================================================

@dataclass
class BulkStressResult:

    phase: str

    operation_count: int

    elapsed_seconds: float

    throughput_per_second: float

    generated_at: str


# =============================================================================
# Suite
# =============================================================================

class AnalyticsBulkStressSuite:

    def __init__(
        self,
        config: BulkStressConfig | None = None,
    ):

        self.config = (
            config
            or BulkStressConfig()
        )

        self.registry = None

        self.queue = None

        self.bulk = None

    # =========================================================================
    # Setup
    # =========================================================================

    def _setup(self):

        if (
            self.config.reset_db
            and
            os.path.exists(
                self.config.db_path
            )
        ):
            os.remove(
                self.config.db_path
            )

        self.registry = (
            UniverseJobRegistry(
                db_path=self.config.db_path
            )
        )

        self.queue = (
            UniverseExecutionQueue(
                registry=self.registry,
                db_path=self.config.db_path,
            )
        )

        self.bulk = (
            AnalyticsBulkOperations(
                registry=self.registry,
                queue=self.queue,
            )
        )

    # =========================================================================
    # Timing
    # =========================================================================

    def _result(
        self,
        phase: str,
        count: int,
        elapsed: float,
    ) -> BulkStressResult:

        throughput = (
            count / elapsed
            if elapsed > 0
            else 0
        )

        return BulkStressResult(
            phase=phase,
            operation_count=count,
            elapsed_seconds=round(
                elapsed,
                4,
            ),
            throughput_per_second=round(
                throughput,
                2,
            ),
            generated_at=utc_now_iso(),
        )

    # =========================================================================
    # Individual Registration
    # =========================================================================

    def benchmark_individual_registration(
        self,
    ) -> BulkStressResult:

        start = time.perf_counter()

        for i in range(
            self.config.job_count
        ):

            self.registry.register_job(
                tenant_id=self.config.tenant_id,
                universe_id=self.config.universe_id,
                job_type="TEST",
                payload={
                    "i": i,
                },
            )

        elapsed = (
            time.perf_counter()
            - start
        )

        return self._result(
            "individual_registration",
            self.config.job_count,
            elapsed,
        )

    # =========================================================================
    # Bulk Registration
    # =========================================================================

    def benchmark_bulk_registration(
        self,
    ) -> BulkStressResult:

        jobs = []

        for i in range(
            self.config.job_count
        ):

            jobs.append(
                {
                    "job_type": "TEST",
                    "priority": "NORMAL",
                    "payload": {
                        "i": i,
                    },
                }
            )

        start = time.perf_counter()

        self.bulk.bulk_register_jobs(
            tenant_id=self.config.tenant_id,
            universe_id=self.config.universe_id,
            jobs=jobs,
        )

        elapsed = (
            time.perf_counter()
            - start
        )

        return self._result(
            "bulk_registration",
            self.config.job_count,
            elapsed,
        )

    # =========================================================================
    # Individual Queue
    # =========================================================================

    def benchmark_individual_enqueue(
        self,
    ) -> BulkStressResult:

        jobs = self.registry.list_jobs(
            tenant_id=self.config.tenant_id,
            limit=self.config.job_count,
        )

        start = time.perf_counter()

        for job in jobs:

            self.queue.enqueue_job(
                tenant_id=self.config.tenant_id,
                job_id=job.job_id,
                priority="NORMAL",
            )

        elapsed = (
            time.perf_counter()
            - start
        )

        return self._result(
            "individual_enqueue",
            len(jobs),
            elapsed,
        )

    # =========================================================================
    # Bulk Queue
    # =========================================================================

    def benchmark_bulk_enqueue(
        self,
    ) -> BulkStressResult:

        jobs = self.registry.list_jobs(
            tenant_id=self.config.tenant_id,
            limit=self.config.job_count,
        )

        payload = [
            (
                self.config.tenant_id,
                job.job_id,
                "NORMAL",
            )
            for job in jobs
        ]

        start = time.perf_counter()

        self.bulk.bulk_enqueue_jobs(
            tenant_id=self.config.tenant_id,
            job_ids=[
                j.job_id
                for j in jobs
            ],
        )

        elapsed = (
            time.perf_counter()
            - start
        )

        return self._result(
            "bulk_enqueue",
            len(jobs),
            elapsed,
        )

    # =========================================================================
    # Status Update
    # =========================================================================

    def benchmark_bulk_status_update(
        self,
    ) -> BulkStressResult:

        jobs = self.registry.list_jobs(
            tenant_id=self.config.tenant_id,
            limit=self.config.job_count,
        )

        start = time.perf_counter()

        self.bulk.bulk_update_status(
            tenant_id=self.config.tenant_id,
            job_ids=[
                j.job_id
                for j in jobs
            ],
            status="RUNNING",
        )

        elapsed = (
            time.perf_counter()
            - start
        )

        return self._result(
            "bulk_status_update",
            len(jobs),
            elapsed,
        )

    # =========================================================================
    # Complete
    # =========================================================================

    def benchmark_bulk_complete(
        self,
    ) -> BulkStressResult:

        jobs = self.registry.list_jobs(
            tenant_id=self.config.tenant_id,
            limit=self.config.job_count,
        )

        start = time.perf_counter()

        self.bulk.bulk_complete_jobs(
            tenant_id=self.config.tenant_id,
            job_ids=[
                j.job_id
                for j in jobs
            ],
        )

        elapsed = (
            time.perf_counter()
            - start
        )

        return self._result(
            "bulk_complete",
            len(jobs),
            elapsed,
        )

    # =========================================================================
    # Run
    # =========================================================================

    def run(
        self,
    ) -> Dict[str, Any]:

        self._setup()

        results: List[
            BulkStressResult
        ] = []

        if self.config.verbose:

            print()
            print(
                "=== ANALYTICS BULK STRESS SUITE ==="
            )
            print(
                f"Jobs: {self.config.job_count}"
            )
            print()

        individual = (
            self.benchmark_individual_registration()
        )

        results.append(
            individual
        )

        # Reset DB for clean comparison

        temp_db = (
            self.config.db_path
            + ".bulk"
        )

        if os.path.exists(
            temp_db
        ):
            os.remove(
                temp_db
            )

        self.registry = (
            UniverseJobRegistry(
                db_path=temp_db
            )
        )

        self.queue = (
            UniverseExecutionQueue(
                registry=self.registry,
                db_path=temp_db,
            )
        )

        self.bulk = (
            AnalyticsBulkOperations(
                registry=self.registry,
                queue=self.queue,
            )
        )

        bulk = (
            self.benchmark_bulk_registration()
        )

        results.append(
            bulk
        )

        enqueue = (
            self.benchmark_bulk_enqueue()
        )

        results.append(
            enqueue
        )

        status = (
            self.benchmark_bulk_status_update()
        )

        results.append(
            status
        )

        complete = (
            self.benchmark_bulk_complete()
        )

        results.append(
            complete
        )

        summary = {
            r.phase: asdict(r)
            for r in results
        }

        if (
            individual.throughput_per_second
            > 0
        ):
            summary[
                "registration_improvement"
            ] = round(
                (
                    bulk.throughput_per_second
                    /
                    individual.throughput_per_second
                ),
                2,
            )

        return summary


# =============================================================================
# Convenience
# =============================================================================

def run_bulk_stress_suite(
    job_count: int = 10000,
):

    suite = (
        AnalyticsBulkStressSuite(
            BulkStressConfig(
                job_count=job_count,
            )
        )
    )

    return suite.run()