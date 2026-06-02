import streamlit as st
import pandas as pd
from datetime import datetime, UTC

from modules.institutional.earnings import (
    ingest_massive_earnings,
    list_upcoming,
    fetch_earnings_transcript,
    store_transcript_and_chunks,
    query_transcript_with_llm,
    generate_comparison_table,
)


def _safe_eps(e):
    """
    Safely resolve EPS value from any possible column.
    """
    return (
        getattr(e, "eps_actual", None)
        or getattr(e, "eps_est", None)
        or getattr(e, "eps_estimate", None)
    )


def _safe_revenue(e):
    """
    Safely resolve revenue value from any possible column.
    """
    return (
        getattr(e, "rev_actual", None)
        or getattr(e, "revenue_actual", None)
        or getattr(e, "rev_est", None)
        or getattr(e, "revenue_estimate", None)
    )


def render_earnings(db, user):

    tenant_id = user["tenant_id"]

    st.subheader("Earnings Intelligence")

    # Tabs for different earnings features
    tab1, tab2, tab3, tab4 = st.tabs(
        ["Earnings Events", "Transcript Q&A", "Comparison", "Upload Transcript"]
    )

    # ================================================================
    # TAB 1: Earnings Events (Original)
    # ================================================================
    with tab1:
        st.markdown("### Massive Earnings")

        col1, col2 = st.columns([2, 1])
        with col1:
            symbol = st.text_input("Ticker", "AAPL", key="earnings_ticker").upper()
        with col2:
            if st.button("Fetch Earnings", type="primary", key="fetch_earnings_btn"):
                try:
                    inserted = ingest_massive_earnings(
                        db,
                        tenant_id,
                        symbol,
                    )

                    if inserted == 0:
                        st.warning("No earnings inserted (may already exist).")
                    else:
                        st.success(f"{inserted} earnings records inserted.")

                except Exception as e:
                    st.error(f"Earnings ingestion failed: {e}")

        events = list_upcoming(db, tenant_id)

        if not events:
            st.info("No earnings data ingested yet.")
        else:
            st.markdown("### Stored Earnings")

            for e in events:

                eps = _safe_eps(e)
                revenue = _safe_revenue(e)

                eps_display = f"{eps:.2f}" if isinstance(eps, (int, float)) else "N/A"

                if isinstance(revenue, (int, float)):
                    revenue_display = f"{revenue:,.0f}"
                else:
                    revenue_display = "N/A"

                has_transcript = "📄" if e.transcript_text else "🔳"

                st.write(
                    f"{has_transcript} **{e.symbol}** | {e.event_date.strftime('%Y-%m-%d')} | "
                    f"EPS: {eps_display} | Revenue: {revenue_display}"
                )

    # ================================================================
    # TAB 2: Transcript Q&A (NEW)
    # ================================================================
    with tab2:
        st.markdown("### Earnings Call Transcript AI Q&A")
        st.info(
            "Ask questions about earnings call transcripts. "
            "Responses include citations from the actual call."
        )

        col1, col2 = st.columns(2)
        with col1:
            qa_symbol = st.selectbox(
                "Select Company",
                options=[e.symbol for e in events if e.transcript_text],
                key="qa_symbol_select",
            )
        with col2:
            # Show date of transcript
            selected_event = next(
                (e for e in events if e.symbol == qa_symbol and e.transcript_text), None
            )
            if selected_event:
                st.markdown(f"**Date:** {selected_event.event_date.strftime('%Y-%m-%d')}")

        if not selected_event:
            st.warning("No transcript available for this company. Upload one first.")
        else:
            # AI Q&A Interface
            st.markdown("#### Ask a Question")
            user_query = st.text_area(
                "Your question about the earnings call:",
                placeholder="e.g., What were the main drivers of revenue growth? "
                "What guidance did management provide?",
                key="earnings_qa_input",
            )

            col1, col2 = st.columns(2)
            with col1:
                llm_choice = st.radio(
                    "LLM Provider:",
                    ["OpenAI (GPT-4)", "Anthropic (Claude)"],
                    horizontal=True,
                    key="llm_choice",
                )
            with col2:
                if st.button("Ask", type="primary", key="ask_btn"):
                    if not user_query.strip():
                        st.warning("Please enter a question.")
                    else:
                        with st.spinner("Analyzing transcript..."):
                            llm_provider = "openai" if "OpenAI" in llm_choice else "anthropic"
                            result = query_transcript_with_llm(
                                selected_event.transcript_text, user_query, llm_provider
                            )

                            if result:
                                st.markdown("### Answer")
                                st.write(result.get("answer", "No answer generated."))

                                citations = result.get("citations", [])
                                if citations:
                                    st.markdown("### Citations from Transcript")
                                    for i, citation in enumerate(citations, 1):
                                        st.caption(f"{i}. {citation[:200]}...")
                            else:
                                st.error("Failed to generate answer. Check API key settings.")

    # ================================================================
    # TAB 3: Comparison (NEW)
    # ================================================================
    with tab3:
        st.markdown("### Compare Across Companies")
        st.info(
            "Compare metrics across multiple earnings call transcripts. "
            "E.g., 'Compare AWS, Azure, and Google Cloud revenue growth'"
        )

        col1, col2 = st.columns([2, 1])
        with col1:
            symbols_input = st.text_input(
                "Symbols (comma-separated)",
                "AMZN, MSFT, GOOGL",
                key="comparison_symbols",
            )
            symbols = [s.strip().upper() for s in symbols_input.split(",") if s.strip()]
        with col2:
            st.markdown("**Format:** AMZN, MSFT, GOOGL")

        col1, col2 = st.columns(2)
        with col1:
            metric_choice = st.selectbox(
                "Metric to Compare",
                [
                    "Revenue Growth",
                    "Margin Expansion",
                    "Operating Expenses",
                    "Custom Query",
                ],
                key="metric_choice",
            )
        with col2:
            if metric_choice == "Custom Query":
                custom_query = st.text_input(
                    "Custom comparison query:",
                    placeholder="e.g., What were capital expenditure plans?",
                    key="custom_query_input",
                )
            else:
                custom_query = None

        if st.button("Generate Comparison", type="primary", key="compare_btn"):
            if not symbols:
                st.warning("Please enter at least one symbol.")
            else:
                with st.spinner("Generating comparison table..."):
                    metric_map = {
                        "Revenue Growth": "revenue_growth",
                        "Margin Expansion": "margin_expansion",
                        "Operating Expenses": "operating_expenses",
                    }
                    metric_key = metric_map.get(metric_choice, metric_choice.lower())
                    query = custom_query if custom_query else None

                    result = generate_comparison_table(
                        db, tenant_id, symbols, metric_key, query
                    )

                    if result:
                        st.markdown("### Comparison Table")
                        st.dataframe(
                            result["table"],
                            use_container_width=True,
                            hide_index=True,
                        )

                        citations = result.get("citations", {})
                        if any(citations.values()):
                            st.markdown("### Supporting Citations")
                            for symbol, quotes in citations.items():
                                if quotes:
                                    with st.expander(f"{symbol} - Citations"):
                                        for quote in quotes:
                                            st.caption(f'📎 "{quote}"')
                    else:
                        st.warning(
                            "No transcripts found for comparison. "
                            "Upload transcripts for these companies first."
                        )

    # ================================================================
    # TAB 4: Upload/Store Transcript (NEW)
    # ================================================================
    with tab4:
        st.markdown("### Add Earnings Call Transcript")

        col1, col2 = st.columns(2)
        with col1:
            upload_symbol = st.text_input(
                "Ticker", "AAPL", key="upload_ticker"
            ).upper()
        with col2:
            upload_date = st.date_input(
                "Earnings Date", key="upload_date"
            )

        transcript_url = st.text_input(
            "Transcript URL (optional)",
            placeholder="https://example.com/transcript",
            key="transcript_url_input",
        )

        transcript_source = st.selectbox(
            "Source",
            ["seeking_alpha", "investor_relations", "other"],
            key="transcript_source_select",
        )

        transcript_text = st.text_area(
            "Paste Transcript Text Here",
            height=300,
            placeholder="Paste the full earnings call transcript...",
            key="transcript_text_area",
        )

        if st.button("Store Transcript", type="primary", key="store_transcript_btn"):
            if not transcript_text.strip():
                st.warning("Please paste transcript text.")
            elif not upload_symbol:
                st.warning("Please enter a ticker.")
            else:
                with st.spinner("Processing transcript..."):
                    upload_datetime = datetime.combine(
                        upload_date, datetime.min.time()
                    ).replace(tzinfo=UTC)
                    
                    success, message = store_transcript_and_chunks(
                        db,
                        tenant_id,
                        upload_symbol,
                        upload_datetime,
                        transcript_text,
                        transcript_url if transcript_url else None,
                        transcript_source,
                    )

                    if success:
                        st.success(message)
                        st.info(
                            "✅ Transcript stored and ready for Q&A. "
                            "Go to 'Transcript Q&A' tab to ask questions."
                        )
                    else:
                        st.error(message)
