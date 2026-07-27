"""
modules/forex/forex_validation_failover_manager.py

Enterprise Validation Failover Manager
"""

from __future__ import annotations

import copy
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from modules.forex.forex_validation_cluster_manager import (
    cluster_manager,
)

from modules.forex.forex_validation_distributed_runner import (
    ForexValidationDistributedRunner,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ForexValidationFailoverManager:
    """
    Supervises validation execution and automatically retries failed
    validation jobs on alternate workers.

    Designed to integrate with:

        ForexValidationClusterManager
        ForexValidationDistributedRunner
        ForexRuntimeController
        ForexOperationsCenter
    """

    def __init__(self):

        self.cluster = cluster_manager()

        self.runner = ForexValidationDistributedRunner()

        self.max_failover_attempts = 3

        self.failover_history: List[Dict[str, Any]] = []

    ######################################################################

    def run(self):

        """
        Execute queued validation jobs.

        Automatically retries failures.
        """

        initial = self.runner.run_distributed()

        recovered = self._recover_failed_jobs(initial)

        return {

            "status": "completed",

            "cluster": self.cluster.cluster_metrics(),

            "initial": initial,

            "recovery": recovered,

            "timestamp": utc_now(),

        }

    ######################################################################

    def _recover_failed_jobs(
        self,
        run_result: Dict[str, Any],
    ):

        recovered = []

        failed = [

            r

            for r in run_result.get("results", [])

            if r["status"] == "failed"

        ]

        for job in failed:

            recovered.append(

                self.retry_job(job)

            )

        return recovered

    ######################################################################

    def retry_job(
        self,
        failed_job: Dict[str, Any],
    ):

        attempts = 0

        last_error = None

        while attempts < self.max_failover_attempts:

            attempts += 1

            payload = copy.deepcopy(

                failed_job.get("result", {})

            )

            queued = self.runner.submit_validation(

                **payload

            )

            rerun = self.runner.run_distributed()

            completed = [

                r

                for r in rerun["results"]

                if r["status"] == "completed"

            ]

            if completed:

                recovery = {

                    "job_id":

                        failed_job["job_id"],

                    "status":

                        "recovered",

                    "attempt":

                        attempts,

                    "completed":

                        completed[0],

                    "timestamp":

                        utc_now(),

                }

                self.failover_history.append(recovery)

                return recovery

            last_error = rerun

        failure = {

            "job_id":

                failed_job["job_id"],

            "status":

                "failed",

            "attempts":

                attempts,

            "last_result":

                last_error,

            "timestamp":

                utc_now(),

        }

        self.failover_history.append(failure)

        return failure

    ######################################################################

    def health(self):

        metrics = self.cluster.cluster_metrics()

        failed = metrics["failed_jobs"]

        healthy = failed == 0

        return {

            "healthy": healthy,

            "cluster": metrics,

            "failovers":

                len(self.failover_history),

            "history":

                self.failover_history[-25:],

            "timestamp":

                utc_now(),

        }

    ######################################################################

    def statistics(self):

        recovered = len(

            [

                h

                for h in self.failover_history

                if h["status"] == "recovered"

            ]

        )

        failed = len(

            [

                h

                for h in self.failover_history

                if h["status"] == "failed"

            ]

        )

        return {

            "recoveries":

                recovered,

            "permanent_failures":

                failed,

            "history":

                len(self.failover_history),

            "cluster":

                self.cluster.cluster_metrics(),

        }

    ######################################################################

    def reset(self):

        self.failover_history.clear()

        return {

            "status": "reset",

            "timestamp": utc_now(),

        }

    ######################################################################

    def inject_failure(
        self,
        payload: Optional[Dict[str, Any]] = None,
    ):

        """
        Test helper for validation framework.
        """

        try:

            raise RuntimeError(

                "Synthetic validation failure."

            )

        except Exception:

            event = {

                "status": "synthetic_failure",

                "traceback": traceback.format_exc(),

                "payload": payload,

                "timestamp": utc_now(),

            }

            self.failover_history.append(event)

            return event


_FAILOVER: Optional[
    ForexValidationFailoverManager
] = None


def validation_failover_manager():

    global _FAILOVER

    if _FAILOVER is None:

        _FAILOVER = ForexValidationFailoverManager()

    return _FAILOVER
