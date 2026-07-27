"""
api/services/executive_dashboard_api_service.py

Executive Dashboard API Service

Backs GET /api/v1/executive/summary. Wraps every metrics function in
modules.dashboard.executive_dashboard -- the same module app.py's own
"Executive Dashboard" page renders from (modules.dashboard.
executive_dashboard.render_executive_dashboard). No business logic
lives here; this only calls those functions, builds the tenant-scoping
"user" dict they expect, and converts DataFrame/numpy/datetime values
into JSON-safe ones.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _json_safe(value: Any) -> Any:
    """
    Recursively converts a value (or dict/list of values) into
    something the standard JSON encoder can handle -- DataFrames
    become lists of records, numpy scalars become native Python
    types, NaN/NaT become None, datetimes become ISO strings.
    """
    if isinstance(value, pd.DataFrame):
        if value.empty:
            return []
        clean = value.replace([np.inf, -np.inf], np.nan).where(pd.notnull(value), None)
        return [_json_safe(row) for row in clean.to_dict(orient="records")]

    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}

    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]

    if value is None or value is pd.NaT:
        return None

    if isinstance(value, float) and (value != value):  # NaN
        return None

    if hasattr(value, "isoformat"):
        return value.isoformat()

    if isinstance(value, (np.integer,)):
        return int(value)

    if isinstance(value, (np.floating,)):
        return float(value)

    if isinstance(value, (np.bool_,)):
        return bool(value)

    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        try:
            return value.item()
        except Exception:
            pass

    return value


class ExecutiveDashboardAPIService:
    """API service for the platform executive summary."""

    def __init__(self, db):
        self.db = db

    @staticmethod
    def _user_dict(*, tenant_id: str, is_super_admin: bool, roles: list[str]) -> dict[str, Any]:
        """
        Builds the plain dict modules.dashboard.executive_dashboard's
        functions expect (they predate this REST API and were written
        against app.py's Streamlit session-state user representation,
        not api.auth.models.AuthenticatedUser).
        """
        role = "super_admin" if is_super_admin else (roles[0] if roles else "client")
        return {"role": role, "tenant_id": tenant_id}

    def get_summary(
        self,
        *,
        tenant_id: str,
        is_super_admin: bool = False,
        roles: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Every section of the executive dashboard in one response.
        Individual sections that fail are reported as
        {"available": false, "reason": ...} rather than failing the
        whole request -- one slow/broken metric shouldn't take down
        the rest of a genuinely multi-source summary.
        """

        user = self._user_dict(tenant_id=tenant_id, is_super_admin=is_super_admin, roles=roles or [])

        import modules.dashboard.executive_dashboard as ed

        sections: dict[str, Any] = {}

        section_calls = {
            "market": lambda: ed.get_market_metrics(self.db, user),
            "universe": lambda: ed.get_universe_metrics(self.db, user),
            "ai": lambda: ed.get_ai_metrics(self.db, user),
            "platform": lambda: ed.get_platform_metrics(self.db, user),
            "providers": lambda: ed.get_provider_metrics(self.db),
            "analytics_fabric": lambda: ed.get_analytics_fabric_metrics(self.db, user),
            "portfolio": lambda: ed.get_portfolio_metrics(self.db, user),
            "risk": lambda: ed.get_risk_metrics(self.db, user),
            "top_opportunities": lambda: ed.get_top_opportunities(self.db, user, 10),
            "sector_leadership": lambda: ed.get_sector_leadership(self.db, user, 12),
            "earnings_intelligence": lambda: ed.get_earnings_intelligence(self.db, user),
            "smart_money": lambda: ed.get_smart_money_metrics(self.db, user),
        }

        for name, call in section_calls.items():
            try:
                sections[name] = _json_safe(call())
            except Exception:
                logger.exception("Executive dashboard section failed | section=%s", name)
                try:
                    self.db.rollback()
                except Exception:
                    pass
                sections[name] = {"available": False, "reason": "This section failed to load."}

        return {
            "tenant_id": tenant_id,
            **sections,
        }