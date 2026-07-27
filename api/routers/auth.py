from datetime import datetime, UTC
import logging

from fastapi import APIRouter
from fastapi import Depends

from api.auth import get_current_user
from api.auth.models import (
    AuthenticatedUser,
    LoginRequest,
    TokenResponse,
    JWTClaims,
    RefreshRequest,
    LogoutRequest,
    PreferencesUpdateRequest,
)
from api.auth.jwt import jwt_service
from api.auth.permissions import PERMISSIONS
from api.auth.token_revocation import revoke_token
from api.auth.refresh_tokens import issue_refresh_token, rotate_refresh_token, revoke_refresh_token
from api.auth.entitlements import get_capabilities, get_platform_info
from api.auth.preferences import get_preferences, set_preferences
from api.dependencies import get_db
from api.exceptions import Unauthorized, InternalServerError

# Prefix matches every other endpoint in this API (/api/v1/...) -- this
# used to be just "/auth", inconsistent with the rest of the platform
# API's URL structure.
router = APIRouter(
    prefix="/api/v1/auth",
)

logger = logging.getLogger(__name__)


def _permissions_for_role(role: str) -> tuple[list[str], bool]:
    """
    Maps a modules.db.models.User.role string onto (permissions,
    is_super_admin) for the JWT this user's login issues.

    Trading/data access in this app isn't gated by admin status --
    admin.* permissions are specifically platform management (API
    keys, tenants), not asset-class access -- so both "client" (the
    default role for a regular end user) and "tenant_admin" get every
    non-admin permission in the catalog; tenant_admin additionally
    gets admin.api_keys (managing their own tenant's external API
    keys). admin.system/admin.tenants stay super_admin-only, matching
    the same boundary already enforced throughout this API (see
    api/routers/admin_tenants.py, api/routers/admin_api_keys.py).

    An unrecognized role fails closed -- no permissions -- rather than
    guessing.
    """

    if role == "super_admin":
        return [], True

    if role in ("client", "tenant_admin"):
        permissions = [p for p in PERMISSIONS if not p.startswith("admin.")]
        if role == "tenant_admin":
            permissions = permissions + ["admin.api_keys"]
        return permissions, False

    return [], False


def _resolve_default_portfolio_id(db, *, tenant_id: str, user_id: str | None = None) -> str | None:
    """
    This user's default stock portfolio within the tenant, auto-
    created if none exists yet (modules.portfolio.portfolio_service.
    PortfolioService.ensure_default_portfolio) -- populated into this
    session's JWT claims and the login/refresh/me response body so a
    mobile client knows which portfolio to reference (e.g. GET
    /api/v1/portfolio/{id}/dashboard for real equity/cash/performance
    data) without a separate "list my portfolios" call first, the
    same way forex and crypto each already resolve their own default
    portfolio.

    Returns None (rather than raising) on any failure -- a portfolio-
    less session should still be able to log in; it just won't have
    this convenience field populated, the same as before this existed.
    """
    try:
        from modules.portfolio.portfolio_service import PortfolioService

        portfolio = PortfolioService(db).ensure_default_portfolio(tenant_id=tenant_id, user_id=user_id)

        if portfolio is None:
            return None

        # ensure_default_portfolio returns a Portfolio ORM row when one
        # already existed, or a {"id", "name"} dict when it just
        # created one -- normalized here rather than in every caller.
        return portfolio.id if hasattr(portfolio, "id") else portfolio.get("id")

    except Exception:
        logger.exception("Failed to resolve default portfolio | tenant_id=%s", tenant_id)
        return None


