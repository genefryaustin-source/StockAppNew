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
    ("ALPACA_API_SECRET", "Alpaca (brokerage secret)", "https://app.alpaca.markets/signup"),
    ("TRADIER_ACCESS_TOKEN", "Tradier (brokerage)", "https://tradier.com/products/brokerage-api"),
    ("TRADIER_ACCOUNT_ID", "Tradier (account ID)", "https://tradier.com/products/brokerage-api"),
    ("IBKR_ACCOUNT_ID", "Interactive Brokers (account ID)", "https://www.interactivebrokers.com/campus/ibkr-api-page/cpapi-v1/"),
    ("IBKR_GATEWAY_URL", "Interactive Brokers (Client Portal Gateway URL)", "https://www.interactivebrokers.com/campus/ibkr-api-page/cpapi-v1/"),
    ("PORTFOLIOSCIENCE_API_KEY", "PortfolioScience RiskAPI", "https://www.portfolioscience.com/products/riskapi-enterprise"),
    ("FACTSET_API_USERNAME", "FactSet Open:Risk API (username-serial)", "https://developer.factset.com/api-catalog/openrisk-api"),
    ("FACTSET_API_KEY", "FactSet Open:Risk API (API key)", "https://developer.factset.com/api-catalog/openrisk-api"),
    ("CUSTOM_RISK_PROVIDER_BASE_URL", "Custom Risk Provider (base URL)", ""),
    ("CUSTOM_RISK_PROVIDER_API_KEY", "Custom Risk Provider (API key)", ""),
    ("ONDO_API_KEY", "Ondo Finance (Global Markets)", "https://ondo.finance/"),
    ("SECURITIZE_API_KEY", "Securitize", "https://securitize.io/"),
    ("SECURITIZE_API_SECRET", "Securitize (secret)", "https://securitize.io/"),
    ("CUSTOM_TOKENIZED_ASSET_BASE_URL", "Custom Tokenized Asset Provider (base URL)", ""),
    ("CUSTOM_TOKENIZED_ASSET_API_KEY", "Custom Tokenized Asset Provider (API key)", ""),
    ("CCXT_EXCHANGE_ID", "Crypto Exchange (ccxt exchange id, e.g. binance)", "https://docs.ccxt.com/"),
    ("CCXT_API_KEY", "Crypto Exchange (API key)", "https://docs.ccxt.com/"),
    ("CCXT_API_SECRET", "Crypto Exchange (API secret)", "https://docs.ccxt.com/"),
    ("SEC_EDGAR_IDENTITY", "SEC EDGAR (contact identity, e.g. 'Name email@domain.com')", "https://www.sec.gov/os/webmaster-faq#developers"),
    ("FINTEL_API_KEY", "Fintel", "https://fintel.io/"),
    ("QUIVER_API_KEY", "QuiverQuant", "https://www.quiverquant.com/"),
    ("ETHERSCAN_API_KEY","Etherscan","https://etherscan.io/myapikey"),
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


# -----------------------------------------------------
# BROKER PROVIDERS -- same resolution order as get_provider_key, but
# brokers (Alpaca and any future broker/execution provider) need a
# key + secret + environment (paper/live base URL) bundle rather than a
# single string, so they get a small dedicated helper on top of it.
# -----------------------------------------------------

def get_alpaca_credentials(paper: bool = True, db=None, tenant_id: Optional[str] = None) -> dict:
    """
    Resolves Alpaca brokerage credentials exactly like every other
    provider in KNOWN_PROVIDERS: the current tenant's own key/secret
    (set in Settings > API Keys) first, then the platform-wide fallback
    in Streamlit secrets / environment variables. Never raises --
    returns {"configured": False} if nothing is set anywhere, so callers
    can show a clear "connect Alpaca" prompt instead of crashing.

    Also honors the older nested `st.secrets["alpaca"] = {API_KEY,
    API_SECRET, BASE_URL_PAPER, BASE_URL_LIVE}` block for backwards
    compatibility with deployments that were set up before the flat
    ALPACA_API_KEY / ALPACA_API_SECRET convention existed.
    """
    api_key = get_provider_key("ALPACA_API_KEY", db=db, tenant_id=tenant_id)
    api_secret = get_provider_key("ALPACA_API_SECRET", db=db, tenant_id=tenant_id)

    base_url_paper = "https://paper-api.alpaca.markets"
    base_url_live = "https://api.alpaca.markets"

    legacy = {}
    if _has_streamlit_context():
        try:
            legacy = dict(st.secrets.get("alpaca", {}))
        except Exception:
            legacy = {}

    if not api_key:
        api_key = legacy.get("API_KEY", "")
    if not api_secret:
        api_secret = legacy.get("API_SECRET", "")
    base_url_paper = legacy.get("BASE_URL_PAPER") or base_url_paper
    base_url_live = legacy.get("BASE_URL_LIVE") or base_url_live

    return {
        "api_key": api_key,
        "api_secret": api_secret,
        "base_url": base_url_paper if paper else base_url_live,
        "paper": paper,
        "configured": bool(api_key and api_secret),
    }

