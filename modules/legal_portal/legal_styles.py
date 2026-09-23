import streamlit as st


LEGAL_PORTAL_CSS = r'''
<style>
.aiq-legal-shell {
    border: 1px solid rgba(103, 232, 249, 0.18);
    border-radius: 24px;
    padding: 24px;
    background:
        linear-gradient(135deg, rgba(103,232,249,.055), transparent 48%),
        rgba(12, 21, 36, 0.92);
    box-shadow: 0 24px 70px rgba(0,0,0,.28);
    margin-bottom: 1rem;
}

.aiq-legal-kicker {
    color: #67E8F9;
    font-size: .78rem;
    font-weight: 800;
    letter-spacing: .12em;
    text-transform: uppercase;
    margin-bottom: .25rem;
}

.aiq-legal-title {
    color: white;
    font-size: clamp(1.8rem, 4vw, 3rem);
    font-weight: 800;
    line-height: 1.08;
    margin: 0;
}

.aiq-legal-subtitle {
    color: #A8B3C7;
    margin-top: .7rem;
    max-width: 800px;
}

.aiq-legal-meta {
    display: flex;
    flex-wrap: wrap;
    gap: .6rem;
    margin-top: 1rem;
}

.aiq-legal-badge {
    display: inline-flex;
    align-items: center;
    border: 1px solid rgba(103,232,249,.2);
    border-radius: 999px;
    padding: .3rem .65rem;
    color: #D5FBFF;
    background: rgba(103,232,249,.06);
    font-size: .78rem;
    font-weight: 700;
}

.aiq-legal-card {
    border: 1px solid rgba(103,232,249,.14);
    border-radius: 16px;
    padding: 16px;
    background: rgba(4,11,22,.35);
    height: 100%;
}

.aiq-legal-card h4 {
    color: white;
    margin: 0 0 .4rem;
}

.aiq-legal-card p {
    color: #A8B3C7;
    font-size: .9rem;
    margin: 0;
}

.aiq-legal-doc {
    border: 1px solid rgba(103,232,249,.14);
    border-radius: 18px;
    padding: 24px;
    background: rgba(4,11,22,.32);
    overflow-x: auto;
}

.aiq-legal-doc h1,
.aiq-legal-doc h2,
.aiq-legal-doc h3 {
    color: white;
}

.aiq-legal-doc p,
.aiq-legal-doc li,
.aiq-legal-doc td {
    color: #D5DEEB;
}

.aiq-legal-doc a {
    color: #67E8F9;
}

.aiq-legal-warning {
    border: 1px solid rgba(253,230,138,.35);
    border-radius: 14px;
    padding: 14px 16px;
    background: rgba(253,230,138,.07);
    color: #FFF7CC;
    margin: 1rem 0;
}

.aiq-legal-search-result {
    border-left: 3px solid #67E8F9;
    padding: .7rem .9rem;
    margin: .6rem 0;
    background: rgba(103,232,249,.04);
    border-radius: 0 12px 12px 0;
}

@media print {
    [data-testid="stSidebar"],
    [data-testid="stHeader"],
    .stButton,
    .stDownloadButton {
        display: none !important;
    }

    .aiq-legal-doc,
    .aiq-legal-shell {
        box-shadow: none;
        border-color: #ccc;
        background: white;
    }

    .aiq-legal-doc *,
    .aiq-legal-shell * {
        color: black !important;
    }
}
</style>
'''


def load_legal_styles() -> None:
    st.markdown(LEGAL_PORTAL_CSS, unsafe_allow_html=True)
