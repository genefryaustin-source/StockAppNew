"""
modules/screener/nl_screener.py

Natural Language Stock Screener.

Translates plain-English queries like:
  "show me high-momentum tech stocks with low debt under $50"
  "find cheap value plays in healthcare with strong quality"
  "aggressive growth stocks, PE under 30, buy rated only"

...into the exact filter parameters that run_screener() accepts.

Uses Claude tool-use for guaranteed structured output.
Falls back gracefully with a helpful message if translation fails.

Integration — add to screener_ui.py render_screener():
    from modules.screener.nl_screener import render_nl_screener_input
    nl_filters = render_nl_screener_input(sectors)
    if nl_filters:
        # nl_filters is a dict ready to unpack into run_screener()
        results = run_screener(db=db, tenant_id=tenant_id,
                               symbols=symbols, **nl_filters)
"""

from __future__ import annotations

import json
import os
from typing import Optional

import streamlit as st


# ─────────────────────────────────────────────────────────────
# Available sectors (used in the tool schema description)
# ─────────────────────────────────────────────────────────────

_DEFAULT_SECTORS = [
    "Technology", "Healthcare", "Financial Services",
    "Consumer Cyclical", "Consumer Defensive", "Industrials",
    "Communication Services", "Energy", "Utilities",
    "Real Estate", "Basic Materials",
]

# ─────────────────────────────────────────────────────────────
# Tool schema
# ─────────────────────────────────────────────────────────────

def _build_tool(sectors: list[str]) -> dict:
    sector_list = ", ".join(f'"{s}"' for s in (sectors or _DEFAULT_SECTORS))
    return {
        "name": "submit_screener_filters",
        "description": (
            "Submit parsed screener filters from a natural language query. "
            "Only include fields that were clearly implied by the user's query. "
            "Leave everything else as null."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "min_price": {
                    "type": ["number", "null"],
                    "description": "Minimum stock price in USD. e.g. 'over $10' → 10",
                },
                "max_price": {
                    "type": ["number", "null"],
                    "description": "Maximum stock price in USD. e.g. 'under $50' → 50",
                },
                "min_volume": {
                    "type": ["number", "null"],
                    "description": "Minimum average daily volume. e.g. 'liquid stocks' → 500000",
                },
                "min_composite": {
                    "type": ["number", "null"],
                    "description": (
                        "Minimum composite score 0-100. "
                        "'high quality' or 'strong' → 70. 'top picks' → 80."
                    ),
                },
                "min_confidence": {
                    "type": ["number", "null"],
                    "description": "Minimum confidence score 0-100.",
                },
                "min_quality": {
                    "type": ["number", "null"],
                    "description": (
                        "Minimum quality score 0-100. "
                        "'high quality', 'strong balance sheet', 'profitable' → 65-75."
                    ),
                },
                "min_growth": {
                    "type": ["number", "null"],
                    "description": (
                        "Minimum growth score 0-100. "
                        "'high growth', 'fast growing', 'aggressive growth' → 65-75."
                    ),
                },
                "min_value": {
                    "type": ["number", "null"],
                    "description": (
                        "Minimum value score 0-100. "
                        "'value', 'cheap', 'low PE', 'undervalued' → 60-70."
                    ),
                },
                "min_momentum": {
                    "type": ["number", "null"],
                    "description": (
                        "Minimum momentum score 0-100. "
                        "'high momentum', 'trending up', 'breakout' → 65-75."
                    ),
                },
                "max_risk": {
                    "type": ["number", "null"],
                    "description": (
                        "Maximum risk score 0-100 (lower = safer). "
                        "'low risk', 'conservative', 'safe', 'low debt' → 40-50. "
                        "'high risk', 'speculative' → 80-90."
                    ),
                },
                "sector": {
                    "type": ["string", "null"],
                    "description": (
                        f"Exact sector name. Must be one of: {sector_list}. "
                        "Map 'tech' → 'Technology', 'healthcare' → 'Healthcare', etc."
                    ),
                },
                "rating_in": {
                    "type": ["array", "null"],
                    "items": {"type": "string", "enum": ["Buy", "Hold", "Sell", "N/A"]},
                    "description": (
                        "'buy rated' → ['Buy']. "
                        "'buy or hold' → ['Buy', 'Hold']. "
                        "If not mentioned, return null (not an empty array)."
                    ),
                },
                "limit": {
                    "type": ["integer", "null"],
                    "description": (
                        "Max results to return. "
                        "'top 10' → 10, 'top 25' → 25. Default null (use system default)."
                    ),
                },
                "plain_english_summary": {
                    "type": "string",
                    "description": (
                        "1 sentence confirming what filters were applied, "
                        "e.g. 'Showing buy-rated technology stocks priced under $50 "
                        "with high momentum (≥70) and low risk (≤45).'"
                    ),
                },
                "warnings": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "List any parts of the query that couldn't be mapped to a filter, "
                        "or any ambiguous interpretations. Empty array if all clear."
                    ),
                },
            },
            "required": ["plain_english_summary", "warnings"],
        },
    }


