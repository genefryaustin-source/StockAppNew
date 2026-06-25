"""
modules/admin/tenant_api_keys.py

Per-tenant API key management.

Streamlit Cloud's "Secrets" settings panel produces ONE st.secrets object
for the whole deployment -- there's no native way to give different
tenants different provider keys there. Instead, tenant-specific keys live
encrypted in the database (TenantApiKey), and the one thing that still
needs to be in Streamlit's secrets UI is a single master encryption key:

    APP_ENCRYPTION_KEY = "<a Fernet key -- see generate_encryption_key()>"

Resolution order for any given provider + tenant:
    1. The tenant's own key, if they've set one (decrypted from the DB).
    2. The platform-wide key in st.secrets / the environment (the
       existing shared key, used as a fallback so tenants aren't blocked
       before they configure their own).

Usage at call sites (drop-in replacement for the old pattern):

    # before:
    key = st.secrets.get("ANTHROPIC_API_KEY", "") or os.getenv("ANTHROPIC_API_KEY", "")

    # after:
    from modules.admin.tenant_api_keys import get_provider_key
    key = get_provider_key("ANTHROPIC_API_KEY")
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, UTC
from typing import Optional

import streamlit as st

from modules.db.models import TenantApiKey, Tenant

# How long a tenant can rely on the platform's shared key before they must
# add their own. After this many days from tenant creation, get_provider_key
# stops returning the platform fallback for any provider the tenant hasn't
# configured themselves -- the dependent feature then degrades exactly the
# way it already does when no key is configured at all (a clear warning,
# not a crash, per the existing fallback handling throughout the app).
PLATFORM_KEY_GRACE_PERIOD_DAYS = 7

# Providers tenants are allowed to override, with a direct link to where
# they generate a key. Verified working URLs as of June 2026 -- Anthropic,
# OpenAI, and Alpha Vantage are direct deep links to the key page itself;
# the others go to the provider's main dashboard/signup since their exact
# key sub-page is more likely to move -- double check those four before
# relying on them long-term.
KNOWN_PROVIDERS = [
    ("ANTHROPIC_API_KEY", "Anthropic (Claude)", "https://console.anthropic.com/settings/keys"),
    ("OPENAI_API_KEY", "OpenAI (GPT)", "https://platform.openai.com/api-keys"),
    ("POLYGON_API_KEY", "Polygon.io", "https://polygon.io/dashboard/signup"),
    ("ALPHA_VANTAGE_API_KEY", "Alpha Vantage", "https://www.alphavantage.co/support/#api-key"),
    ("MARKETDATA_API_KEY", "MarketData.app", "https://www.marketdata.app/"),
    ("FINNHUB_API_KEY", "Finnhub", "https://finnhub.io/register"),
    ("TWELVEDATA_API_KEY", "Twelve Data", "https://twelvedata.com/pricing"),
    ("FMP_API_KEY", "Financial Modeling Prep", "https://site.financialmodelingprep.com/developer/docs"),
    ("MASSIVE_API_KEY", "Massive (options data)", "https://polygon.io/dashboard/signup"),
    ("ALPACA_API_KEY", "Alpaca (brokerage)", "https://app.alpaca.markets/signup"),
    ("FINTEL_API_KEY", "Fintel", "https://fintel.io/"),
    ("QUIVER_API_KEY", "QuiverQuant", "https://www.quiverquant.com/"),
]


# -----------------------------------------------------
# ENCRYPTION
# -----------------------------------------------------

def generate_encryption_key() -> str:
    """Run this once to generate APP_ENCRYPTION_KEY for Streamlit secrets."""
    from cryptography.fernet import Fernet
    return Fernet.generate_key().decode()


def _get_fernet():
    from cryptography.fernet import Fernet

    raw_key = None
    try:
        raw_key = st.secrets.get("APP_ENCRYPTION_KEY", "")
    except Exception:
        pass
    if not raw_key:
        raw_key = os.getenv("APP_ENCRYPTION_KEY", "")

    if not raw_key:
        raise RuntimeError(
            "APP_ENCRYPTION_KEY is not configured. Generate one with "
            "tenant_api_keys.generate_encryption_key() and add it to "
            "Streamlit secrets, then restart the app."
        )

    return Fernet(raw_key.encode())


def _encrypt(raw_value: str) -> str:
    return _get_fernet().encrypt(raw_value.encode()).decode()


def _decrypt(ciphertext: str) -> str:
    return _get_fernet().decrypt(ciphertext.encode()).decode()


def _get_db_session():
    """Open a short-lived session for callers that don't already have one
    (most narrative/AI helper functions don't carry a db handle today)."""
    from modules.db.core import SessionLocal
    return SessionLocal()


def _has_streamlit_context() -> bool:
    """True only if we're running on the actual Streamlit script thread.
    Background job threads (e.g. a queued universe-refresh job running
    off the main script thread) have no ScriptRunContext attached -- in
    that case, calling st.session_state / st.secrets / any st.* API
    doesn't raise a normal Python exception we could try/except. It
    fails inside Streamlit's own runtime (trying to deliver a message to
    a session that doesn't exist), which is exactly the "Tried to use
    SessionInfo before it was initialized" error. The fix is to never
    make the call in the first place when there's no valid context.
    """
    try:
        from streamlit.runtime.scriptrunner_utils.script_run_context import (
            get_script_run_ctx,
        )
        return get_script_run_ctx() is not None
    except Exception:
        return False


def _current_tenant_id() -> Optional[str]:
    if not _has_streamlit_context():
        return None
    try:
        user = st.session_state.get("user")
        if user:
            return user.get("tenant_id")
    except Exception:
        pass
    return None


def grace_period_status(db, tenant_id: str) -> dict:
    """Returns {'expired': bool, 'days_left': int|None, 'created_at': datetime|None,
    'unlimited': bool, 'days_override': int|None}.
    Fails safe: if the tenant record can't be found, treats the grace
    period as NOT expired rather than locking the tenant out due to a
    data problem.
    """
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if tenant is None or tenant.created_at is None:
        return {
            "expired": False, "days_left": None, "created_at": None,
            "unlimited": False, "days_override": None,
        }

    if getattr(tenant, "api_grace_unlimited", False):
        return {
            "expired": False, "days_left": None, "created_at": tenant.created_at,
            "unlimited": True, "days_override": None,
        }

    created_at = tenant.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)

    days_override = getattr(tenant, "api_grace_days_override", None)
    grace_days = days_override if days_override is not None else PLATFORM_KEY_GRACE_PERIOD_DAYS

    deadline = created_at + timedelta(days=grace_days)
    now = datetime.now(UTC)
    days_left = (deadline - now).days

    return {
        "expired": now >= deadline,
        "days_left": max(days_left, 0),
        "created_at": created_at,
        "unlimited": False,
        "days_override": days_override,
    }


