import uuid
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    Text,
    Boolean,
    UniqueConstraint,
)
from datetime import datetime, UTC

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

    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Super-admin override of the platform API key grace period (see
    # modules/admin/tenant_api_keys.py). If api_grace_unlimited is True,
    # the grace period never expires for this tenant regardless of how
    # old it is. Otherwise, api_grace_days_override (if set) replaces the
    # global PLATFORM_KEY_GRACE_PERIOD_DAYS default for this tenant only.
    #
    # server_default (not just default=) is required here: app.py's
    # bootstrap inserts tenants via raw SQL that doesn't name every
    # column, and a Python-side default= only applies through the ORM --
    # raw SQL needs the database itself to supply the default.
    api_grace_unlimited = Column(Boolean, nullable=False, default=False, server_default="0")
    api_grace_days_override = Column(Integer, nullable=True)



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
    is_active = Column(Boolean, nullable=False, default=True)


# ------------------------------------
# TenantApiKey model
#
# Lets each tenant bring their own provider API keys (market data, AI,
# etc.) instead of sharing the platform's single Streamlit Cloud secret.
# Values are stored encrypted (see modules/admin/tenant_api_keys.py) --
# never store a raw key in this column.
# ------------------------------------

class TenantApiKey(Base):
    __tablename__ = "tenant_api_keys"
    __table_args__ = (
        UniqueConstraint("tenant_id", "provider", name="uq_tenant_provider_key"),
    )

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, nullable=False, index=True)

    # The secret name this overrides, e.g. "ANTHROPIC_API_KEY", "POLYGON_API_KEY".
    provider = Column(String, nullable=False)

    # Fernet-encrypted ciphertext, never the raw key.
    encrypted_value = Column(Text, nullable=False)

    # Last 4 characters of the real key, kept in plaintext only so the UI
    # can show "...a1B2" for confirmation without ever redisplaying the
    # full secret.
    key_suffix = Column(String(8), nullable=True)

    is_active = Column(Boolean, nullable=False, default=True)

    created_by_user_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

class TenantBrokerSetting(Base):
    """
    Which execution/broker providers (paper, alpaca, tradier, ibkr, ...) a
    tenant is allowed to pick in the Trading & Execution broker dropdown.

    No row for a given (tenant_id, broker_name) means "not explicitly set" --
    callers should treat that as enabled for "paper" (always available) and
    disabled for every real broker until a tenant/super admin turns it on,
    so a tenant doesn't see broker options they never asked for.
    """
    __tablename__ = "tenant_broker_settings"
    __table_args__ = (
        UniqueConstraint("tenant_id", "broker_name", name="uq_tenant_broker_setting"),
    )

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, nullable=False, index=True)

    broker_name = Column(String, nullable=False)
    enabled = Column(Boolean, nullable=False, default=False)

    updated_by_user_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


class TenantRiskLimit(Base):
    """
    Per-tenant Internal Risk Layer limits (modules/risk_layer). No row for
    a given (tenant_id, limit_name) means "use the built-in default" -- see
    modules.risk_layer.limits.DEFAULT_LIMITS for the fallback values and
    what each limit_name means.
    """
    __tablename__ = "tenant_risk_limits"
    __table_args__ = (
        UniqueConstraint("tenant_id", "limit_name", name="uq_tenant_risk_limit"),
    )

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, nullable=False, index=True)

    limit_name = Column(String, nullable=False)
    limit_value = Column(Float, nullable=False)

    updated_by_user_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


class TenantRiskProviderSetting(Base):
    """
    Which external risk-analytics vendors (modules/risk_providers) a
    tenant has enabled, plus any provider-specific config (e.g. the
    Custom Risk Provider's field-mapping JSON). Mirrors
    TenantBrokerSetting -- no row means "not enabled," so a tenant only
    sees vendor output in the Risk Layer once a tenant/super admin turns
    one on and its credentials are set under Admin > API Keys.
    """
    __tablename__ = "tenant_risk_provider_settings"
    __table_args__ = (
        UniqueConstraint("tenant_id", "provider_name", name="uq_tenant_risk_provider_setting"),
    )

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, nullable=False, index=True)

    # Matches a key in modules.risk_providers.registry.RISK_PROVIDER_REGISTRY,
    # e.g. "portfolioscience", "factset", "custom".
    provider_name = Column(String, nullable=False)

    enabled = Column(Boolean, nullable=False, default=False)
    config_json = Column(Text, nullable=True)

    updated_by_user_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
