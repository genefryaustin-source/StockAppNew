from datetime import datetime, UTC
from sqlalchemy import Column, String, Text, Integer
from modules.db.core import Base
from modules.db.models import gen_uuid


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, nullable=False, index=True)
    job_type = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, index=True)  # queued/running/succeeded/failed/cancelled/stopped

    universe_id = Column(String, nullable=True, index=True)
    symbol = Column(String, nullable=True, index=True)

    total = Column(Integer, nullable=True)
    done = Column(Integer, nullable=True)

    payload = Column(Text, nullable=True)
    logs = Column(Text, nullable=True)
    error = Column(Text, nullable=True)

    created_at = Column(String, default=lambda: datetime.now(UTC).isoformat())
    started_at = Column(String, nullable=True)
    finished_at = Column(String, nullable=True)