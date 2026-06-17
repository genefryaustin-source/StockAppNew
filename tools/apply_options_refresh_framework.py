"""Apply professional options refresh framework to StockApp options modules.
Run from StockApp root: python tools/apply_options_refresh_framework.py
"""
from __future__ import annotations
from pathlib import Path
import re

ROOT = Path.cwd()
IMPORT_LINE = "from modules.options.options_refresh_framework import render_refresh_controls\n"


def backup(path: Path) -> None:
    bak = path.with_suffix(path.suffix + ".refresh_bak")
    if not bak.exists():
        bak.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")


def ensure_import(text: str) -> str:
    if "modules.options.options_refresh_framework" in text:
        return text
    return text.replace("import streamlit as st\n", "import streamlit as st\n" + IMPORT_LINE)


def insert_after_header(text: str, func_name: str, namespace: str, cache_prefixes: list[str]) -> str:
    marker = f'render_refresh_controls(\n        "{namespace}"'
    if marker in text:
        return text
    m = re.search(rf"(def {func_name}\([^\n]*\):\n(?:    .+\n)*?    st\.caption\([^\n]*\)\n)", text)
    if not m:
        m = re.search(rf"(def {func_name}\([^\n]*\):\n(?:    .+\n)*?    st\.subheader\([^\n]*\)\n)", text)
    if not m:
        print(f"skip {func_name}: insertion point not found")
        return text
    block = (
        "\n    refresh_state = render_refresh_controls(\n"
        f"        \"{namespace}\",\n"
        "        ticker if \"ticker\" in locals() else clean_ticker if \"clean_ticker\" in locals() else \"\",\n"
        f"        cache_prefixes={cache_prefixes!r},\n"
        "        default_mode=\"1 Minute\",\n"
        "    )\n\n"
    )
    return text[:m.end()] + block + text[m.end():]


def patch_file(path: Path, func_name: str, namespace: str, prefixes: list[str]) -> None:
    if not path.exists():
        print(f"missing {path}")
        return
    backup(path)
    text = ensure_import(path.read_text(encoding="utf-8"))
    text = insert_after_header(text, func_name, namespace, prefixes)
    text = text.replace("import uuid\n", "")
    text = re.sub(r'key=f"dealer_refresh_\{clean_ticker\}_\{uuid\.uuid4\(\)\.hex\[:8\]\}"', 'key=f"dealer_refresh_{clean_ticker}"', text)
    path.write_text(text, encoding="utf-8")
    print(f"patched {path}")


def patch_flow(path: Path) -> None:
    if not path.exists():
        print(f"missing {path}")
        return
    backup(path)
    text = ensure_import(path.read_text(encoding="utf-8"))
    old = '''    with col_ref:
        st.write("")
        if st.button("↺ Refresh", key="flow_refresh", use_container_width=True):
            keys = [k for k in st.session_state if k.startswith("flow_cache_")]
            for k in keys:
                del st.session_state[k]
            st.rerun()
'''
    new = '''    with col_ref:
        refresh_state = render_refresh_controls(
            "options_flow",
            ticker,
            cache_prefixes=["flow_cache_"],
            default_mode="1 Minute",
        )
        if refresh_state.force_refresh:
            try:
                from modules.options_flow import flow_service as _flow_service
                if hasattr(_flow_service, "_CACHE"):
                    _flow_service._CACHE.clear()
            except Exception:
                pass
'''
    text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")
    print(f"patched {path}")


def main() -> None:
    patch_flow(ROOT / "modules" / "options_flow" / "flow_ui.py")
    patch_file(ROOT / "modules" / "options" / "options_smart_money_dashboard.py", "render_options_smart_money_dashboard", "options_smart_money", ["options_smart_money_report_", "ai_smart_money_commentary_"])
    patch_file(ROOT / "modules" / "options" / "options_volatility_dashboard.py", "render_options_volatility_dashboard", "options_volatility", ["options_volatility_", "phase4_vol_"])
    patch_file(ROOT / "modules" / "options" / "options_dealer_analytics_dashboard.py", "render_options_dealer_analytics_dashboard", "options_dealer", ["dealer_exposure_report_", "dealer_ai_"])
    patch_file(ROOT / "modules" / "options" / "options_workstation_ui.py", "render_full_options_workstation", "options_workstation", ["expanded_chain_", "options_smart_money_report_", "dealer_exposure_report_"])
    print("done")


if __name__ == "__main__":
    main()
