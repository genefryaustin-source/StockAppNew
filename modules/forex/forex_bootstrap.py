"""
modules/forex/forex_bootstrap.py

Cycle-safe bootstrap entry point for the Forex subsystem.

This module intentionally avoids importing the full Forex application stack at
module import time. All heavy imports are lazy so app.py can safely import:

    from modules.forex.forex_bootstrap import bootstrap_forex_runtime

without triggering circular dependency chains.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


_RUNTIME_STATE: Dict[str, Any] = {
    "initialized": False,
    "started_at": None,
    "completed_at": None,
    "last_error": None,
    "mode": "development",
    "components": {},
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _component(name: str, fn) -> Dict[str, Any]:
    """
    Execute one bootstrap component safely.
    """

    try:
        value = fn()

        if isinstance(value, dict):
            if "status" not in value:
                value["status"] = "READY"
            return value

        return {
            "status": "READY",
            "component": name,
        }

    except Exception as exc:

        return {
            "status": "WARNING",
            "component": name,
            "error": str(exc),
        }


def bootstrap_forex_runtime(
    db: Optional[Any] = None,
    mode: str = "development",
    session_factory=None,
) -> Dict[str, Any]:

    global _RUNTIME_STATE

    if _RUNTIME_STATE["initialized"]:
        return {
            "status": "READY",
            "mode": _RUNTIME_STATE["mode"],
            "initialized_at": _RUNTIME_STATE["started_at"],
            "components": dict(_RUNTIME_STATE["components"]),
        }

    started = _now()

    components: Dict[str, Any] = {}

    #
    # Registry
    #

    def _registry():

        from modules.forex.forex_registry import get_forex_registry

        registry = get_forex_registry()

        if hasattr(registry, "initialize"):
            return registry.initialize()

        if hasattr(registry, "summary"):
            return registry.summary()

        return {
            "status": "READY",
            "component": type(registry).__name__,
        }

    components["registry"] = _component("registry", _registry)

    #
    # Runtime Manager
    #

    def _runtime():

        from modules.forex.forex_runtime_manager import (
            get_forex_runtime_manager,
        )

        runtime = get_forex_runtime_manager()

        if hasattr(runtime, "start"):
            return runtime.start()

        if hasattr(runtime, "status"):
            return runtime.status()

        return {
            "status": "READY",
            "component": type(runtime).__name__,
        }

    components["runtime"] = _component("runtime", _runtime)

    #
    # Database Bootstrap
    #

    if db is not None:

        def _database():

            from modules.forex.forex_database_initializer import (
                initialize_forex_database,
            )

            initialize_forex_database(db=db)

            return {"status": "READY"}

        components["database"] = _component("database", _database)

    else:

        components["database"] = {
            "status": "SKIPPED"
        }

    #
    # Session Manager
    #

    if session_factory is not None:

        def _sessions():

            from modules.forex.forex_session_manager import (
                configure_forex_session_manager,
            )

            configure_forex_session_manager(session_factory)

            return {"status": "READY"}

        components["session_manager"] = _component(
            "session_manager",
            _sessions,
        )

    else:

        components["session_manager"] = {
            "status": "SKIPPED"
        }

    #
    # Provider Router
    #

    def _router():

        from modules.forex.forex_provider_router import (
            get_forex_provider_router,
        )

        get_forex_provider_router()

        return {"status": "READY"}

    components["provider_router"] = _component(
        "provider_router",
        _router,
    )

    #
    # Quote Cache
    #

    def _quotes():

        from modules.forex.forex_quote_cache import (
            get_forex_quote_cache,
        )

        get_forex_quote_cache()

        return {"status": "READY"}

    components["quote_cache"] = _component(
        "quote_cache",
        _quotes,
    )

    #
    # History Cache
    #

    def _history():

        from modules.forex.forex_history_cache import (
            get_forex_history_cache,
        )

        get_forex_history_cache()

        return {"status": "READY"}

    components["history_cache"] = _component(
        "history_cache",
        _history,
    )

    #
    # Provider Health
    #

    def _health():

        from modules.forex.forex_provider_health import (
            get_forex_provider_health,
        )

        get_forex_provider_health()

        return {"status": "READY"}

    components["provider_health"] = _component(
        "provider_health",
        _health,
    )

    #
    # Currency Strength
    #

    def _strength():

        from modules.forex.forex_currency_strength_engine import (
            get_forex_currency_strength_engine,
        )

        get_forex_currency_strength_engine()

        return {"status": "READY"}

    components["currency_strength"] = _component(
        "currency_strength",
        _strength,
    )

    #
    # Alpha Model
    #
    # IMPORTANT:
    # Instantiate only.
    # Never execute run_alpha_model() here.
    #

    def _alpha():

        from modules.forex.forex_alpha_model import (
            get_forex_alpha_model,
        )

        get_forex_alpha_model()

        return {"status": "READY"}

    components["alpha_model"] = _component(
        "alpha_model",
        _alpha,
    )

    completed = _now()

    _RUNTIME_STATE = {
        "initialized": True,
        "started_at": started,
        "completed_at": completed,
        "last_error": None,
        "mode": mode,
        "components": components,
    }

    return {
        "status": "READY",
        "mode": mode,
        "initialized_at": started,
        "completed_at": completed,
        "components": components,
    }


def shutdown_forex_runtime() -> Dict[str, Any]:

    global _RUNTIME_STATE

    runtime_report = {"status": "SKIPPED"}

    try:

        from modules.forex.forex_runtime_manager import (
            get_forex_runtime_manager,
        )

        runtime = get_forex_runtime_manager()

        if hasattr(runtime, "stop"):
            runtime_report = runtime.stop()

    except Exception as exc:

        runtime_report = {
            "status": "WARNING",
            "error": str(exc),
        }

    _RUNTIME_STATE["initialized"] = False

    return {
        "status": "STOPPED",
        "runtime": runtime_report,
        "timestamp": _now(),
    }


def forex_runtime_status() -> Dict[str, Any]:
    return dict(_RUNTIME_STATE)


# ---------------------------------------------------------------------
# Backwards-compatible aliases
# ---------------------------------------------------------------------

def bootstrap_forex_platform(
    db: Optional[Any] = None,
    mode: str = "development",
    session_factory=None,
) -> Dict[str, Any]:

    return bootstrap_forex_runtime(
        db=db,
        mode=mode,
        session_factory=session_factory,
    )


def shutdown_forex_platform() -> Dict[str, Any]:
    return shutdown_forex_runtime()


def reload_forex_platform(
    db: Optional[Any] = None,
    mode: str = "development",
    session_factory=None,
) -> Dict[str, Any]:

    shutdown_forex_runtime()

    return bootstrap_forex_runtime(
        db=db,
        mode=mode,
        session_factory=session_factory,
    )


def platform_status() -> Dict[str, Any]:
    return forex_runtime_status()