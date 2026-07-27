"""
Institutional Forex UI Framework.

Sprint 22 UI modernization package.
"""

from modules.forex.ui.forex_ui_theme import (
    ForexUITheme,
    get_forex_ui_theme,
    inject_forex_ui_theme,
)

from modules.forex.ui.forex_ui_layout import (
    render_page_header,
    render_workspace_shell,
    render_section_header,
    render_spacer,
)

from modules.forex.ui.forex_ui_status import (
    status_label,
    status_color,
    render_status_pill,
    render_health_pill,
)
