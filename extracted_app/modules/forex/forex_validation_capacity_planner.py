"""
modules/forex/forex_validation_capacity_planner.py

Enterprise Validation Capacity Planner
"""

from __future__ import annotations

import math
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    import psutil
except Exception:
    psutil = None

from modules.forex.forex_validation_cluster_manager import (
    cluster_manager,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ForexValidationCapacityPlanner:
    """
    Estimates validation cluster capacity and recommends scaling.

    Integrates with:

        ForexValidationClusterManager
        ForexValidationDistributedRunner
        ForexValidationRuntimeController
        ForexValidationScheduler
    """

    def __init__(self):

        self.cluster = cluster_manager()

    ######################################################################

    def current_capacity(self):

        metrics = self.cluster.cluster_metrics()

        workers = metrics["workers"]

        queued = metrics["queued_jobs"]

        active = metrics["active_jobs"]

        idle = metrics["idle_workers"]

        utilization = 0.0

        if workers > 0:
            utilization = active / workers

        return {

            "workers": workers,

            "idle_workers": idle,

            "active_jobs": active,

            "queued_jobs": queued,

            "utilization": round(utilization * 100, 2),

            "timestamp": utc_now(),

        }

    ######################################################################

    def recommend_workers(
        self,
        queued_jobs: Optional[int] = None,
    ):

        if queued_jobs is None:

            queued_jobs = self.cluster.cluster_metrics()["queued_jobs"]

        cpu = os.cpu_count() or 4

        recommended = max(

            cpu,

            math.ceil(queued_jobs / 4),

        )

        recommended = min(

            64,

            recommended,

        )

        return recommended

    ######################################################################

    def estimate_completion_time(
        self,
        average_job_seconds: float = 2.0,
    ):

        metrics = self.cluster.cluster_metrics()

        queued = metrics["queued_jobs"]

        workers = max(metrics["workers"], 1)

        total = queued * average_job_seconds

        completion = total / workers

        return {

            "estimated_seconds":

                round(completion, 2),

            "estimated_minutes":

                round(completion / 60.0, 2),

        }

    ######################################################################

    def host_resources(self):

        if psutil is None:

            return {

                "cpu_percent": None,

                "memory_percent": None,

                "available_memory_gb": None,

            }

        memory = psutil.virtual_memory()

        return {

            "cpu_percent":

                psutil.cpu_percent(interval=None),

            "memory_percent":

                memory.percent,

            "available_memory_gb":

                round(memory.available / 1024 ** 3, 2),

        }

    ######################################################################

    def scaling_recommendation(self):

        metrics = self.current_capacity()

        resources = self.host_resources()

        recommendation = "No Scaling Required"

        if metrics["queued_jobs"] > metrics["workers"] * 3:

            recommendation = "Scale Out"

        elif metrics["utilization"] > 90:

            recommendation = "Scale Out"

        elif metrics["utilization"] < 20:

            recommendation = "Scale In"

        return {

            "recommendation":

                recommendation,

            "recommended_workers":

                self.recommend_workers(

                    metrics["queued_jobs"]

                ),

            "capacity":

                metrics,

            "resources":

                resources,

            "estimated_completion":

                self.estimate_completion_time(),

            "timestamp":

                utc_now(),

        }

    ######################################################################

    def analyze(self):

        return {

            "status": "completed",

            "capacity":

                self.current_capacity(),

            "resources":

                self.host_resources(),

            "scaling":

                self.scaling_recommendation(),

            "cluster":

                self.cluster.health(),

        }

    ######################################################################

    def workload_projection(

        self,

        projected_jobs: List[int],

    ):

        projections = []

        for jobs in projected_jobs:

            workers = self.recommend_workers(jobs)

            projections.append({

                "jobs": jobs,

                "recommended_workers": workers,

                "estimated_completion":

                    round(

                        (jobs * 2.0) / workers,

                        2,

                    ),

            })

        return {

            "generated": utc_now(),

            "projection": projections,

        }

    ######################################################################

    def optimize_cluster(self):

        recommendation = self.scaling_recommendation()

        return {

            "status": "optimization_complete",

            "recommendation": recommendation,

            "timestamp": utc_now(),

        }


_CAPACITY: Optional[
    ForexValidationCapacityPlanner
] = None


def validation_capacity_planner():

    global _CAPACITY

    if _CAPACITY is None:

        _CAPACITY = ForexValidationCapacityPlanner()

    return _CAPACITY