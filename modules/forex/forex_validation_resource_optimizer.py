"""
modules/forex/forex_validation_resource_optimizer.py

Enterprise Forex Validation Resource Optimizer
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    import psutil
except Exception:
    psutil = None

from modules.forex.forex_validation_cluster_manager import cluster_manager
from modules.forex.forex_validation_capacity_planner import (
    ForexValidationCapacityPlanner,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ForexValidationResourceOptimizer:
    """
    Optimizes cluster resource utilization for validation workloads.

    Integrates with:
        - ForexValidationClusterManager
        - ForexValidationCapacityPlanner
        - ForexValidationDistributedRunner
        - ForexValidationRuntimeController
    """

    CPU_HIGH = 85.0
    CPU_LOW = 25.0

    MEMORY_HIGH = 85.0
    MEMORY_LOW = 30.0

    UTIL_HIGH = 90.0
    UTIL_LOW = 20.0

    def __init__(self):

        self.cluster = cluster_manager()

        self.capacity = ForexValidationCapacityPlanner()

    ######################################################################

    def host_resources(self) -> Dict[str, Any]:

        if psutil is None:

            return {
                "cpu_percent": None,
                "memory_percent": None,
                "available_memory_gb": None,
                "logical_cpus": os.cpu_count() or 1,
            }

        memory = psutil.virtual_memory()

        return {

            "cpu_percent":
                psutil.cpu_percent(interval=None),

            "memory_percent":
                memory.percent,

            "available_memory_gb":
                round(memory.available / 1024 ** 3, 2),

            "used_memory_gb":
                round(memory.used / 1024 ** 3, 2),

            "total_memory_gb":
                round(memory.total / 1024 ** 3, 2),

            "logical_cpus":
                psutil.cpu_count(),

            "physical_cpus":
                psutil.cpu_count(logical=False),

        }

    ######################################################################

    def analyze(self) -> Dict[str, Any]:

        capacity = self.capacity.current_capacity()

        resources = self.host_resources()

        recommendations: List[str] = []

        cpu = resources.get("cpu_percent")
        mem = resources.get("memory_percent")

        util = capacity.get("utilization", 0)

        if cpu is not None:

            if cpu > self.CPU_HIGH:

                recommendations.append(
                    "CPU utilization is high. Increase worker count or reduce concurrency."
                )

            elif cpu < self.CPU_LOW:

                recommendations.append(
                    "CPU utilization is low. Validation workers may be over-provisioned."
                )

        if mem is not None:

            if mem > self.MEMORY_HIGH:

                recommendations.append(
                    "Memory utilization is high. Reduce batch sizes or worker count."
                )

            elif mem < self.MEMORY_LOW:

                recommendations.append(
                    "Memory utilization is low. Additional workers can be allocated."
                )

        if util > self.UTIL_HIGH:

            recommendations.append(
                "Cluster utilization exceeds target. Scale out validation workers."
            )

        elif util < self.UTIL_LOW:

            recommendations.append(
                "Cluster utilization is low. Scale in to reduce resource consumption."
            )

        if not recommendations:

            recommendations.append(
                "Current resource allocation is within optimal operating range."
            )

        return {

            "status": "completed",

            "cluster_capacity":
                capacity,

            "host_resources":
                resources,

            "recommendations":
                recommendations,

            "timestamp":
                utc_now(),

        }

    ######################################################################

    def recommend_worker_count(self) -> Dict[str, Any]:

        metrics = self.cluster.cluster_metrics()

        recommended = self.capacity.recommend_workers(
            metrics["queued_jobs"]
        )

        delta = recommended - metrics["workers"]

        return {

            "current_workers":
                metrics["workers"],

            "recommended_workers":
                recommended,

            "worker_delta":
                delta,

            "action":
                (
                    "scale_out"
                    if delta > 0
                    else "scale_in"
                    if delta < 0
                    else "no_change"
                ),

            "timestamp":
                utc_now(),

        }

    ######################################################################

    def optimize(self) -> Dict[str, Any]:

        analysis = self.analyze()

        worker_plan = self.recommend_worker_count()

        optimization_actions = []

        if worker_plan["action"] == "scale_out":

            optimization_actions.append(
                f"Increase validation workers to {worker_plan['recommended_workers']}."
            )

        elif worker_plan["action"] == "scale_in":

            optimization_actions.append(
                f"Reduce validation workers to {worker_plan['recommended_workers']}."
            )

        else:

            optimization_actions.append(
                "No worker scaling required."
            )

        optimization_actions.extend(
            analysis["recommendations"]
        )

        return {

            "status": "optimization_complete",

            "analysis":
                analysis,

            "worker_plan":
                worker_plan,

            "actions":
                optimization_actions,

            "completed_at":
                utc_now(),

        }

    ######################################################################

    def benchmark_projection(
        self,
        projected_jobs: List[int],
    ) -> Dict[str, Any]:

        projection = self.capacity.workload_projection(
            projected_jobs
        )

        optimized = []

        for row in projection["projection"]:

            optimized.append({

                "projected_jobs":
                    row["jobs"],

                "recommended_workers":
                    row["recommended_workers"],

                "estimated_completion_seconds":
                    row["estimated_completion"],

                "estimated_throughput_jobs_per_minute":
                    round(
                        (
                            row["jobs"]
                            /
                            max(
                                row["estimated_completion"] / 60.0,
                                0.01,
                            )
                        ),
                        2,
                    ),

            })

        return {

            "status": "completed",

            "projection":
                optimized,

            "generated_at":
                utc_now(),

        }


_RESOURCE_OPTIMIZER: Optional[
    ForexValidationResourceOptimizer
] = None


def validation_resource_optimizer() -> ForexValidationResourceOptimizer:

    global _RESOURCE_OPTIMIZER

    if _RESOURCE_OPTIMIZER is None:

        _RESOURCE_OPTIMIZER = ForexValidationResourceOptimizer()

    return _RESOURCE_OPTIMIZER