def get_tradier_credentials(sandbox: bool = True, db=None, tenant_id: Optional[str] = None) -> dict:
    """
    Resolves Tradier brokerage credentials the same way as every other
    provider: tenant key first, then platform secret/env fallback.
    Tradier auths with a single bearer access token, but calls are scoped
    to an account id, so both TRADIER_ACCESS_TOKEN and TRADIER_ACCOUNT_ID
    are resolved. Also honors a legacy nested st.secrets["tradier"] block
    for parity with the Alpaca back-compat path.
    """
    access_token = get_provider_key("TRADIER_ACCESS_TOKEN", db=db, tenant_id=tenant_id)
    account_id = get_provider_key("TRADIER_ACCOUNT_ID", db=db, tenant_id=tenant_id)

    legacy = {}
    if _has_streamlit_context():
        try:
            legacy = dict(st.secrets.get("tradier", {}))
        except Exception:
            legacy = {}

    if not access_token:
        access_token = legacy.get("ACCESS_TOKEN", "")
    if not account_id:
        account_id = legacy.get("ACCOUNT_ID", "")

    base_url = "https://sandbox.tradier.com" if sandbox else "https://api.tradier.com"
    base_url = legacy.get("BASE_URL_SANDBOX" if sandbox else "BASE_URL_PRODUCTION") or base_url

    return {
        "access_token": access_token,
        "account_id": account_id,
        "base_url": base_url,
        "sandbox": sandbox,
        "configured": bool(access_token and account_id),
    }


def get_ibkr_credentials(db=None, tenant_id: Optional[str] = None) -> dict:
    """
    Resolves Interactive Brokers connection settings.

    IBKR is structurally different from Alpaca/Tradier: retail accounts
    don't get a static API key + secret. Programmatic access goes through
    IBKR's Client Portal Gateway -- a small local/hosted process the user
    must run and log into (with 2FA) themselves in a browser. This app
    can only talk to that already-authenticated gateway over its local
    REST API; it cannot perform the login for you (nor should it try --
    entering IBKR credentials on the user's behalf isn't something this
    app does).

    So "configured" here means: a gateway URL and account id are set,
    NOT that the session is currently authenticated. Use
    IBKRBroker.test_connection() to check live session status.
    """
    account_id = get_provider_key("IBKR_ACCOUNT_ID", db=db, tenant_id=tenant_id)
    gateway_url = get_provider_key("IBKR_GATEWAY_URL", db=db, tenant_id=tenant_id)

    legacy = {}
    if _has_streamlit_context():
        try:
            legacy = dict(st.secrets.get("ibkr", {}))
        except Exception:
            legacy = {}

    if not account_id:
        account_id = legacy.get("ACCOUNT_ID", "")
    if not gateway_url:
        gateway_url = legacy.get("GATEWAY_URL", "")

    gateway_url = (gateway_url or "https://localhost:5000/v1/api").rstrip("/")

    return {
        "account_id": account_id,
        "base_url": gateway_url,
        # account_id can be auto-discovered from the gateway session, so
        # only require the gateway URL to consider this "configured" --
        # the real go/no-go check is test_connection().
        "configured": bool(gateway_url),
    }


