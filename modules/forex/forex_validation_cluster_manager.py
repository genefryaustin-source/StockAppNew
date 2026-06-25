"""
modules/forex/forex_validation_cluster_manager.py

Enterprise Validation Cluster Manager
"""

from __future__ import annotations

import os
import socket
import threading
import time
import uuid
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    import psutil
except Exception:
    psutil = None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ClusterWorker:

    worker_id: str
    hostname: str
    status: str = "idle"
    active_jobs: int = 0
    completed_jobs: int = 0
    failed_jobs: int = 0
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    last_heartbeat: str = ""

    def heartbeat(self):
        self.last_heartbeat = utc_now()

        if psutil:
            self.cpu_percent = psutil.cpu_percent(interval=None)
            self.memory_percent = psutil.virtual_memory().percent


class ForexValidationClusterManager:

    def __init__(self, max_workers: Optional[int] = None):

        self.cluster_id = str(uuid.uuid4())

        self.hostname = socket.gethostname()

        self.max_workers = (
            max_workers
            or max(2, min(32, (os.cpu_count() or 4)))
        )

        self.executor = ThreadPoolExecutor(
            max_workers=self.max_workers,
            thread_name_prefix="ForexValidation"
        )

        self.lock = threading.Lock()

        self.workers: Dict[str, ClusterWorker] = {}

        self.job_queue = deque()

        self.completed_jobs = 0

        self.failed_jobs = 0

        self.started = utc_now()

        self.running = True

        self._register_local_workers()

    ###########################################################################

    def _register_local_workers(self):

        for i in range(self.max_workers):

            wid = f"worker_{i+1:03d}"

            self.workers[wid] = ClusterWorker(
                worker_id=wid,
                hostname=self.hostname,
            )

    ###########################################################################

    def register_worker(self, worker_id: str):

        with self.lock:

            if worker_id not in self.workers:

                self.workers[worker_id] = ClusterWorker(
                    worker_id=worker_id,
                    hostname=self.hostname,
                )

        return self.workers[worker_id]

    ###########################################################################

    def enqueue(self, payload: Dict[str, Any]):

        job = {
            "job_id": str(uuid.uuid4()),
            "submitted": utc_now(),
            "payload": payload,
            "status": "queued",
        }

        with self.lock:
            self.job_queue.append(job)

        return job

    ###########################################################################

    def next_job(self):

        with self.lock:

            if not self.job_queue:
                return None

            return self.job_queue.popleft()

    ###########################################################################

    def assign_job(self, worker_id: str):

        worker = self.workers[worker_id]

        job = self.next_job()

        if job is None:
            return None

        worker.status = "running"

        worker.active_jobs += 1

        worker.heartbeat()

        return job

    ###########################################################################

    def complete_job(self, worker_id: str):

        worker = self.workers[worker_id]

        worker.active_jobs = max(0, worker.active_jobs - 1)

        worker.completed_jobs += 1

        worker.status = "idle"

        worker.heartbeat()

        self.completed_jobs += 1

    ###########################################################################

    def fail_job(self, worker_id: str):

        worker = self.workers[worker_id]

        worker.active_jobs = max(0, worker.active_jobs - 1)

        worker.failed_jobs += 1

        worker.status = "idle"

        worker.heartbeat()

        self.failed_jobs += 1

    ###########################################################################

    def worker_snapshot(self):

        return [
            asdict(worker)
            for worker in self.workers.values()
        ]

    ###########################################################################

    def cluster_metrics(self):

        queued = len(self.job_queue)

        active = sum(
            w.active_jobs
            for w in self.workers.values()
        )

        idle = sum(
            1
            for w in self.workers.values()
            if w.status == "idle"
        )

        return {

            "cluster_id": self.cluster_id,

            "hostname": self.hostname,

            "workers":

                len(self.workers),

            "idle_workers":

                idle,

            "active_jobs":

                active,

            "queued_jobs":

                queued,

            "completed_jobs":

                self.completed_jobs,

            "failed_jobs":

                self.failed_jobs,

            "uptime":

                self.started,

            "timestamp":

                utc_now(),
        }

    ###########################################################################

    def heartbeat(self):

        for worker in self.workers.values():
            worker.heartbeat()

        return self.cluster_metrics()

    ###########################################################################

    def health(self):

        metrics = self.cluster_metrics()

        healthy = (
            metrics["failed_jobs"] == 0
        )

        return {

            "healthy": healthy,

            "cluster": metrics,

            "workers": self.worker_snapshot(),

        }

    ###########################################################################

    def shutdown(self):

        self.running = False

        self.executor.shutdown(wait=False)

        return {

            "status": "shutdown",

            "timestamp": utc_now(),

        }


_CLUSTER: Optional[ForexValidationClusterManager] = None


def cluster_manager() -> ForexValidationClusterManager:

    global _CLUSTER

    if _CLUSTER is None:
        _CLUSTER = ForexValidationClusterManager()

    return _CLUSTER