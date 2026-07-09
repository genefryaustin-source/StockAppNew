from typing import Dict, Any, List
from collections import deque
import logging

from modules.forex.forex_execution_job import ForexExecutionJob

logger = logging.getLogger(__name__)


class ForexExecutionQueue:

    def __init__(self):
        self.queue = deque()
        self.active_jobs: Dict[str, ForexExecutionJob] = {}

    def submit(self, job: ForexExecutionJob):
        self.queue.append(job)
        self.active_jobs[job.id] = job
        logger.info(f"Queued execution job {job.id} | {job.action}")

    def process_next(self, executor):
        if not self.queue:
            return None

        job = self.queue.popleft()
        job.mark_running()

        try:
            action = str(job.action or "").upper().strip()

            payload = job.payload or {}

            print("=" * 80)
            print("FOREX EXECUTION JOB")
            print("job_id :", job.id)
            print("action :", action)
            print("payload:", payload)
            print("=" * 80)

            # ==========================================================
            # ROUTING LAYER (SAFE DISPATCH)
            # ==========================================================

            if action == "CLOSE_POSITION":
                result = executor.close_position(**payload)

            elif action == "REVERSE_POSITION":
                result = executor.reverse_position(**payload)

            elif action == "FLATTEN":
                result = executor.flatten_account(**payload)

            elif action == "OPEN_POSITION":
                result = executor.open_position(**payload)

            else:
                raise ValueError(f"Unknown execution action: {action}")

            job.mark_complete(result)

            print("=" * 80)
            print("JOB COMPLETE")
            print(result)
            print("=" * 80)

            return result

        except Exception as e:
            job.retries += 1
            job.mark_failed(str(e))

            print("=" * 80)
            print("JOB FAILED")
            print(str(e))
            print("=" * 80)

            if job.can_retry():
                logger.warning(f"Retrying job {job.id}")
                self.queue.append(job)

            return None

    def status(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": j.id,
                "action": j.action,
                "status": j.status,
                "retries": j.retries,
            }
            for j in self.active_jobs.values()
        ]