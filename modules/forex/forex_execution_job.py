from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from datetime import datetime
import uuid


@dataclass
class ForexExecutionJob:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)

    status: str = "PENDING"
    retries: int = 0
    max_retries: int = 2

    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def mark_running(self):
        self.status = "RUNNING"
        self.updated_at = datetime.utcnow()

    def mark_complete(self, result: Dict[str, Any]):
        self.status = "COMPLETE"
        self.result = result
        self.updated_at = datetime.utcnow()

    def mark_failed(self, error: str):
        self.status = "FAILED"
        self.error = error
        self.updated_at = datetime.utcnow()

    def can_retry(self) -> bool:
        return self.retries < self.max_retries