# ─────────────────────────────────────────────────────────────
# Core translation function
# ─────────────────────────────────────────────────────────────

def translate_query(
    query: str,
    sectors: Optional[list[str]] = None,
) -> dict:
    """
    Translate a natural language query into run_screener() parameters.

    Returns a dict with keys matching run_screener's kwargs plus:
        _summary  : str   — plain-English confirmation of filters
        _warnings : list  — any unmapped or ambiguous parts
        _error    : str | None
    """
    if not query or not query.strip():
        return {"_error": "Empty query.", "_summary": "", "_warnings": []}

    try:
        import anthropic
        from modules.admin.tenant_api_keys import get_provider_key
        key = get_provider_key("ANTHROPIC_API_KEY")
        if not key:
            raise EnvironmentError("ANTHROPIC_API_KEY not set.")
        client = anthropic.Anthropic(api_key=key)
    except Exception as e:
        return {"_error": str(e), "_summary": "", "_warnings": []}

    tool = _build_tool(sectors or _DEFAULT_SECTORS)

    system = (
        "You are a financial data expert helping translate investor queries into "
        "structured stock screener filters. "
        "Be conservative — only set a filter if the user clearly implied it. "
        "Do not add filters the user didn't mention. "
        "Scores are 0-100. Risk score is inverted: higher = riskier. "
        "You must call the submit_screener_filters tool."
    )

    user_msg = (
        f"Translate this stock screener query into filters:\n\n"
        f"\"{query}\"\n\n"
        f"Available sectors: {', '.join(sectors or _DEFAULT_SECTORS)}\n"
        f"Score fields (composite, confidence, quality, growth, value, momentum) "
        f"are 0-100 where 100 is best. Risk is 0-100 where 100 is most risky.\n"
        f"Only set filters clearly implied by the query."
    )

    try:
        message = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=512,
            system=system,
            tools=[tool],
            tool_choice={"type": "tool", "name": "submit_screener_filters"},
            messages=[{"role": "user", "content": user_msg}],
        )

        for block in message.content:
            if block.type == "tool_use" and block.name == "submit_screener_filters":
                raw = block.input

                # Extract summary and warnings, remove from filter dict
                summary  = raw.pop("plain_english_summary", "")
                warnings = raw.pop("warnings", [])

                # Remove null values — run_screener treats None as "no filter"
                filters = {k: v for k, v in raw.items() if v is not None}

                filters["_summary"]  = summary
                filters["_warnings"] = warnings
                filters["_error"]    = None
                return filters

        return {"_error": "No filters returned.", "_summary": "", "_warnings": []}

    except Exception as e:
        return {"_error": str(e), "_summary": "", "_warnings": []}


# ─────────────────────────────────────────────────────────────
# Streamlit UI component
# ─────────────────────────────────────────────────────────────

# Example queries shown to the user
_EXAMPLES = [
    "High-momentum tech stocks under $100 with buy rating",
    "Cheap value plays in healthcare, low risk, PE under 20",
    "Aggressive growth stocks with strong quality, top 25 results",
    "Defensive consumer stocks, low volatility, confidence over 70",
    "Undervalued energy stocks with high composite score",
    "Show me financial stocks with strong momentum and low risk",
]


