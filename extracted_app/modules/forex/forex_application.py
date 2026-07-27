"""
modules/forex/forex_application.py

Cycle-safe application facade for Forex.

Important:
- No module-level imports from forex_ui_integration, forex_service, or terminal wrappers.
- Rendering uses lazy imports only.
- Service access flows downward into engines/SDK, never back into application.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ForexApplication:
    def __init__(
        self,
        db: Optional[Any] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
    ):
        self.db = db

        self.tenant_id = tenant_id
        self.user_id = user_id
        self.portfolio_id = portfolio_id

        self.created_at = datetime.now(
            timezone.utc,
        ).isoformat()

    def initialize(self) -> Dict[str, Any]:
        try:
            from modules.forex.forex_bootstrap import bootstrap_forex_runtime
            return bootstrap_forex_runtime(db=self.db)
        except Exception as exc:
            return {"status": "ERROR", "error": str(exc)}

    def run(self, **kwargs):
        return self.render(**kwargs)

    def render(self, **kwargs):
        """
        Render UI lazily so importing ForexApplication does not import all UI,
        terminal, service, and AI facades.
        """
        try:
            from modules.forex.forex_workspace import render_forex_workspace
            return render_forex_workspace(
                db=self.db,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                portfolio_id=self.portfolio_id,
            )
        except Exception as exc:
            try:
                import streamlit as st
                st.error(f"Forex workspace failed to load: {exc}")
                with st.expander("Forex fallback status", expanded=False):
                    st.json(self.status())
                return None
            except Exception:
                return {"status": "ERROR", "error": str(exc), "fallback": self.status()}

    def refresh(self) -> Dict[str, Any]:
        try:
            from modules.forex.forex_service import get_forex_service
            service = get_forex_service(db=self.db)
            if hasattr(service, "refresh_market_data"):
                return service.refresh_market_data()
            return {"status": "READY", "message": "Forex service loaded; refresh not implemented."}
        except Exception as exc:
            return {"status": "ERROR", "error": str(exc)}

    def shutdown(self) -> Dict[str, Any]:
        try:
            from modules.forex.forex_bootstrap import shutdown_forex_runtime
            return shutdown_forex_runtime()
        except Exception as exc:
            return {"status": "ERROR", "error": str(exc)}

    def status(self) -> Dict[str, Any]:
        try:
            from modules.forex.forex_bootstrap import forex_runtime_status
            runtime = forex_runtime_status()
        except Exception:
            runtime = {"status": "UNKNOWN"}

        return {
            "status": "READY",
            "component": "ForexApplication",
            "created_at": self.created_at,
            "runtime": runtime,
        }


_APP = None


def get_forex_application(
    db: Optional[Any] = None,
    tenant_id=None,
    user_id=None,
    portfolio_id=None,
) -> ForexApplication:

    global _APP

    if (
        _APP is None
        or _APP.db is not db
        or getattr(_APP, "tenant_id", None) != tenant_id
        or getattr(_APP, "user_id", None) != user_id
        or getattr(_APP, "portfolio_id", None) != portfolio_id
    ):

        _APP = ForexApplication(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
        )

    return _APP
