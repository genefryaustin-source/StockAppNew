
import json
from uuid import UUID
from .execution_models import ExecutionEvent
class ExecutionValidationError(Exception): ...
class ExecutionEventValidator:
    def validate(self,event:ExecutionEvent):
        UUID(event.event_id)
        if event.occurred_at.tzinfo is None:
            raise ExecutionValidationError("UTC timestamp required")
        json.dumps(event.payload,default=str)
        json.dumps(event.metadata,default=str)
        return True
