import uuid
from sqlalchemy import Column, String, DateTime, Integer
from datetime import datetime

from modules.db.core import Base


def gen_uuid():
    return str(uuid.uuid4())


# ------------------------------------
# Tenant model
# ------------------------------------

class Tenant(Base):

    __tablename__ = "tenants"

    id = Column(String, primary_key=True, default=gen_uuid)

    name = Column(String)

    created_at = Column(DateTime, default=datetime.utcnow)


# ------------------------------------
# User model
# ------------------------------------

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, default="default_tenant")

    email = Column(String, nullable=False, unique=True)
    role = Column(String, nullable=False, default="client")

    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    # REQUIRED — your table already has this column
    password_hash = Column(String, nullable=True)

    # REQUIRED — your migrations add this
    is_active = Column(Integer, nullable=False, default=1)