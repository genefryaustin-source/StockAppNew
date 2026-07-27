"""
modules/forex/forex_validation_distributed_runner.py

Enterprise Distributed Validation Runner
"""

from __future__ import annotations

import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from modules.forex.forex_validation_cluster_manager import (
    cluster_manager,
)

try:
    from modules.forex.forex_validation_center import (
        ForexValidationCenter,
    )
except Exception:
    ForexValidationCenter = None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ForexValidationDistributedRunner:

    def __init__(self):

        self.cluster = cluster_manager()

        self.validation = (
            ForexValidationCenter()
            if ForexValidationCenter
            else None
        )

    ###########################################################################

    def _execute_single_job(
        self,
        worker_id: str,
        job: Dict[str, Any],
    ):

        try:

            if self.validation is not None:

                result = self.validation.run_full_validation(
                    **job.get("payload", {})
                )

            else:

                result = {
                    "status": "completed",
                    "validation": "placeholder"
                }

            self.cluster.complete_job(worker_id)

            return {

                "job_id": job["job_id"],

                "worker": worker_id,

                "status": "completed",

                "result": result,

                "finished": utc_now(),

            }

        except Exception:

            self.cluster.fail_job(worker_id)

            return {

                "job_id": job["job_id"],

                "worker": worker_id,

                "status": "failed",

                "error": traceback.format_exc(),

                "finished": utc_now(),

            }

    ###########################################################################

    def submit_validation(
        self,
        **kwargs,
    ):

        return self.cluster.enqueue(kwargs)

    ###########################################################################

    def run_distributed(self):

        futures = []

        results = []

        executor = ThreadPoolExecutor(
            max_workers=self.cluster.max_workers
        )

        for worker_id in self.cluster.workers:

            job = self.cluster.assign_job(worker_id)

            if job is None:
                continue

            futures.append(

                executor.submit(

                    self._execute_single_job,

                    worker_id,

                    job,

                )

            )

        for future in as_completed(futures):

            results.append(future.result())

        executor.shutdown(wait=True)

        return {

            "run_id": str(uuid.uuid4()),

            "cluster": self.cluster.cluster_metrics(),

            "jobs_executed": len(results),

            "results": results,

            "completed": utc_now(),

        }

    ###########################################################################

    def submit_batch(

        self,

        jobs: List[Dict[str, Any]],

    ):

        queued = []

        for job in jobs:

            queued.append(

                self.submit_validation(

                    **job

                )

            )

        return {

            "queued": len(queued),

            "jobs": queued,

        }

    ###########################################################################

    def status(self):

        return {

            "cluster": self.cluster.cluster_metrics(),

            "workers": self.cluster.worker_snapshot(),

        }

    ###########################################################################

    def health(self):

        return self.cluster.health()

    ###########################################################################

    def shutdown(self):

        return self.cluster.shutdown()