def render_nl_screener_input(sectors: Optional[list[str]] = None) -> Optional[dict]:
    """
    Renders the natural language screener input bar.

    Returns a dict of run_screener kwargs if the user submitted a query,
    or None if no query has been submitted yet.

    The returned dict is ready to unpack:
        results = run_screener(db=db, tenant_id=tid,
                               symbols=syms, **nl_filters)

    Note: 'max_price' is returned if specified — add a price ceiling
    filter to run_screener if you want to support it, or apply it
    as a post-filter on results.
    """

    st.markdown("#### 🔍 Natural Language Screener")
    st.caption(
        "Describe what you're looking for in plain English. "
        "Claude will translate it into filters automatically."
    )

    # Example chips
    with st.expander("💡 Example queries", expanded=False):
        cols = st.columns(2)
        for i, ex in enumerate(_EXAMPLES):
            with cols[i % 2]:
                if st.button(ex, key=f"nl_example_{i}", use_container_width=True):
                    st.session_state["nl_query_input"] = ex

    # Query input
    query = st.text_input(
        "Describe the stocks you want",
        placeholder="e.g. high-momentum tech stocks with strong quality under $150",
        key="nl_query_input",
        label_visibility="collapsed",
    )

    col_search, col_clear = st.columns([1, 4])
    with col_search:
        search_btn = st.button(
            "🔍 Search",
            key="nl_search_btn",
            type="primary",
            use_container_width=True,
        )
    with col_clear:
        if st.button("✕ Clear", key="nl_clear_btn"):
            if "nl_query_input" in st.session_state:
                del st.session_state["nl_query_input"]
            if "nl_filters" in st.session_state:
                del st.session_state["nl_filters"]
            st.rerun()

    if search_btn and query and query.strip():
        with st.spinner("Translating query…"):
            filters = translate_query(query, sectors)
            st.session_state["nl_filters"] = filters
            st.session_state["nl_last_query"] = query

    filters = st.session_state.get("nl_filters")

    if not filters:
        return None

    # Show error
    if filters.get("_error"):
        st.error(f"Could not translate query: {filters['_error']}")
        return None

    # Show confirmation
    summary = filters.get("_summary", "")
    if summary:
        st.success(f"✅ {summary}")

    # Show warnings
    for w in filters.get("_warnings", []):
        st.warning(f"⚠️ {w}")

    # Show parsed filters as a readable badge row
    _render_filter_badges(filters)

    # Return only the run_screener-compatible keys
    screener_keys = {
        "min_price", "min_volume", "min_composite", "min_confidence",
        "min_quality", "min_growth", "min_value", "min_momentum",
        "max_risk", "sector", "rating_in", "limit",
    }
    result = {k: v for k, v in filters.items() if k in screener_keys}
    # Carry max_price separately — apply as post-filter
    if "max_price" in filters:
        result["_max_price"] = filters["max_price"]

    return result if result else None


def _render_filter_badges(filters: dict):
    """Render a compact row of filter chips showing what was parsed."""
    badge_map = {
        "min_price":      lambda v: f"Price ≥ ${v:,.0f}",
        "max_price":      lambda v: f"Price ≤ ${v:,.0f}",
        "min_volume":     lambda v: f"Vol ≥ {v/1e6:.1f}M",
        "min_composite":  lambda v: f"Composite ≥ {v:.0f}",
        "min_confidence": lambda v: f"Confidence ≥ {v:.0f}",
        "min_quality":    lambda v: f"Quality ≥ {v:.0f}",
        "min_growth":     lambda v: f"Growth ≥ {v:.0f}",
        "min_value":      lambda v: f"Value ≥ {v:.0f}",
        "min_momentum":   lambda v: f"Momentum ≥ {v:.0f}",
        "max_risk":       lambda v: f"Risk ≤ {v:.0f}",
        "sector":         lambda v: f"Sector: {v}",
        "rating_in":      lambda v: f"Rating: {'/'.join(v)}",
        "limit":          lambda v: f"Top {v}",
    }

    badges = []
    for key, fmt in badge_map.items():
        val = filters.get(key)
        if val is not None:
            try:
                badges.append(fmt(val))
            except Exception:
                pass

    if badges:
        st.markdown(
            " &nbsp;·&nbsp; ".join(
                f"<code>{b}</code>" for b in badges
            ),
            unsafe_allow_html=True,
        )
        st.markdown("")