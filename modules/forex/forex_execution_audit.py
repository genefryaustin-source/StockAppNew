from typing import Dict, Any, List
from datetime import datetime


class ForexExecutionAudit:

    def __init__(self):
        self.records: List[Dict[str, Any]] = []

    def log(self, job_id: str, action: str, payload: Dict[str, Any], result: Any, status: str):
        self.records.append({
            "job_id": job_id,
            "action": action,
            "payload": payload,
            "result": result,
            "status": status,
            "timestamp": datetime.utcnow().isoformat()
        })

    def get_all(self):
        return self.records