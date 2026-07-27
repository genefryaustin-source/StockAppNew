"""
modules/analytics/analytics_bulk_operations.py

Analytics Bulk Operations Engine

Purpose
-------
High-throughput batch execution layer for Analytics Fabric.

This module eliminates the primary performance bottleneck discovered
during profiling:

    1000 jobs
        ->
    1000 SQLite transactions

and replaces it with:

    1000 jobs
        ->
    1 SQLite transaction

Design Goals
------------

* Bulk job registration
* Bulk queue insertion
* Bulk status transitions
* Bulk completion
* Bulk failure handling
* Bulk lease recovery
* Batch event creation
* Tenant isolation
* Deterministic execution

Expected Improvement
--------------------

Typical:

    50-150 ops/sec

becomes:

    1000-10000+ ops/sec

depending on hardware.

"""

from __future__ import annotations

import uuid

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional


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
class BulkOperationResult:

    operation: str

    requested: int

    processed: int

    failed: int

    generated_at: str


# =============================================================================
# Engine
# =============================================================================

class AnalyticsBulkOperations:

    """
    High-performance batch operations.

    Uses direct registry/queue connections
    to execute large workloads in a
    single transaction.
    """

    def __init__(
        self,
        *,
        registry,
        queue,
    ):

        self.registry = registry

        self.queue = queue

    # =========================================================================
    # Bulk Register
    # =========================================================================

    def bulk_register_jobs(
        self,
        *,
        tenant_id: str,
        universe_id: str,
        jobs: Iterable[Dict[str, Any]],
    ) -> BulkOperationResult:

        jobs = list(jobs)

        if not jobs:

            return BulkOperationResult(
                operation="bulk_register_jobs",
                requested=0,
                processed=0,
                failed=0,
                generated_at=utc_now_iso(),
            )

        now = utc_now_iso()

        rows = []

        events = []

        for job in jobs:

            job_id = (
                job.get("job_id")
                or
                f"JOB_{uuid.uuid4().hex}"
            )

            rows.append(
                (
                    job_id,
                    tenant_id,
                    universe_id,
                    job.get(
                        "job_type",
                        "CUSTOM",
                    ),
                    "REGISTERED",
                    job.get(
                        "priority",
                        "NORMAL",
                    ),
                    "{}",
                    now,
                    now,
                )
            )

            events.append(
                (
                    f"EVT_{uuid.uuid4().hex}",
                    job_id,
                    tenant_id,
                    "JOB_REGISTERED",
                    "Bulk registered",
                    "{}",
                    now,
                )
            )

        with self.registry._connect() as conn:

            conn.executemany(
                """
                INSERT INTO universe_jobs
                (
                    job_id,
                    tenant_id,
                    universe_id,
                    job_type,
                    status,
                    priority,
                    payload_json,
                    created_at,
                    updated_at
                )
                VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

            conn.executemany(
                self.registry._insert_event_sql(),
                events,
            )

        return BulkOperationResult(
            operation="bulk_register_jobs",
            requested=len(jobs),
            processed=len(jobs),
            failed=0,
            generated_at=utc_now_iso(),
        )

    # =========================================================================
    # Bulk Queue
    # =========================================================================

    def bulk_enqueue_jobs(
        self,
        *,
        tenant_id: str,
        job_ids: Iterable[str],
        priority_rank: int = 3,
    ) -> BulkOperationResult:

        job_ids = list(job_ids)

        now = utc_now_iso()

        queue_rows = []

        for job_id in job_ids:

            queue_rows.append(
                (
                    f"Q_{uuid.uuid4().hex}",
                    tenant_id,
                    job_id,
                    priority_rank,
                    now,
                    now,
                    0,
                )
            )

        with self.queue._connect() as conn:

            conn.executemany(
                """
                INSERT INTO universe_execution_queue
                (
                    queue_id,
                    tenant_id,
                    job_id,
                    priority_rank,
                    queued_at,
                    available_at,
                    claimed
                )
                VALUES
                (?, ?, ?, ?, ?, ?, ?)
                """,
                queue_rows,
            )

        self.registry.update_status_bulk(
            tenant_id=tenant_id,
            job_ids=job_ids,
            status="QUEUED",
            event_type="JOB_QUEUED",
            message="Bulk queued",
        )

        return BulkOperationResult(
            operation="bulk_enqueue_jobs",
            requested=len(job_ids),
            processed=len(job_ids),
            failed=0,
            generated_at=utc_now_iso(),
        )

    # =========================================================================
    # Bulk Status Update
    # =========================================================================

    def bulk_update_status(
        self,
        *,
        tenant_id: str,
        job_ids: Iterable[str],
        status: str,
    ) -> BulkOperationResult:

        updated = (
            self.registry.update_status_bulk(
                tenant_id=tenant_id,
                job_ids=job_ids,
                status=status,
                event_type="BULK_STATUS_UPDATE",
                message=f"Bulk status -> {status}",
            )
        )

        return BulkOperationResult(
            operation="bulk_update_status",
            requested=len(list(job_ids)),
            processed=updated,
            failed=0,
            generated_at=utc_now_iso(),
        )

    # =========================================================================
    # Bulk Complete
    # =========================================================================

    def bulk_complete_jobs(
        self,
        *,
        tenant_id: str,
        job_ids: Iterable[str],
    ) -> BulkOperationResult:

        job_ids = list(job_ids)

        now = utc_now_iso()

        updated = []

        with self.registry._connect() as conn:

            for job_id in job_ids:

                cursor = conn.execute(
                    """
                    UPDATE universe_jobs
                    SET
                        status = 'COMPLETED',
                        completed_at = ?,
                        updated_at = ?
                    WHERE
                        tenant_id = ?
                        AND job_id = ?
                    """,
                    (
                        now,
                        now,
                        tenant_id,
                        job_id,
                    ),
                )

                if cursor.rowcount > 0:

                    updated.append(
                        job_id
                    )

            conn.executemany(
                self.registry._insert_event_sql(),
                [
                    (
                        f"EVT_{uuid.uuid4().hex}",
                        job_id,
                        tenant_id,
                        "JOB_COMPLETED",
                        "Bulk completed",
                        "{}",
                        now,
                    )
                    for job_id
                    in updated
                ],
            )

        return BulkOperationResult(
            operation="bulk_complete_jobs",
            requested=len(job_ids),
            processed=len(updated),
            failed=(
                len(job_ids)
                - len(updated)
            ),
            generated_at=utc_now_iso(),
        )

    # =========================================================================
    # Bulk Fail
    # =========================================================================

    def bulk_fail_jobs(
        self,
        *,
        tenant_id: str,
        job_ids: Iterable[str],
        reason: str,
    ) -> BulkOperationResult:

        job_ids = list(job_ids)

        now = utc_now_iso()

        updated = []

        with self.registry._connect() as conn:

            for job_id in job_ids:

                cursor = conn.execute(
                    """
                    UPDATE universe_jobs
                    SET
                        status = 'FAILED',
                        error_message = ?,
                        updated_at = ?
                    WHERE
                        tenant_id = ?
                        AND job_id = ?
                    """,
                    (
                        reason,
                        now,
                        tenant_id,
                        job_id,
                    ),
                )

                if cursor.rowcount > 0:

                    updated.append(
                        job_id
                    )

            conn.executemany(
                self.registry._insert_event_sql(),
                [
                    (
                        f"EVT_{uuid.uuid4().hex}",
                        job_id,
                        tenant_id,
                        "JOB_FAILED",
                        reason,
                        "{}",
                        now,
                    )
                    for job_id
                    in updated
                ],
            )

        return BulkOperationResult(
            operation="bulk_fail_jobs",
            requested=len(job_ids),
            processed=len(updated),
            failed=(
                len(job_ids)
                - len(updated)
            ),
            generated_at=utc_now_iso(),
        )

    # =========================================================================
    # Bulk Lease Recovery
    # =========================================================================

    def bulk_recover_expired_leases(
        self,
    ) -> BulkOperationResult:

        recovered = (
            self.queue.recover_expired_leases()
        )

        return BulkOperationResult(
            operation="bulk_recover_expired_leases",
            requested=recovered,
            processed=recovered,
            failed=0,
            generated_at=utc_now_iso(),
        )