def _build_entitlements_payload(
    db,
    *,
    user_id: str,
    tenant_id: str,
    role: str,
    permissions: list[str],
    is_super_admin: bool,
    portfolio_id: str | None = None,
) -> dict:
    """
    Shared by login and /me, so a mobile client can re-fetch the same
    platform/capabilities/preferences shape mid-session (e.g. after a
    super admin changes a tenant's module licensing) without forcing a
    full re-login.
    """

    from modules.db.models import User, Tenant

    user_record = db.query(User).filter(User.id == user_id).one_or_none()
    tenant_record = db.query(Tenant).filter(Tenant.id == tenant_id).one_or_none()

    # A user's real name isn't tracked for every account (User.name is
    # nullable -- accounts created before this column existed, or ones
    # that never set one) -- falls back to the email's local part
    # rather than returning a blank/null name. email itself comes from
    # the User row here (not a passed-in parameter): JWTClaims never
    # carries email at all, so AuthenticatedUser.email is always None
    # for a JWT-authenticated request -- looking it up from the row
    # this function already queries is what actually gets a real value
    # into GET /me's response.
    email = user_record.email if user_record is not None else ""

    display_name = None
    if user_record is not None and user_record.name:
        display_name = user_record.name
    if not display_name:
        display_name = email.split("@")[0] if email else user_id

    return {
        "user": {
            "id": user_id,
            "name": display_name,
            "email": email,
            "role": role,
            "portfolio_id": portfolio_id,
        },
        "tenant": {
            "id": tenant_id,
            "name": tenant_record.name if tenant_record is not None else None,
        },
        "platform": get_platform_info(),
        "capabilities": get_capabilities(
            tenant=tenant_record, permissions=permissions, is_super_admin=is_super_admin,
        ),
        "preferences": get_preferences(db, user_id=user_id),
    }


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    db=Depends(get_db),
):
    """
    Exchange a platform username (email) and password for a session:
    an access token, a refresh token, and the entitlements a mobile or
    web client needs to know upfront -- which asset-class modules this
    tenant is licensed for, a coarse permissions summary, and this
    user's saved preferences -- so the client can decide what to show
    (and what to even request from GET /api/v1/executive/mobile-
    dashboard) before making a single dashboard call. The backend
    still enforces every one of these independently on each request;
    this is a client-side hint, not the security boundary.

    Uses the same credentials and password hash (modules.auth.
    auth_service) as the Streamlit UI's own login -- this is a second
    entry point to the same user accounts, not a separate credential
    system. For machine-to-machine access without a human's password,
    use platform API keys instead (POST /api/v1/api-keys).
    """

    from modules.auth.auth_service import authenticate

    user = authenticate(db, payload.username, payload.password)

    if user is None:
        raise Unauthorized("Incorrect username or password.")

    permissions, is_super_admin = _permissions_for_role(user["role"])

    portfolio_id = _resolve_default_portfolio_id(db, tenant_id=user["tenant_id"], user_id=user["user_id"])

    claims = JWTClaims(
        sub=user["user_id"],
        tenant_id=user["tenant_id"],
        portfolio_id=portfolio_id,
        roles=[user["role"]],
        permissions=permissions,
        is_super_admin=is_super_admin,
    )

    access_token = jwt_service.create_access_token(claims)

    refresh_token, refresh_expires_at = issue_refresh_token(
        db, tenant_id=user["tenant_id"], user_id=user["user_id"],
    )

    entitlements = _build_entitlements_payload(
        db,
        user_id=user["user_id"],
        tenant_id=user["tenant_id"],
        role=user["role"],
        permissions=permissions,
        is_super_admin=is_super_admin,
        portfolio_id=portfolio_id,
    )

    refresh_expires_in = int((refresh_expires_at - datetime.now(UTC).replace(tzinfo=None)).total_seconds())

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="Bearer",
        expires_in=jwt_service.expiration_minutes * 60,
        refresh_expires_in=refresh_expires_in,
        **entitlements,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: RefreshRequest,
    db=Depends(get_db),
):
    """
    Exchanges a refresh token for a brand new access token AND a new
    refresh token (rotation) -- the presented refresh token is revoked
    in the same call and will not work again; the client must store
    the newly returned one. Returns the same full entitlements payload
    as login, since a long-lived mobile session may not have re-
    fetched /me recently and entitlements can change server-side (a
    super admin adjusting a tenant's module licensing, for instance).
    """

    result = rotate_refresh_token(db, raw_token=payload.refresh_token)

    if result is None:
        raise Unauthorized(
            "This refresh token is invalid, expired, or was already used. Please log in again.",
        )

    from modules.db.models import User

    user_record = db.query(User).filter(User.id == result["user_id"]).one_or_none()

    if user_record is None or not user_record.is_active:
        raise Unauthorized("This account is no longer active.")

    permissions, is_super_admin = _permissions_for_role(user_record.role)

    portfolio_id = _resolve_default_portfolio_id(db, tenant_id=result["tenant_id"], user_id=user_record.id)

    claims = JWTClaims(
        sub=user_record.id,
        tenant_id=result["tenant_id"],
        portfolio_id=portfolio_id,
        roles=[user_record.role],
        permissions=permissions,
        is_super_admin=is_super_admin,
    )

    access_token = jwt_service.create_access_token(claims)

    entitlements = _build_entitlements_payload(
        db,
        user_id=user_record.id,
        tenant_id=result["tenant_id"],
        role=user_record.role,
        permissions=permissions,
        is_super_admin=is_super_admin,
        portfolio_id=portfolio_id,
    )

    refresh_expires_in = int(
        (result["refresh_expires_at"] - datetime.now(UTC).replace(tzinfo=None)).total_seconds()
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=result["refresh_token"],
        token_type="Bearer",
        expires_in=jwt_service.expiration_minutes * 60,
        refresh_expires_in=refresh_expires_in,
        **entitlements,
    )


