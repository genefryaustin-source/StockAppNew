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

    # Gate on whether this tenant can use the external platform API
    # (api.auth.api_keys.PlatformAPIKey) at all -- creating a key,
    # AND authenticating with an existing one, both check this.
    # Defaults OFF: a newly created tenant has no external API access
    # until a super admin explicitly turns it on, so plugging in a new
    # tenant never accidentally grants free API access. Only a super
    # admin can change this -- see modules.admin.tenant_service.
    #
    # server_default (not just default=) for the same reason as
    # api_grace_unlimited above: app.py's bootstrap inserts tenants via
    # raw SQL that doesn't name every column, and a Python-side default=
    # only applies through the ORM.
    platform_api_access_enabled = Column(Boolean, nullable=False, default=False, server_default="0")

    # Module (asset-class) entitlements, surfaced in the login response
    # for mobile/API clients (api/routers/auth.py) and enforced again
    # server-side on every request that touches that asset class (e.g.
    # api.services.executive_mobile_dashboard_api_service) -- a client
    # hint is not the security boundary, this is.
    #
    # stocks/options/forex default enabled: these have been working,
    # ungated features throughout this app's history, and this is the
    # first time any licensing gate has existed for them -- defaulting
    # to disabled would silently take working functionality away from
    # every existing tenant the moment this column exists. crypto
    # defaults disabled because there is no trading capability behind
    # it yet at all (see modules/crypto/ -- market data only); this
    # reflects that reality, not a separate licensing choice.
    module_stocks_enabled = Column(Boolean, nullable=False, default=True, server_default="1")
    module_options_enabled = Column(Boolean, nullable=False, default=True, server_default="1")
    module_forex_enabled = Column(Boolean, nullable=False, default=True, server_default="1")
    module_crypto_enabled = Column(Boolean, nullable=False, default=False, server_default="0")



# ------------------------------------
# User model
# ------------------------------------

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, default="default_tenant")

    email = Column(String, nullable=False, unique=True)
    role = Column(String, nullable=False, default="client")

    # Display name for API/mobile responses (api/routers/auth.py's
    # login response). Nullable -- an account created before this
    # column existed, or one that never had a name set, falls back to
    # deriving something from the email locally rather than storing a
    # fabricated value here.
    name = Column(String, nullable=True)

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


# ------------------------------------
# PlatformAPIKey model
#
# Not to be confused with TenantApiKey above: that table stores each
# tenant's own third-party provider credentials (Polygon, Anthropic,
# etc.) that this app uses to call OUT to external services. This one
# is the opposite direction -- keys that external systems present to
# call IN to this app's own REST API (api/routers/).
#
# The raw key is never stored, not even encrypted -- only a SHA-256
# hash of it. Unlike TenantApiKey's provider credentials, which this
# app needs to decrypt and actually use, an API key only ever needs to
# be compared against what a caller presents, so a one-way hash is the
# correct (and simpler, unrecoverable-by-design) choice. High-entropy
# random tokens like these don't need a slow password-hashing KDF the
# way a human-chosen password would.
# ------------------------------------

class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    # The JWT's own jti claim (api.auth.models.JWTClaims.jti) -- not a
    # separately-generated id, since the whole point is to look this
    # table up by the jti embedded in a presented token.
    jti = Column(String, primary_key=True)

    tenant_id = Column(String, nullable=True, index=True)
    user_id = Column(String, nullable=True, index=True)

    revoked_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))

    # Mirrors the original token's own exp -- once real time passes this,
    # the token is already rejected by JWT expiry validation regardless
    # of whether a revocation row exists, so entries past this point are
    # safe to delete rather than keeping this table growing forever.
    expires_at = Column(DateTime, nullable=False, index=True)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    # Opaque, randomly-generated token (not a JWT) -- only its SHA-256
    # hash is stored, the same pattern PlatformAPIKey below uses for
    # its own secret material, so a database compromise doesn't hand
    # over usable refresh tokens directly.
    token_hash = Column(String, primary_key=True)

    tenant_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)

    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    expires_at = Column(DateTime, nullable=False, index=True)

    # Set the moment this token is used to issue a new access token
    # (rotation) or is explicitly logged out -- checked instead of
    # deleting the row outright, so a reused, already-rotated-away
    # token can be distinguished from one that never existed, which is
    # itself a signal worth logging (a legitimate refresh token should
    # only ever be presented once).
    revoked_at = Column(DateTime, nullable=True)

    # The token this one replaced, if issued via rotation -- not
    # currently read anywhere, kept only as an audit trail for tracing
    # a rotation chain by hand if a theft investigation ever needs it.
    replaced_token_hash = Column(String, nullable=True)


class UserPreferences(Base):
    __tablename__ = "user_preferences"

    user_id = Column(String, primary_key=True)

    theme = Column(String, nullable=False, default="dark", server_default="dark")
    default_workspace = Column(String, nullable=False, default="dashboard", server_default="dashboard")
    notifications_enabled = Column(Boolean, nullable=False, default=True, server_default="1")

    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))


class PlatformAPIKey(Base):
    __tablename__ = "platform_api_keys"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, nullable=False, index=True)

    name = Column(String, nullable=False)

    key_prefix = Column(String(16), nullable=False)
    key_hash = Column(String(64), nullable=False, unique=True, index=True)
    key_suffix = Column(String(8), nullable=True)

    # JSON-encoded list of permission strings from api.auth.permissions.PERMISSIONS.
    permissions = Column(Text, nullable=False, default="[]")

    rate_limit_per_minute = Column(Integer, nullable=False, default=100)

    is_active = Column(Boolean, nullable=False, default=True)

    created_by_user_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    last_used_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)


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