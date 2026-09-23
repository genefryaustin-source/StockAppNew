from __future__ import annotations

from html import escape

import streamlit as st

from .legal_components import render_empty_state
from .legal_registry import categories
from .legal_search import search_documents, suggested_queries


SEARCH_HISTORY_KEY = "legal_portal_search_history"


def _add_history(query: str) -> None:
    history = list(st.session_state.get(SEARCH_HISTORY_KEY, []))
    normalized = " ".join((query or "").split()).strip()

    if not normalized:
        return

    history = [item for item in history if item.lower() != normalized.lower()]
    history.insert(0, normalized)
    st.session_state[SEARCH_HISTORY_KEY] = history[:8]


def render_search_panel(*, expanded: bool = False) -> None:
    with st.expander("Search the Legal Portal", expanded=expanded):
        search_col, filter_col = st.columns([3, 1])

        with search_col:
            query = st.text_input(
                "Search legal documents",
                key="legal_portal_search_query",
                placeholder="Search terms, disclosures, agreements, and policies",
            )

        with filter_col:
            selected_category = st.selectbox(
                "Category",
                options=["All categories", *categories()],
                key="legal_portal_search_category",
            )

        option_col, count_col = st.columns([2, 1])

        with option_col:
            require_all_terms = st.checkbox(
                "Require all search terms",
                value=False,
                key="legal_portal_search_require_all",
            )

        with count_col:
            limit = st.selectbox(
                "Maximum results",
                options=[10, 20, 30, 50],
                index=1,
                key="legal_portal_search_limit",
            )

        if not query:
            st.caption("Suggested searches")
            suggestion_columns = st.columns(4)

            for index, suggestion in enumerate(suggested_queries()):
                with suggestion_columns[index % len(suggestion_columns)]:
                    if st.button(
                        suggestion,
                        key=f"legal_search_suggestion_{index}",
                        use_container_width=True,
                    ):
                        st.session_state["legal_portal_search_query"] = suggestion
                        st.rerun()

            history = st.session_state.get(SEARCH_HISTORY_KEY, [])
            if history:
                st.caption("Recent searches")
                st.write(" | ".join(history))
            return

        _add_history(query)

        category = None if selected_category == "All categories" else selected_category

        results = search_documents(
            query,
            category=category,
            limit=limit,
            require_all_terms=require_all_terms,
        )

        if not results:
            render_empty_state(
                "No matching documents",
                "Try removing a filter, using fewer words, or searching for a broader legal topic.",
            )
            return

        st.caption(f"{len(results)} matching document(s)")

        for position, result in enumerate(results, start=1):
            matched = ", ".join(result.matched_terms)
            phrase_badge = (
                '<span class="aiq-legal-search-badge">Exact phrase</span>'
                if result.exact_phrase
                else ""
            )

            card_html = (
                '<article class="aiq-legal-search-card">'
                '<div class="aiq-legal-search-card-topline">'
                f'<span class="aiq-legal-search-rank">#{position}</span>'
                f'<span class="aiq-legal-search-category">{escape(result.document.category)}</span>'
                f'{phrase_badge}'
                '</div>'
                f'<h3>{escape(result.document.title)}</h3>'
                f'<p>{escape(result.snippet)}</p>'
                '<div class="aiq-legal-search-meta">'
                f'Matched: {escape(matched)} | Score: {result.score:.1f}'
                '</div>'
                '</article>'
            )

            st.markdown(card_html, unsafe_allow_html=True)

            if st.button(
                f"Open {result.document.title}",
                key=f"legal_search_result_{result.document.key}_{position}",
                use_container_width=True,
            ):
                st.query_params["legal_document"] = result.document.key
                st.rerun()
