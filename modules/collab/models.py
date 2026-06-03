"""
modules/collab/models.py

Collaboration DB models.

Uses the existing tenant_id / user_id structure — no schema changes needed
for the user/tenant tables. These new tables slot into the same SQLite DB.

Tables:
  team_messages       — internal chat per tenant (like Bloomberg IB)
  watchlist_shares    — marks a watchlist as shared with the whole tenant
  chart_annotations   — per-symbol text notes / chart callouts
  screener_presets    — saved and optionally shared screener filter sets
  activity_feed       — audit trail of team actions (optional, read-only)
"""

from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, Boolean, Integer, ForeignKey
from modules.db.models import Base, gen_uuid


def _now():
    return datetime.now(timezone.utc)


# ─────────────────────────────────────────────────────────────
# Team Messages (internal chat)
# ─────────────────────────────────────────────────────────────

class TeamMessage(Base):
    """
    Simple append-only message log per tenant.
    Supports plain text messages and ticker-tagged messages ($NVDA, $AAPL).
    No threading — flat chat like Bloomberg IB.
    """
    __tablename__ = "team_messages"

    id          = Column(String, primary_key=True, default=gen_uuid)
    tenant_id   = Column(String, nullable=False, index=True)
    user_id     = Column(String, nullable=False)
    user_email  = Column(String, nullable=False)      # denormalised for display
    body        = Column(Text, nullable=False)
    ticker_tags = Column(String, nullable=True)        # comma-separated "$NVDA,$AAPL"
    msg_type    = Column(String, default="text")       # text | alert | system
    created_at  = Column(DateTime, default=_now, index=True)
    is_deleted  = Column(Boolean, default=False)


# ─────────────────────────────────────────────────────────────
# Shared Watchlists
# ─────────────────────────────────────────────────────────────

class WatchlistShare(Base):
    """
    Marks a watchlist as shared with the entire tenant team.
    Any tenant member can view (and optionally edit) shared watchlists.
    """
    __tablename__ = "watchlist_shares"

    id             = Column(String, primary_key=True, default=gen_uuid)
    watchlist_id   = Column(String, ForeignKey("watchlists.id"), nullable=False, index=True)
    tenant_id      = Column(String, nullable=False, index=True)
    shared_by      = Column(String, nullable=False)    # user_id
    can_edit       = Column(Boolean, default=False)    # False = view-only
    shared_at      = Column(DateTime, default=_now)
    note           = Column(String, nullable=True)     # optional description


# ─────────────────────────────────────────────────────────────
# Chart Annotations
# ─────────────────────────────────────────────────────────────

class ChartAnnotation(Base):
    """
    Text annotations on a ticker — visible to the whole team.
    Displayed as callouts on price charts and in Stock Dashboard.
    """
    __tablename__ = "chart_annotations"

    id          = Column(String, primary_key=True, default=gen_uuid)
    tenant_id   = Column(String, nullable=False, index=True)
    user_id     = Column(String, nullable=False)
    user_email  = Column(String, nullable=False)
    symbol      = Column(String, nullable=False, index=True)
    body        = Column(Text, nullable=False)
    annotation_type = Column(String, default="note")   # note | bullish | bearish | alert
    price_at    = Column(String, nullable=True)        # price when annotation was made
    is_pinned   = Column(Boolean, default=False)
    created_at  = Column(DateTime, default=_now, index=True)
    updated_at  = Column(DateTime, default=_now, onupdate=_now)
    is_deleted  = Column(Boolean, default=False)


# ─────────────────────────────────────────────────────────────
# Screener Presets
# ─────────────────────────────────────────────────────────────

class ScreenerPreset(Base):
    """
    Saved screener filter configurations.
    Private (owner only) or shared with the whole tenant.
    """
    __tablename__ = "screener_presets"

    id          = Column(String, primary_key=True, default=gen_uuid)
    tenant_id   = Column(String, nullable=False, index=True)
    user_id     = Column(String, nullable=False)
    user_email  = Column(String, nullable=False)
    name        = Column(String, nullable=False)
    description = Column(String, nullable=True)
    filters_json= Column(Text, nullable=False)     # JSON blob of filter config
    query_text  = Column(Text, nullable=True)       # NL screener query if applicable
    is_shared   = Column(Boolean, default=False)    # share with tenant
    result_count= Column(Integer, nullable=True)    # how many symbols matched
    created_at  = Column(DateTime, default=_now)
    updated_at  = Column(DateTime, default=_now, onupdate=_now)


# ─────────────────────────────────────────────────────────────
# Activity Feed
# ─────────────────────────────────────────────────────────────

class ActivityEvent(Base):
    """
    Read-only audit trail of team actions — what each member has done.
    Displayed in the team feed like a Bloomberg activity ticker.
    """
    __tablename__ = "activity_events"

    id          = Column(String, primary_key=True, default=gen_uuid)
    tenant_id   = Column(String, nullable=False, index=True)
    user_id     = Column(String, nullable=False)
    user_email  = Column(String, nullable=False)
    event_type  = Column(String, nullable=False)    # watchlist_add | annotation | message | screener_run | report_gen
    symbol      = Column(String, nullable=True)
    detail      = Column(String, nullable=True)     # short description
    created_at  = Column(DateTime, default=_now, index=True)