from __future__ import annotations

from pathlib import Path
import base64
import streamlit as st


CONDURO_PRIMARY = "#28D7FF"
CONDURO_ACCENT = "#2DF8A8"
CONDURO_BG = "#050B14"
CONDURO_PANEL = "#0C1524"
CONDURO_PANEL_2 = "#101C2E"
CONDURO_BORDER = "rgba(103, 232, 249, 0.18)"
CONDURO_TEXT = "#F8FAFC"
CONDURO_MUTED = "#A8B3C7"


def _asset_data_uri(filename: str) -> str:
    path = Path(__file__).parent / "assets" / filename
    if not path.exists():
        return ""
    data = path.read_bytes()
    suffix = path.suffix.lower()
    mime = "image/svg+xml" if suffix == ".svg" else "image/png"
    encoded = base64.b64encode(data).decode("utf-8")
    return f"data:{mime};base64,{encoded}"


def conduro_logo_uri() -> str:
    return _asset_data_uri("conduro-logo.svg")


def conduro_mark_uri() -> str:
    return _asset_data_uri("conduro-mark.svg")


def load_conduro_theme() -> None:
    """Inject Conduro Ventures / Stock Research Terminal visual styling."""
    logo_uri = conduro_logo_uri()
    mark_uri = conduro_mark_uri()

    st.markdown(
        f"""
<style>
:root {{
    --conduro-bg: {CONDURO_BG};
    --conduro-panel: {CONDURO_PANEL};
    --conduro-panel-2: {CONDURO_PANEL_2};
    --conduro-primary: {CONDURO_PRIMARY};
    --conduro-accent: {CONDURO_ACCENT};
    --conduro-border: {CONDURO_BORDER};
    --conduro-text: {CONDURO_TEXT};
    --conduro-muted: {CONDURO_MUTED};
}}

html, body, [data-testid="stAppViewContainer"], .stApp {{
    background:
        radial-gradient(circle at top left, rgba(40, 215, 255, 0.14), transparent 34rem),
        radial-gradient(circle at top right, rgba(45, 248, 168, 0.10), transparent 30rem),
        linear-gradient(180deg, #050B14 0%, #07101D 48%, #050B14 100%) !important;
    color: var(--conduro-text) !important;
}}

[data-testid="stHeader"] {{
    background: rgba(5, 11, 20, 0.70) !important;
    backdrop-filter: blur(18px);
    border-bottom: 1px solid var(--conduro-border);
}}

[data-testid="stSidebar"] {{
    background: linear-gradient(180deg, #07101D 0%, #050B14 100%) !important;
    border-right: 1px solid var(--conduro-border);
}}

[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] span {{
    color: var(--conduro-text) !important;
}}
/* Sidebar radio navigation */

div[role="radiogroup"] label {{

    color: #D7E3F4 !important;
    opacity: 1 !important;
    font-weight: 500 !important;

}}

div[role="radiogroup"] label p {{

    color: #D7E3F4 !important;
    opacity: 1 !important;

}}

div[role="radiogroup"] * {{

    color: #D7E3F4 !important;

}}

.block-container {{
    padding-top: 2.5rem !important;
    padding-bottom: 1rem !important;
    max-width: 1900px !important;
}}

.conduro-shell {{
    margin-top: 0.75rem;
}}

h1 {{
    color: var(--conduro-text) !important;
    font-size: 1.50rem !important;
    font-weight: 700 !important;
    line-height: 1.2 !important;
    margin-bottom: 0.5rem !important;
}}

h2 {{
    color: var(--conduro-text) !important;
    font-size: 1.20rem !important;
    font-weight: 650 !important;
    line-height: 1.2 !important;
    margin-bottom: 0.4rem !important;
}}

h3 {{
    color: var(--conduro-text) !important;
    font-size: 1.00rem !important;
    font-weight: 600 !important;
    line-height: 1.15 !important;
    margin-bottom: 0.3rem !important;
}}

h4 {{
    color: var(--conduro-text) !important;
    font-size: 0.90rem !important;
    font-weight: 600 !important;
    line-height: 1.1 !important;
    margin-bottom: 0.25rem !important;
}}

p, li, label, span, div {{
    color: inherit;
}}

a {{
    color: var(--conduro-primary) !important;
}}

.stButton > button,
[data-testid="stBaseButton-secondary"],
[data-testid="stBaseButton-primary"] {{
    border-radius: 999px !important;
    border: 1px solid rgba(40, 215, 255, 0.45) !important;
    background: linear-gradient(135deg, rgba(40, 215, 255, 0.22), rgba(45, 248, 168, 0.12)) !important;
    color: #F8FAFC !important;
    box-shadow: 0 12px 32px rgba(40, 215, 255, 0.10);
    font-weight: 700 !important;
}}

.stButton > button:hover {{
    border-color: rgba(45, 248, 168, 0.75) !important;
    box-shadow: 0 14px 42px rgba(40, 215, 255, 0.20);
    transform: translateY(-1px);
}}

[data-testid="stMetric"] {{
    background: linear-gradient(180deg, rgba(16, 28, 46, 0.94), rgba(12, 21, 36, 0.92));
    border: 1px solid var(--conduro-border);
    border-radius: 22px;
    padding: 10px 12px;
    min-height: 90px;
    box-shadow: 0 24px 80px rgba(0,0,0,0.22);
}}

[data-testid="stMetricLabel"] p {{
    color: var(--conduro-muted) !important;
    font-size: 0.65rem !important;
    text-transform: uppercase;
    letter-spacing: .08em;
}}

[data-testid="stMetricValue"] {{
    color: var(--conduro-text) !important;
}}

[data-testid="stMetricDelta"] {{
    color: var(--conduro-text) !important;
    font-size: 1.05rem !important;
    line-height: 1.1 !important;
}}

[data-testid="stExpander"] {{
    background: rgba(12, 21, 36, 0.74) !important;
    border: 1px solid var(--conduro-border) !important;
    border-radius: 18px !important;
    overflow: hidden;
}}

[data-testid="stTabs"] button {{
    color: var(--conduro-muted) !important;
    border-radius: 999px !important;
}}

[data-testid="stTabs"] button[aria-selected="true"] {{
    color: var(--conduro-text) !important;
    background: rgba(40, 215, 255, 0.13) !important;
    border: 1px solid rgba(40, 215, 255, 0.25) !important;
}}

.stDataFrame, [data-testid="stDataFrame"],
[data-testid="stTable"] {{
    border: 1px solid var(--conduro-border) !important;
    border-radius: 18px !important;
    overflow: hidden !important;
    box-shadow: 0 22px 70px rgba(0,0,0,0.20);
    font-size: 12px !important;
}}

div[data-baseweb="select"] > div,
input,
textarea,
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stTextArea"] textarea {{
    background: rgba(5, 11, 20, 0.84) !important;
    color: var(--conduro-text) !important;
    border: 1px solid rgba(103, 232, 249, 0.25) !important;
    border-radius: 14px !important;
}}

[data-testid="stAlert"] {{
    border-radius: 18px !important;
    border: 1px solid var(--conduro-border) !important;
}}

hr {{
    border-color: var(--conduro-border) !important;
}}

.conduro-shell {{
    position: relative;
    border: 1px solid var(--conduro-border);
    background:
        linear-gradient(135deg, rgba(40, 215, 255, 0.11), rgba(45, 248, 168, 0.05)),
        rgba(12, 21, 36, 0.84);
    border-radius: 28px;
    padding: 22px 24px;
    margin-bottom: 22px;
    box-shadow: 0 28px 90px rgba(0,0,0,0.26);
    overflow: hidden;
}}

.conduro-shell::after {{
    content: "";
    position: absolute;
    right: -80px;
    top: -80px;
    width: 240px;
    height: 240px;
    background: radial-gradient(circle, rgba(40,215,255,.20), transparent 70%);
    pointer-events: none;
}}

.conduro-brandbar {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 18px;
}}

.conduro-brand-left {{
    display: flex;
    align-items: center;
    gap: 16px;
}}

.conduro-logo {{
    height: 42px;
    max-width: 260px;
}}

.conduro-mark {{
    height: 44px;
    width: 44px;
    border-radius: 14px;
    box-shadow: 0 0 28px rgba(40, 215, 255, 0.20);
}}

.conduro-kicker {{
    color: var(--conduro-primary);
    text-transform: uppercase;
    letter-spacing: .14em;
    font-size: .78rem;
    font-weight: 800;
    margin-bottom: 3px;
}}

.conduro-title {{
    color: var(--conduro-text);
    font-size: clamp(1.25rem, 2vw, 2rem);
    font-weight: 850;
    letter-spacing: -.035em;
    margin: 0;
}}

.conduro-subtitle {{
    color: var(--conduro-muted);
    margin-top: 4px;
    font-size: .95rem;
}}

.conduro-pill {{
    color: var(--conduro-accent);
    border: 1px solid rgba(45, 248, 168, 0.32);
    background: rgba(45, 248, 168, 0.08);
    padding: 9px 14px;
    border-radius: 999px;
    font-weight: 750;
    white-space: nowrap;
}}

.conduro-card {{
    background: linear-gradient(180deg, rgba(16, 28, 46, 0.94), rgba(12, 21, 36, 0.92));
    border: 1px solid var(--conduro-border);
    border-radius: 22px;
    padding: 20px;
    box-shadow: 0 24px 80px rgba(0,0,0,0.22);
}}

.conduro-small {{
    color: var(--conduro-muted);
    font-size: .88rem;
}}

@media (max-width: 780px) {{
    .conduro-brandbar {{
        align-items: flex-start;
        flex-direction: column;
    }}
    .conduro-logo {{
        max-width: 220px;
    }}
}}
</style>
        """,
        unsafe_allow_html=True,
    )


