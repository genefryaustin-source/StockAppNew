from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

def render_shortcut_bridge() -> None:
    components.html(
        """
        <script>
        (() => {
          const parentDoc = window.parent.document;
          if (window.parent.__aiqLegalShortcutsInstalled) return;
          window.parent.__aiqLegalShortcutsInstalled = true;

          parentDoc.addEventListener("keydown", (event) => {
            const target = event.target;
            const typing = target && (
              target.tagName === "INPUT" ||
              target.tagName === "TEXTAREA" ||
              target.isContentEditable
            );

            if (event.key === "/" && !typing) {
              event.preventDefault();
              const search = [...parentDoc.querySelectorAll("input")]
                .find((input) => (input.placeholder || "").toLowerCase().includes("search"));
              if (search) {
                search.focus();
                search.scrollIntoView({behavior: "smooth", block: "center"});
              }
            }

            if (event.key === "Escape" && typing) target.blur();

            if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "p") {
              event.preventDefault();
              window.parent.print();
            }
          });
        })();
        </script>
        """,
        height=0,
        width=0,
    )

def render_shortcut_help() -> None:
    with st.popover("Keyboard shortcuts"):
        st.markdown(
            """
            - `/` — focus portal search
            - `Esc` — leave the active search field
            - `Ctrl+P` or `Cmd+P` — print or save as PDF
            """
        )
