"""
modules/forex/ui/forex_ui_theme.py

Sprint 22 — Phase 22.1
Institutional UI Foundation: theme engine.

Centralized styling for the Forex institutional terminal. Every Forex workspace
should import and use this theme instead of defining one-off card/panel styles.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class ForexUITheme:
    name: str = "Institutional Dark"
    bg: str = "#06111d"
    bg_2: str = "#071a26"
    panel: str = "#0b1b2b"
    panel_2: str = "#10233a"
    panel_soft: str = "rgba(13, 39, 58, 0.72)"
    border: str = "rgba(0, 210, 255, 0.32)"
    border_soft: str = "rgba(120, 180, 220, 0.18)"
    text: str = "#eef8ff"
    text_muted: str = "#9bb5c9"
    text_dim: str = "#6f8aa0"
    cyan: str = "#20d6ff"
    teal: str = "#19e0d2"
    green: str = "#2ff58d"
    yellow: str = "#ffd166"
    orange: str = "#ff9f1c"
    red: str = "#ff4d6d"
    purple: str = "#b388ff"
    blue: str = "#4da3ff"
    shadow: str = "0 10px 32px rgba(0, 0, 0, 0.28)"
    radius_sm: str = "10px"
    radius_md: str = "14px"
    radius_lg: str = "18px"
    font: str = "Inter, Segoe UI, Roboto, Helvetica, Arial, sans-serif"
    mono_font: str = "JetBrains Mono, Consolas, Menlo, monospace"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def get_forex_ui_theme() -> ForexUITheme:
    return ForexUITheme()


def forex_ui_css(theme: Optional[ForexUITheme] = None) -> str:
    t = theme or get_forex_ui_theme()
    return f"""
<style>
:root {{
    --fx-bg: {t.bg};
    --fx-bg-2: {t.bg_2};
    --fx-panel: {t.panel};
    --fx-panel-2: {t.panel_2};
    --fx-panel-soft: {t.panel_soft};
    --fx-border: {t.border};
    --fx-border-soft: {t.border_soft};
    --fx-text: {t.text};
    --fx-muted: {t.text_muted};
    --fx-dim: {t.text_dim};
    --fx-cyan: {t.cyan};
    --fx-teal: {t.teal};
    --fx-green: {t.green};
    --fx-yellow: {t.yellow};
    --fx-orange: {t.orange};
    --fx-red: {t.red};
    --fx-purple: {t.purple};
    --fx-blue: {t.blue};
    --fx-shadow: {t.shadow};
    --fx-radius-sm: {t.radius_sm};
    --fx-radius-md: {t.radius_md};
    --fx-radius-lg: {t.radius_lg};
    --fx-font: {t.font};
    --fx-mono: {t.mono_font};
}}

.fx-terminal-root {{
    font-family: var(--fx-font);
    color: var(--fx-text);
}}

.fx-page-header {{
    border: 1px solid var(--fx-border);
    background:
        radial-gradient(circle at top left, rgba(32, 214, 255, 0.16), transparent 30%),
        linear-gradient(135deg, rgba(7, 26, 38, 0.96), rgba(6, 17, 29, 0.92));
    border-radius: var(--fx-radius-lg);
    padding: 18px 22px;
    box-shadow: var(--fx-shadow);
    margin-bottom: 18px;
}}

.fx-page-title {{
    font-size: 1.35rem;
    line-height: 1.2;
    font-weight: 800;
    letter-spacing: -0.02em;
    color: var(--fx-text);
    margin: 0;
}}

.fx-page-subtitle {{
    color: var(--fx-muted);
    font-size: 0.88rem;
    margin-top: 6px;
}}

.fx-section-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    margin: 8px 0 10px 0;
}}

.fx-section-title {{
    font-size: 0.92rem;
    font-weight: 800;
    color: var(--fx-text);
    margin: 0;
}}

.fx-section-kicker {{
    color: var(--fx-cyan);
    font-size: 0.68rem;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
}}

.fx-section-meta {{
    color: var(--fx-muted);
    font-size: 0.72rem;
}}

.fx-panel {{
    border: 1px solid var(--fx-border-soft);
    background: linear-gradient(180deg, rgba(16, 35, 58, 0.86), rgba(7, 20, 32, 0.86));
    border-radius: var(--fx-radius-md);
    padding: 14px;
    box-shadow: var(--fx-shadow);
    margin-bottom: 14px;
}}

.fx-panel-tight {{
    border: 1px solid var(--fx-border-soft);
    background: rgba(7, 20, 32, 0.84);
    border-radius: var(--fx-radius-sm);
    padding: 10px;
    margin-bottom: 10px;
}}

.fx-ribbon {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(138px, 1fr));
    gap: 12px;
    margin: 12px 0 16px 0;
}}

.fx-card {{
    border: 1px solid var(--fx-border);
    background:
        linear-gradient(180deg, rgba(16, 35, 58, 0.96), rgba(8, 22, 35, 0.96));
    border-radius: var(--fx-radius-md);
    padding: 13px 14px;
    min-height: 92px;
    box-shadow: var(--fx-shadow);
}}

.fx-card-label {{
    color: #80cfff;
    font-size: 0.62rem;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    font-weight: 800;
}}

.fx-card-value {{
    color: var(--fx-text);
    font-size: 1.25rem;
    font-weight: 900;
    margin-top: 6px;
}}

.fx-card-caption {{
    color: var(--fx-muted);
    font-size: 0.70rem;
    margin-top: 3px;
}}

.fx-progress {{
    height: 5px;
    width: 100%;
    background: rgba(145, 180, 210, 0.16);
    border-radius: 99px;
    overflow: hidden;
    margin-top: 9px;
}}

.fx-progress > span {{
    display: block;
    height: 100%;
    border-radius: 99px;
    background: linear-gradient(90deg, var(--fx-cyan), var(--fx-green));
}}

.fx-pill {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    border: 1px solid var(--fx-border);
    border-radius: 999px;
    padding: 3px 9px;
    font-size: 0.68rem;
    font-weight: 800;
    color: var(--fx-text);
    background: rgba(7, 25, 38, 0.84);
}}

.fx-pill-dot {{
    width: 7px;
    height: 7px;
    border-radius: 50%;
    display: inline-block;
}}

.fx-muted {{
    color: var(--fx-muted);
}}

.fx-mono {{
    font-family: var(--fx-mono);
}}

.fx-grid-3 {{
    display: grid;
    grid-template-columns: 1.05fr 2.4fr 1.25fr;
    gap: 14px;
}}

.fx-grid-2 {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
}}

.fx-bottom-grid {{
    display: grid;
    grid-template-columns: 1fr;
    gap: 14px;
}}

@media (max-width: 1100px) {{
    .fx-grid-3, .fx-grid-2 {{
        grid-template-columns: 1fr;
    }}
}}
</style>
"""


def inject_forex_ui_theme(st_module: Optional[Any] = None, theme: Optional[ForexUITheme] = None) -> None:
    """
    Inject shared Forex CSS into Streamlit.

    Usage:
        import streamlit as st
        inject_forex_ui_theme(st)
    """
    if st_module is None:
        try:
            import streamlit as st_module  # type: ignore
        except Exception:
            return

    st_module.markdown(forex_ui_css(theme), unsafe_allow_html=True)
