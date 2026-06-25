"""
modules/forex/forex_service.py

Cycle-safe service facade for the Forex subsystem.

This file must not import forex_application at module import time.
It provides service-level operations used by APIs, command processors, and UI.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ForexService:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def initialize(self) -> Dict[str, Any]:
        return {"status": "READY", "component": "ForexService"}

    def shutdown(self) -> Dict[str, Any]:
        return {"status": "STOPPED", "component": "ForexService"}

    def diagnostics(self) -> Dict[str, Any]:
        return {
            "status": "READY",
            "component": "ForexService",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def render(self):
        try:
            from modules.forex.forex_workspace import render_forex_workspace
            return render_forex_workspace(db=self.db)
        except Exception as exc:
            return {"status": "ERROR", "error": str(exc)}

    def refresh_market_data(self) -> Dict[str, Any]:
        try:
            from modules.forex.forex_refresh_engine import get_forex_refresh_engine
            engine = get_forex_refresh_engine()
            if hasattr(engine, "refresh"):
                return engine.refresh()
            if hasattr(engine, "run"):
                return engine.run()
            return {"status": "READY", "message": "Refresh engine loaded."}
        except Exception as exc:
            return {"status": "WARNING", "message": "Refresh engine unavailable.", "error": str(exc)}

    def get_command_center(self) -> Dict[str, Any]:
        try:
            from modules.forex.forex_command_center_engine import get_forex_command_center_engine
            engine = get_forex_command_center_engine()
            if hasattr(engine, "build"):
                return engine.build(force_refresh=False)
            return {"status": "READY", "component": type(engine).__name__}
        except Exception as exc:
            return {"status": "ERROR", "error": str(exc)}

    def get_alpha_recommendations(self) -> Dict[str, Any]:
        try:
            from modules.forex.forex_alpha_model import get_forex_alpha_model
            engine = get_forex_alpha_model()
            if hasattr(engine, "command_center_payload"):
                return engine.command_center_payload(force_refresh=False)
            if hasattr(engine, "run_alpha_model"):
                return engine.run_alpha_model(force_refresh=False)
            return {"status": "READY", "component": type(engine).__name__}
        except Exception as exc:
            return {"status": "ERROR", "error": str(exc)}

    def get_currency_strength(self) -> Dict[str, Any]:
        try:
            from modules.forex.forex_currency_strength_engine import get_forex_currency_strength_engine
            engine = get_forex_currency_strength_engine()
            if hasattr(engine, "command_center_payload"):
                return engine.command_center_payload(force_refresh=False)
            if hasattr(engine, "analyze"):
                return engine.analyze(force_refresh=False)
            return {"status": "READY", "component": type(engine).__name__}
        except Exception as exc:
            return {"status": "ERROR", "error": str(exc)}

    def get_macro_regime(self) -> Dict[str, Any]:
        try:
            from modules.forex.forex_macro_regime_engine import get_forex_macro_regime_engine
            engine = get_forex_macro_regime_engine()
            if hasattr(engine, "analyze"):
                return engine.analyze(force_refresh=False)
            return {"status": "READY", "component": type(engine).__name__}
        except Exception as exc:
            return {"status": "ERROR", "error": str(exc)}

    def get_sentiment(self) -> Dict[str, Any]:
        try:
            from modules.forex.forex_sentiment_engine import get_forex_sentiment_engine
            engine = get_forex_sentiment_engine()
            if hasattr(engine, "analyze"):
                return engine.analyze(force_refresh=False)
            return {"status": "READY", "component": type(engine).__name__}
        except Exception as exc:
            return {"status": "ERROR", "error": str(exc)}


_SERVICE = None


def get_forex_service(db: Optional[Any] = None) -> ForexService:
    global _SERVICE
    if _SERVICE is None or (db is not None and _SERVICE.db is None):
        _SERVICE = ForexService(db=db)
    return _SERVICE