def set_tenant_grace_override(
    db, tenant_id: str, unlimited: Optional[bool] = None, days_override: Optional[int] = None,
    clear_override: bool = False,
) -> None:
    """Super-admin override of a tenant's API key grace period.

    - unlimited=True: this tenant's platform-key fallback never expires.
    - days_override=N: use N days instead of the global default for this
      tenant only (still subject to expiry, just on a different clock).
    - clear_override=True: remove any override and revert to the default
      PLATFORM_KEY_GRACE_PERIOD_DAYS behavior.
    """
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if tenant is None:
        raise ValueError(f"No tenant found with id {tenant_id!r}")

    if clear_override:
        tenant.api_grace_unlimited = False
        tenant.api_grace_days_override = None
    else:
        if unlimited is not None:
            tenant.api_grace_unlimited = unlimited
        if days_override is not None:
            tenant.api_grace_days_override = days_override
            tenant.api_grace_unlimited = False

    db.commit()


# -----------------------------------------------------
# CRUD
# -----------------------------------------------------

def set_tenant_key(db, tenant_id: str, provider: str, raw_key: str, user_id: str = None) -> None:
    """Create or update a tenant's key for a provider (upsert)."""
    raw_key = (raw_key or "").strip()
    if not raw_key:
        raise ValueError("Key value cannot be empty.")

    row = (
        db.query(TenantApiKey)
        .filter(TenantApiKey.tenant_id == tenant_id, TenantApiKey.provider == provider)
        .first()
    )

    encrypted = _encrypt(raw_key)
    suffix = raw_key[-4:] if len(raw_key) >= 4 else raw_key

    if row:
        row.encrypted_value = encrypted
        row.key_suffix = suffix
        row.is_active = True
        row.updated_at = datetime.now(UTC)
    else:
        row = TenantApiKey(
            tenant_id=tenant_id,
            provider=provider,
            encrypted_value=encrypted,
            key_suffix=suffix,
            is_active=True,
            created_by_user_id=user_id,
        )
        db.add(row)

    db.commit()


def delete_tenant_key(db, tenant_id: str, provider: str) -> bool:
    row = (
        db.query(TenantApiKey)
        .filter(TenantApiKey.tenant_id == tenant_id, TenantApiKey.provider == provider)
        .first()
    )
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True


def list_tenant_keys(db, tenant_id: str) -> list[TenantApiKey]:
    return (
        db.query(TenantApiKey)
        .filter(TenantApiKey.tenant_id == tenant_id, TenantApiKey.is_active == True)  # noqa: E712
        .order_by(TenantApiKey.provider)
        .all()
    )


# -----------------------------------------------------
# RESOLVER -- the function the rest of the app should call
# -----------------------------------------------------

def get_provider_key(provider: str, db=None, tenant_id: Optional[str] = None) -> str:
    """Resolve an API key for `provider`, preferring the current tenant's
    own key (if they've set one) and falling back to the platform-wide
    key in Streamlit secrets / the environment.

    Safe to call from anywhere -- opens and closes its own short-lived db
    session if one isn't supplied, and never raises if nothing is found
    (returns "").
    """
    resolved_tenant_id = tenant_id or _current_tenant_id()

    if resolved_tenant_id:
        owns_session = db is None
        session = db or _get_db_session()
        try:
            row = (
                session.query(TenantApiKey)
                .filter(
                    TenantApiKey.tenant_id == resolved_tenant_id,
                    TenantApiKey.provider == provider,
                    TenantApiKey.is_active == True,  # noqa: E712
                )
                .first()
            )
            if row is not None:
                try:
                    return _decrypt(row.encrypted_value)
                except Exception:
                    # Corrupt/undecryptable row (e.g. encryption key
                    # rotated) -- fall through to the platform key rather
                    # than hard-failing the caller.
                    pass
            else:
                # No tenant-specific key set -- check whether they're
                # still inside the grace period for using the platform's
                # shared key at all.
                status = grace_period_status(session, resolved_tenant_id)
                if status["expired"]:
                    return ""
        except Exception:
            pass
        finally:
            if owns_session:
                session.close()

    # Platform-wide fallback -- same lookup every call site used to do
    # individually.
    platform_key = ""
    if _has_streamlit_context():
        try:
            platform_key = st.secrets.get(provider, "")
        except Exception:
            platform_key = ""
    if not platform_key:
        platform_key = os.getenv(provider, "")
    return platform_key or ""