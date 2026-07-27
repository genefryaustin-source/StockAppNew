
"""
ui/admin/forex_terminal_validation_nav.py

Tiny entrypoint wrapper that can be imported from an existing Admin Panel.
"""

from __future__ import annotations

from ui.admin.forex_terminal_validation_center import render_forex_terminal_validation_center


def render(db=None):
    return render_forex_terminal_validation_center(db=db)
