"""
ui/forex/forex_app_patch.py

Small app.py-facing helper for registering and rendering the Forex module.
"""

from __future__ import annotations

from typing import Any, Iterable, List, Optional

from ui.forex.forex_app_integration import (
    initialize_forex,
    render_forex,
    refresh_forex,
    shutdown_forex,
)


FOREX_MENU_LABEL = "Forex"


def ensure_forex_menu(menu_items: Iterable[str]) -> List[str]:
    items = list(menu_items or [])
    if FOREX_MENU_LABEL not in items:
        items.append(FOREX_MENU_LABEL)
    return items


def is_forex_selected(selected: str) -> bool:
    return str(selected or "").strip().lower() in {
        "forex",
        "fx",
        "currency trading",
        "foreign exchange",
    }


def render_if_forex_selected(
    selected: str,
    db: Optional[Any] = None,
) -> bool:
    if not is_forex_selected(selected):
        return False

    render_forex(db=db)
    return True


def startup_forex(db: Optional[Any] = None):
    return initialize_forex(db=db)


def reload_forex(db: Optional[Any] = None):
    return refresh_forex(db=db)


def stop_forex(db: Optional[Any] = None):
    return shutdown_forex(db=db)


APP_PY_SNIPPET = """
# Forex integration
from ui.forex.forex_app_integration import render_forex

# In your main router:
elif selected_module == "Forex":
    render_forex(db=db)
"""