def render_conduro_header(
    title: str = "Stock Research Terminal",
    subtitle: str = "AI-powered equity research, portfolio analytics, options intelligence, and professional research workflows.",
    kicker: str = "Conduro Ventures LLC",
    status: str = "Research Terminal",
) -> None:
    logo_uri = conduro_logo_uri()
    mark_uri = conduro_mark_uri()

    logo_html = f'<img class="conduro-logo" src="{logo_uri}" alt="Conduro Ventures LLC">' if logo_uri else '<strong>Conduro Ventures LLC</strong>'
    mark_html = f'<img class="conduro-mark" src="{mark_uri}" alt="Conduro mark">' if mark_uri else ""

    st.markdown(
        f"""
<div class="conduro-shell">
  <div class="conduro-brandbar">
    <div class="conduro-brand-left">
      {mark_html}
      <div>
        {logo_html}
        <div class="conduro-kicker">{kicker}</div>
        <h1 class="conduro-title">{title}</h1>
        <div class="conduro-subtitle">{subtitle}</div>
      </div>
    </div>
    <div class="conduro-pill">{status}</div>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )


def conduro_card(title: str, body: str, kicker: str = "") -> None:
    kicker_html = f'<div class="conduro-kicker">{kicker}</div>' if kicker else ""
    st.markdown(
        f"""
<div class="conduro-card">
  {kicker_html}
  <h3 style="margin-top:0">{title}</h3>
  <div class="conduro-small">{body}</div>
</div>
        """,
        unsafe_allow_html=True,
    )
