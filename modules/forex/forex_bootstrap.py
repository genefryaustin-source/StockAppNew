"""
modules/forex/forex_bootstrap.py

Bootstraps the complete Forex subsystem.
"""

from __future__ import annotations

import logging

from modules.forex.forex_workspace import (
    initialize_forex_workspace,
    render_forex_workspace,
)

LOGGER=logging.getLogger("forex.bootstrap")


def bootstrap_forex():
    """
    Initialize every Forex subsystem once during application startup.
    """
    try:
        initialize_forex_workspace()
        LOGGER.info("Forex subsystem initialized successfully.")
        return {
            "status":"success",
            "message":"Forex initialized."
        }
    except Exception as exc:
        LOGGER.exception("Forex bootstrap failed")
        return {
            "status":"error",
            "message":str(exc),
        }


# app.py imports this name specifically (bootstrap_forex_runtime, not
# bootstrap_forex) -- kept as an alias so both names work rather than
# guessing which one is "correct" and risking breaking some other caller
# that may already depend on bootstrap_forex.
def bootstrap_forex_runtime():
    return bootstrap_forex()


def render():
    """
    Main entry point for app.py.
    """
    return render_forex_workspace()