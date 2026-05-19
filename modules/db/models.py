import uuid
from sqlalchemy import Column, String, DateTime
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

    id = Column(String, primary_key=True, default=gen_uuid)

    tenant_id = Column(String)

    email = Column(String)

    role = Column(String)

    created_at = Column(DateTime, default=datetime.utcnow)