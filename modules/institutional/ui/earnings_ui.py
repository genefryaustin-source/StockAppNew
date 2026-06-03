import streamlit as st
import pandas as pd
from datetime import datetime, UTC

from modules.institutional.earnings import (
    ingest_massive_earnings,
    list_upcoming,
    fetch_earnings_transcript,
    fetch_earnings_transcript_result,
    get_latest_transcript_event,
    store_transcript_and_chunks,
    query_transcript_with_llm,
    generate_comparison_table,
    provider_status,
)


def _safe_eps(e):
    return (
        getattr(e, "eps_actual", None)
        or getattr(e, "eps_est", None)
        or getattr(e, "eps_estimate", None)
    )


def _safe_revenue(e):
    return (
        getattr(e, "rev_actual", None)
        or getattr(e, "revenue_actual", None)
        or getattr(e, "rev_est", None)
        or getattr(e, "revenue_estimate", None)
    )


def _render_provider_status():
    with st.expander("Transcript Provider Status", expanded=False):
        providers = provider_status()

        if providers:
            st.dataframe(
                pd.DataFrame(providers),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No transcript providers registered.")


def _render_transcript_debug(result):
    if not result:
        return

    with st.expander("Transcript Load Details", expanded=False):
        st.json(
            {
                "success": result.get("success"),
                "symbol": result.get("symbol"),
                "source": result.get("source"),
                "cached": result.get("cached"),
                "message": result.get("message"),
                "transcript_chars": result.get("transcript_chars"),
                "provider_attempts": result.get("provider_attempts", []),
            }
        )


def render_earnings(db, user):
    tenant_id = user["tenant_id"]

    st.subheader("Earnings Intelligence")

    tab1, tab2, tab3, tab4 = st.tabs(
        ["Earnings Events", "Transcript Q&A", "Comparison", "Upload Transcript"]
    )

    # ================================================================
    # TAB 1: Earnings Events
    # ================================================================
    with tab1:
        st.markdown("### Massive Earnings")

        col1, col2 = st.columns([2, 1])

        with col1:
            symbol = st.text_input(
                "Ticker",
                "AAPL",
                key="earnings_ticker",
            ).upper().strip()

        with col2:
            if st.button("Fetch Earnings", type="primary", key="fetch_earnings_btn"):
                try:
                    inserted = ingest_massive_earnings(
                        db,
                        tenant_id,
                        symbol,
                    )

                    if inserted == 0:
                        st.warning("No earnings inserted; records may already exist.")
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

                has_transcript = "📄" if getattr(e, "transcript_text", None) else "🔳"

                st.write(
                    f"{has_transcript} **{e.symbol}** | "
                    f"{e.event_date.strftime('%Y-%m-%d')} | "
                    f"EPS: {eps_display} | Revenue: {revenue_display}"
                )

    # ================================================================
    # TAB 2: Transcript Q&A
    # ================================================================
    with tab2:
        st.markdown("### Earnings Call Transcript AI Q&A")
        st.info(
            "Enter a ticker, load the latest available transcript from the provider registry, "
            "then ask OpenAI or Anthropic questions about the actual call."
        )

        _render_provider_status()

        col1, col2, col3 = st.columns([2, 1, 1])

        with col1:
            qa_symbol = st.text_input(
                "Symbol",
                value=st.session_state.get("earnings_qa_symbol_value", "AAPL"),
                key="earnings_qa_symbol_input",
            ).upper().strip()
            st.session_state["earnings_qa_symbol_value"] = qa_symbol

        with col2:
            force_refresh = st.checkbox(
                "Force provider refresh",
                value=False,
                key="earnings_force_transcript_refresh",
            )

        with col3:
            load_clicked = st.button(
                "Load Latest Transcript",
                type="primary",
                key="load_latest_transcript_btn",
                use_container_width=True,
            )

        transcript_result = None

        if load_clicked:
            if not qa_symbol:
                st.warning("Enter a symbol first.")
            else:
                with st.spinner(f"Loading transcript for {qa_symbol}..."):
                    transcript_result = fetch_earnings_transcript_result(
                        db=db,
                        tenant_id=tenant_id,
                        symbol=qa_symbol,
                        force_refresh=force_refresh,
                    )

                    st.session_state["earnings_latest_transcript_result"] = transcript_result

                    if transcript_result.get("success"):
                        st.success(transcript_result.get("message", "Transcript loaded."))
                    else:
                        st.error(transcript_result.get("message", "Transcript could not be loaded."))

        transcript_result = st.session_state.get("earnings_latest_transcript_result")

        if transcript_result and transcript_result.get("symbol") == qa_symbol:
            _render_transcript_debug(transcript_result)

        selected_event = get_latest_transcript_event(
            db,
            tenant_id,
            qa_symbol,
        ) if qa_symbol else None

        transcript_text = None

        if selected_event and getattr(selected_event, "transcript_text", None):
            transcript_text = selected_event.transcript_text

            st.markdown(
                f"**Cached Transcript:** {qa_symbol} | "
                f"Date: {selected_event.event_date.strftime('%Y-%m-%d')} | "
                f"Source: {getattr(selected_event, 'transcript_source', 'cache') or 'cache'} | "
                f"Characters: {len(transcript_text):,}"
            )

            with st.expander("Transcript Preview", expanded=False):
                st.text((transcript_text or "")[:3000])

        else:
            st.warning(
                f"No cached transcript found for {qa_symbol}. "
                "Click **Load Latest Transcript** or use the Upload Transcript tab."
            )

        st.markdown("#### Ask a Question")

        user_query = st.text_area(
            "Your question about the earnings call:",
            placeholder=(
                "Examples: What were the main drivers of revenue growth? "
                "What guidance did management provide? "
                "How did margins perform relative to expectations?"
            ),
            key="earnings_qa_input",
            height=120,
        )

        col1, col2 = st.columns([2, 1])

        with col1:
            llm_choice = st.radio(
                "LLM Provider:",
                ["OpenAI (GPT-4)", "Anthropic (Claude)"],
                horizontal=True,
                key="llm_choice",
            )

        with col2:
            ask_clicked = st.button(
                "Ask",
                type="primary",
                key="ask_btn",
                use_container_width=True,
            )

        if ask_clicked:
            if not qa_symbol:
                st.warning("Enter a symbol first.")
            elif not user_query.strip():
                st.warning("Please enter a question.")
            else:
                with st.spinner("Preparing transcript..."):
                    if not transcript_text:
                        # Auto-load transcript when the user asks.
                        auto_result = fetch_earnings_transcript_result(
                            db=db,
                            tenant_id=tenant_id,
                            symbol=qa_symbol,
                            force_refresh=False,
                        )
                        st.session_state["earnings_latest_transcript_result"] = auto_result

                        if auto_result.get("success"):
                            transcript_text = auto_result.get("transcript_text")
                        else:
                            st.error(auto_result.get("message", "Transcript could not be loaded."))
                            _render_transcript_debug(auto_result)
                            st.stop()

                if not transcript_text:
                    st.error("No transcript text is available for AI analysis.")
                    st.stop()

                with st.spinner("Analyzing transcript..."):
                    llm_provider = "openai" if "OpenAI" in llm_choice else "anthropic"

                    result = query_transcript_with_llm(
                        transcript_text,
                        user_query,
                        llm_provider,
                    )

                    if result:
                        if result.get("error"):
                            st.error(result.get("answer", "AI provider returned an error."))
                            with st.expander("Error Details", expanded=False):
                                st.json(result)
                        else:
                            st.markdown("### Answer")
                            st.write(result.get("answer", "No answer generated."))

                            citations = result.get("citations", [])

                            if citations:
                                st.markdown("### Citations from Transcript")
                                for i, citation in enumerate(citations, 1):
                                    st.caption(f"{i}. {citation[:500]}...")
                    else:
                        st.error("Failed to generate answer. Check API key settings.")

    # ================================================================
    # TAB 3: Comparison
    # ================================================================
    with tab3:
        st.markdown("### Compare Across Companies")
        st.info(
            "Compare metrics across multiple earnings call transcripts. "
            "The app will use cached transcripts first and then provider lookup."
        )

        col1, col2 = st.columns([2, 1])

        with col1:
            symbols_input = st.text_input(
                "Symbols (comma-separated)",
                "AMZN, MSFT, GOOGL",
                key="comparison_symbols",
            )
            symbols = [
                s.strip().upper()
                for s in symbols_input.split(",")
                if s.strip()
            ]

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
            llm_choice_compare = st.radio(
                "LLM Provider",
                ["OpenAI (GPT-4)", "Anthropic (Claude)"],
                horizontal=True,
                key="comparison_llm_choice",
            )

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
                    llm_provider = "openai" if "OpenAI" in llm_choice_compare else "anthropic"

                    result = generate_comparison_table(
                        db,
                        tenant_id,
                        symbols,
                        metric_key,
                        query,
                        llm_provider=llm_provider,
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
                            "Load or upload transcripts for these companies first."
                        )

    # ================================================================
    # TAB 4: Upload/Store Transcript
    # ================================================================
    with tab4:
        st.markdown("### Add Earnings Call Transcript")
        st.info(
            "Use this when providers do not return a transcript. "
            "Paste the full transcript once and it will be cached for future Q&A."
        )

        col1, col2 = st.columns(2)

        with col1:
            upload_symbol = st.text_input(
                "Ticker",
                "AAPL",
                key="upload_ticker",
            ).upper().strip()

        with col2:
            upload_date = st.date_input(
                "Earnings Date",
                key="upload_date",
            )

        transcript_url = st.text_input(
            "Transcript URL (optional)",
            placeholder="https://example.com/transcript",
            key="transcript_url_input",
        )

        transcript_source = st.selectbox(
            "Source",
            ["manual", "seeking_alpha", "investor_relations", "roic", "quartr", "other"],
            key="transcript_source_select",
        )

        transcript_text = st.text_area(
            "Paste Transcript Text Here",
            height=350,
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
                        upload_date,
                        datetime.min.time(),
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
