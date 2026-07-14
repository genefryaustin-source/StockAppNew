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

    def enqueue_many(self, jobs) -> List[str]:
        """
        forex_scheduler.py's schedule_cycle() calls this with a plain list
        of job_id strings (from ForexJobRegistry.register_job() records) -
        this method never existed at all, so every scheduler cycle with
        enqueue=True (the default) raised AttributeError. submit() only
        takes a real ForexExecutionJob, so each id (or job dict/
        ForexExecutionJob passed directly - accept all three shapes) gets
        wrapped into one before queueing.
        """
        queued_ids: List[str] = []
        for entry in jobs or []:
            if isinstance(entry, ForexExecutionJob):
                job = entry
            elif isinstance(entry, dict):
                job = ForexExecutionJob(
                    id=str(entry.get("job_id") or entry.get("id") or ""),
                    action=str(entry.get("job_type") or entry.get("action") or ""),
                    payload=entry.get("payload") or {},
                )
            else:
                job = ForexExecutionJob(id=str(entry))
            self.submit(job)
            queued_ids.append(job.id)
        return queued_ids

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

                position = payload.get("position") or {}

                position_id = (

                        payload.get("position_id")

                        or position.get("id")

                )

                if not position_id:
                    raise ValueError(

                        "REVERSE_POSITION requires a position_id."

                    )

                result = executor.reverse_position(

                    position_id=position_id,

                    account_id=(

                            payload.get("account_id")

                            or position.get("account_id")

                    ),

                    leverage=(

                            payload.get("leverage")

                            or position.get("leverage")

                    ),

                    notes=payload.get(

                        "notes",

                        "Position reversed.",

                    ),

                )



            elif action == "FLATTEN":

                account_id = payload.get("account_id")

                if not account_id:

                    portfolio_id = payload.get("portfolio_id")

                    if portfolio_id:

                        account = executor.get_account(

                            portfolio_id=portfolio_id

                        )

                        if account:
                            account_id = account.id

                if not account_id:
                    raise ValueError(

                        "FLATTEN requires an account_id."

                    )

                result = executor.flatten_account(

                    account_id=account_id,

                    notes=payload.get(

                        "notes",

                        "Flatten account.",

                    ),

                )

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