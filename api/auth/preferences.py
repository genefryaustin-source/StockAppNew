"""
api/auth/preferences.py

User Preferences

Per-user UI preferences (theme, default workspace, notifications).
Read at login (api/routers/auth.py) and updatable via
PUT /api/v1/auth/preferences.
"""

from __future__ import annotations

import logging
from datetime import datetime, UTC

logger = logging.getLogger(__name__)

DEFAULTS = {
    "theme": "dark",
    "default_workspace": "dashboard",
    "notifications": True,
}


def get_preferences(db, *, user_id: str) -> dict:
    """
    Returns this user's preferences, or the platform defaults if
    they've never set any -- a user who's never touched their
    preferences doesn't have (or need) a row in the table yet.
    """

    from modules.db.models import UserPreferences

    try:
        db.rollback()
    except Exception:
        pass

    try:
        record = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).one_or_none()
    except Exception:
        logger.exception("Failed to load user preferences | user_id=%s", user_id)
        try:
            db.rollback()
        except Exception:
            pass
        return dict(DEFAULTS)

    if record is None:
        return dict(DEFAULTS)

    return {
        "theme": record.theme,
        "default_workspace": record.default_workspace,
        "notifications": bool(record.notifications_enabled),
    }


def set_preferences(
    db,
    *,
    user_id: str,
    theme: str | None = None,
    default_workspace: str | None = None,
    notifications: bool | None = None,
) -> dict | None:
    """
    Creates or updates this user's preferences row. Only the fields
    explicitly given (not None) are changed -- omitting a field leaves
    it as whatever it already was (or the default, for a first-time
    write). Returns the resulting preferences dict, or None on a
    database error.
    """

    from modules.db.models import UserPreferences

    try:
        db.rollback()
    except Exception:
        pass

    try:
        record = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).one_or_none()

        if record is None:
            record = UserPreferences(
                user_id=user_id,
                theme=theme or DEFAULTS["theme"],
                default_workspace=default_workspace or DEFAULTS["default_workspace"],
                notifications_enabled=DEFAULTS["notifications"] if notifications is None else notifications,
            )
            db.add(record)
        else:
            if theme is not None:
                record.theme = theme
            if default_workspace is not None:
                record.default_workspace = default_workspace
            if notifications is not None:
                record.notifications_enabled = notifications

        record.updated_at = datetime.now(UTC).replace(tzinfo=None)

        db.commit()

        return {
            "theme": record.theme,
            "default_workspace": record.default_workspace,
            "notifications": bool(record.notifications_enabled),
        }

    except Exception:
        logger.exception("Failed to save user preferences | user_id=%s", user_id)
        try:
            db.rollback()
        except Exception:
            pass
        return None