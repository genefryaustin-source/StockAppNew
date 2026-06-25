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
    "last_error": None,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def bootstrap_forex_runtime(db: Optional[Any] = None, mode: str = "development") -> Dict[str, Any]:
    """
    Initialize only the minimum safe Forex runtime.

    The Streamlit UI should be rendered separately through forex_workspace or
    forex_app_router. This keeps bootstrap from importing UI/service wrappers
    that can create circular imports.
    """
    global _RUNTIME_STATE

    try:
        registry_report = {"status": "SKIPPED"}
        runtime_report = {"status": "SKIPPED"}

        try:
            from modules.forex.forex_registry import get_forex_registry
            registry = get_forex_registry()
            if hasattr(registry, "initialize"):
                registry_report = registry.initialize()
            elif hasattr(registry, "summary"):
                registry_report = registry.summary()
            else:
                registry_report = {"status": "READY", "component": type(registry).__name__}
        except Exception as exc:
            registry_report = {"status": "WARNING", "error": str(exc)}

        try:
            from modules.forex.forex_runtime_manager import get_forex_runtime_manager
            runtime = get_forex_runtime_manager()
            if hasattr(runtime, "start"):
                runtime_report = runtime.start()
            elif hasattr(runtime, "status"):
                runtime_report = runtime.status()
            else:
                runtime_report = {"status": "READY", "component": type(runtime).__name__}
        except Exception as exc:
            runtime_report = {"status": "WARNING", "error": str(exc)}

        _RUNTIME_STATE = {
            "initialized": True,
            "started_at": _now(),
            "mode": mode,
            "last_error": None,
            "registry": registry_report,
            "runtime": runtime_report,
        }

        return {
            "status": "READY",
            "mode": mode,
            "initialized_at": _RUNTIME_STATE["started_at"],
            "registry": registry_report,
            "runtime": runtime_report,
        }

    except Exception as exc:
        _RUNTIME_STATE["last_error"] = str(exc)
        return {
            "status": "ERROR",
            "error": str(exc),
            "timestamp": _now(),
        }


def shutdown_forex_runtime() -> Dict[str, Any]:
    global _RUNTIME_STATE

    runtime_report = {"status": "SKIPPED"}
    try:
        from modules.forex.forex_runtime_manager import get_forex_runtime_manager
        runtime = get_forex_runtime_manager()
        if hasattr(runtime, "stop"):
            runtime_report = runtime.stop()
    except Exception as exc:
        runtime_report = {"status": "WARNING", "error": str(exc)}

    _RUNTIME_STATE["initialized"] = False

    return {
        "status": "STOPPED",
        "runtime": runtime_report,
        "timestamp": _now(),
    }


def forex_runtime_status() -> Dict[str, Any]:
    return dict(_RUNTIME_STATE)


# Backwards-compatible aliases used by later platform files.
def bootstrap_forex_platform(db: Optional[Any] = None, mode: str = "development") -> Dict[str, Any]:
    return bootstrap_forex_runtime(db=db, mode=mode)


def shutdown_forex_platform() -> Dict[str, Any]:
    return shutdown_forex_runtime()


def reload_forex_platform(db: Optional[Any] = None, mode: str = "development") -> Dict[str, Any]:
    shutdown_forex_runtime()
    return bootstrap_forex_runtime(db=db, mode=mode)


def platform_status() -> Dict[str, Any]:
    return forex_runtime_status()