@router.get("/me")
async def me(

    current_user: AuthenticatedUser = Depends(
        get_current_user,
    ),

    db=Depends(get_db),

):
    """
    Same shape as a login/refresh response minus the tokens -- lets a
    client re-check entitlements (e.g. after a super admin changes
    tenant module licensing) without a full re-login.
    """

    base = current_user.model_dump()

    if not current_user.tenant_id or not current_user.user_id:
        return base

    entitlements = _build_entitlements_payload(
        db,
        user_id=current_user.user_id,
        tenant_id=current_user.tenant_id,
        role=(current_user.roles[0] if current_user.roles else "client"),
        permissions=current_user.permissions,
        is_super_admin=current_user.is_super_admin,
        portfolio_id=_resolve_default_portfolio_id(db, tenant_id=current_user.tenant_id, user_id=current_user.user_id),
    )

    return {**base, **entitlements}


@router.post("/logout")
async def logout(
    payload: LogoutRequest | None = None,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Logs out the access token used to authenticate this request -- a
    real, server-side revocation (api.auth.token_revocation), not a
    client-side-only no-op. Optionally also revokes a refresh token if
    the client sends one in the body, so a stored mobile session can't
    silently extend itself via POST /auth/refresh after logout.

    Only meaningful for JWT-authenticated requests (the development
    bypass and platform API key authentication both have no jti to
    revoke -- API keys have their own revoke_key() lifecycle instead,
    see DELETE /api/v1/api-keys/{key_id}).
    """

    if not current_user.jti:
        return {
            "logged_out": False,
            "message": (
                "This request wasn't authenticated with a JWT (development "
                "mode or a platform API key), so there is no token to log "
                "out. API keys are revoked via DELETE /api/v1/api-keys/{key_id}."
            ),
        }

    ok = revoke_token(
        db,
        jti=current_user.jti,
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        expires_at=(
            current_user.expires_at.replace(tzinfo=None)
            if current_user.expires_at is not None
            else None
        ),
    )

    if not ok:
        raise InternalServerError("Logout failed due to a database error.")

    if payload is not None and payload.refresh_token:
        revoke_refresh_token(db, raw_token=payload.refresh_token)

    return {"logged_out": True}


@router.get("/preferences")
async def get_my_preferences(
    current_user: AuthenticatedUser = Depends(get_current_user),
    db=Depends(get_db),
):
    """This user's saved UI preferences, or platform defaults if none have been set yet."""

    if not current_user.user_id:
        raise Unauthorized("No user context on this request.")

    return get_preferences(db, user_id=current_user.user_id)


@router.put("/preferences")
async def update_my_preferences(
    payload: PreferencesUpdateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db=Depends(get_db),
):
    """Updates this user's UI preferences. Omitted fields are left unchanged."""

    if not current_user.user_id:
        raise Unauthorized("No user context on this request.")

    result = set_preferences(
        db,
        user_id=current_user.user_id,
        theme=payload.theme,
        default_workspace=payload.default_workspace,
        notifications=payload.notifications,
    )

    if result is None:
        raise InternalServerError("Failed to save preferences due to a database error.")

    return result