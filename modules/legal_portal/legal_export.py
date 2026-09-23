from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Optional
import streamlit as st

from .legal_registry import LegalDocument

def build_standalone_html(document: LegalDocument, body_html: str) -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} | AIQ Intellus</title>
<style>
body{{max-width:900px;margin:0 auto;padding:40px 28px;font-family:Arial,Helvetica,sans-serif;color:#111827;line-height:1.65}}
header{{border-bottom:2px solid #0891b2;margin-bottom:30px;padding-bottom:18px}}
h1,h2,h3{{color:#0f172a}} a{{color:#0e7490}}
.meta{{display:flex;flex-wrap:wrap;gap:12px 24px;color:#475569;font-size:14px}}
footer{{border-top:1px solid #cbd5e1;margin-top:36px;padding-top:16px;color:#64748b;font-size:13px}}
@media print{{body{{max-width:none;padding:0}}a{{color:inherit;text-decoration:none}}}}
</style>
</head>
<body>
<header>
<p>AIQ Intellus Legal &amp; Compliance</p>
<h1>{title}</h1>
<div class="meta">
<span>Version {version}</span>
<span>Effective {effective}</span>
<span>{category}</span>
</div>
</header>
<main>{body}</main>
<footer>&copy; 2026 Conduro Ventures LLC. All rights reserved.</footer>
</body>
</html>""".format(
        title=escape(document.title),
        version=escape(document.version),
        effective=escape(document.effective_date),
        category=escape(document.category),
        body=body_html,
    )

def render_export_panel(
    document: LegalDocument,
    body_html: str,
    public_path: Optional[str],
) -> None:
    clean_html = build_standalone_html(document, body_html)
    st.markdown('<div id="aiq-legal-actions"></div>', unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.download_button(
            "Download Clean HTML",
            data=clean_html,
            file_name=document.filename,
            mime="text/html",
            use_container_width=True,
        )
    with c2:
        st.download_button(
            "Download Source Body",
            data=body_html,
            file_name=f"{Path(document.filename).stem}-body.html",
            mime="text/html",
            use_container_width=True,
        )
    with c3:
        if public_path:
            st.link_button("Open Public Page", public_path, use_container_width=True)
        else:
            st.button("Public Page Unavailable", disabled=True, use_container_width=True)
    with c4:
        st.markdown(
            '<button class="aiq-legal-native-button" onclick="window.print()">Print / Save PDF</button>',
            unsafe_allow_html=True,
        )