def get_portfolioscience_credentials(db=None, tenant_id: Optional[str] = None) -> dict:
    """PortfolioScience RiskAPI -- a single API key, same resolution order
    (tenant key first, platform fallback second) as every other provider."""
    api_key = get_provider_key("PORTFOLIOSCIENCE_API_KEY", db=db, tenant_id=tenant_id)
    return {
        "api_key": api_key,
        "base_url": "https://api.portfolioscience.com",
        "configured": bool(api_key),
    }


def get_factset_credentials(db=None, tenant_id: Optional[str] = None) -> dict:
    """
    FactSet's developer APIs authenticate with HTTP Basic auth using a
    "username-serial:api-key" pair issued from FactSet's developer portal
    (https://developer.factset.com) -- not a single bearer token.
    """
    username = get_provider_key("FACTSET_API_USERNAME", db=db, tenant_id=tenant_id)
    api_key = get_provider_key("FACTSET_API_KEY", db=db, tenant_id=tenant_id)
    return {
        "username": username,
        "api_key": api_key,
        "base_url": "https://api.factset.com",
        "configured": bool(username and api_key),
    }


def get_custom_risk_provider_credentials(db=None, tenant_id: Optional[str] = None) -> dict:
    """
    A generic REST risk provider slot for any vendor (or in-house service)
    without a dedicated adapter -- a base URL + bearer API key, with the
    JSON response field mapping configured separately in the Risk
    Providers admin tab (modules.risk_providers.provider_settings), since
    that's tenant-specific config rather than a credential.
    """
    base_url = get_provider_key("CUSTOM_RISK_PROVIDER_BASE_URL", db=db, tenant_id=tenant_id)
    api_key = get_provider_key("CUSTOM_RISK_PROVIDER_API_KEY", db=db, tenant_id=tenant_id)
    return {
        "base_url": (base_url or "").rstrip("/"),
        "api_key": api_key,
        "configured": bool(base_url and api_key),
    }


def get_ondo_credentials(db=None, tenant_id: Optional[str] = None) -> dict:
    """Ondo Finance / Ondo Global Markets -- a single API key, same
    resolution order as every other provider."""
    api_key = get_provider_key("ONDO_API_KEY", db=db, tenant_id=tenant_id)
    return {
        "api_key": api_key,
        "base_url": "https://api.ondo.finance",
        "configured": bool(api_key),
    }


def get_securitize_credentials(db=None, tenant_id: Optional[str] = None) -> dict:
    """Securitize -- API key + secret pair, same resolution order as
    every other provider."""
    api_key = get_provider_key("SECURITIZE_API_KEY", db=db, tenant_id=tenant_id)
    api_secret = get_provider_key("SECURITIZE_API_SECRET", db=db, tenant_id=tenant_id)
    return {
        "api_key": api_key,
        "api_secret": api_secret,
        "base_url": "https://api.securitize.io",
        "configured": bool(api_key and api_secret),
    }


def get_custom_tokenized_asset_credentials(db=None, tenant_id: Optional[str] = None) -> dict:
    """Generic tokenized-asset venue slot -- base URL + bearer API key,
    for any custodian/platform without a dedicated adapter."""
    base_url = get_provider_key("CUSTOM_TOKENIZED_ASSET_BASE_URL", db=db, tenant_id=tenant_id)
    api_key = get_provider_key("CUSTOM_TOKENIZED_ASSET_API_KEY", db=db, tenant_id=tenant_id)
    return {
        "base_url": (base_url or "").rstrip("/"),
        "api_key": api_key,
        "configured": bool(base_url and api_key),
    }


def get_ccxt_credentials(db=None, tenant_id: Optional[str] = None) -> dict:
    """
    Crypto exchange credentials for the ccxt broker. CCXT_EXCHANGE_ID picks
    which of ccxt's 100+ supported exchanges to connect to (e.g. "binance",
    "coinbase", "kraken") -- defaults to "binance" if not set.
    """
    exchange_id = get_provider_key("CCXT_EXCHANGE_ID", db=db, tenant_id=tenant_id) or "binance"
    api_key = get_provider_key("CCXT_API_KEY", db=db, tenant_id=tenant_id)
    api_secret = get_provider_key("CCXT_API_SECRET", db=db, tenant_id=tenant_id)
    return {
        "exchange_id": exchange_id.strip().lower(),
        "api_key": api_key,
        "api_secret": api_secret,
        "configured": bool(api_key and api_secret),
    }
