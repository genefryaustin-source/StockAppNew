# ============================================================
# modules/preipo/preipo_ui.py
# Pre-IPO Intelligence Center UI
# ============================================================

from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.ipo.news_ui import render_news_sentiment_tab
from modules.preipo.service import (
    add_manual_preipo_company,
    add_preipo_filing_to_watchlist,
    add_preipo_watchlist_item,
    enrich_preipo_filings_dataframe,
    list_preipo_companies,
    list_preipo_filings,
    list_preipo_watchlist,
    preipo_companies_to_dataframe,
    preipo_discovery_metrics,
    preipo_filings_to_dataframe,
    preipo_intelligence_summary_metrics,
    preipo_maturity_breakdown,
    preipo_pipeline_funnel,
    preipo_probability_distribution,
    preipo_sector_breakdown,
    preipo_underwriter_leaderboard,
    refresh_recent_sec_discovery,
    refresh_sec_filings_for_company,
    top_preipo_candidates_from_filings,
)


def _fmt_money(value):
    try:
        if value is None or pd.isna(value):
            return "N/A"
        value = float(value)
        if abs(value) >= 1_000_000_000:
            return f"${value / 1_000_000_000:,.2f}B"
        if abs(value) >= 1_000_000:
            return f"${value / 1_000_000:,.2f}M"
        return f"${value:,.0f}"
    except Exception:
        return "N/A"


def _show_sec_link(url):
    if not url:
        return ""
    return str(url)


def _load_discovered_filings(db, tenant_id, limit=1000):
    filings = list_preipo_filings(
        db=db,
        tenant_id=tenant_id,
        form_type="All",
        search="",
        spac_only=False,
        limit=limit,
    )
    filing_df = preipo_filings_to_dataframe(filings)
    return enrich_preipo_filings_dataframe(filing_df)


def _format_date_columns(df):
    out = df.copy()
    for col in ["Filing Date", "Funding Date", "Created"]:
        if col in out.columns:
            out[col] = pd.to_datetime(out[col], errors="coerce").dt.strftime("%Y-%m-%d")
    if "SEC Link" in out.columns:
        out["SEC Link"] = out["SEC Link"].apply(_show_sec_link)
    return out


def render_preipo_center(db, user):

    tenant_id = user.get("tenant_id", "default_tenant")
    user_id = user.get("user_id") or user.get("id") or user.get("email")

    st.header("Pre-IPO Intelligence Center")
    st.caption(
        "SEC S-1/F-1/SPAC discovery · IPO probability scoring · opportunity ranking · public-data pre-IPO intelligence"
    )

    tab_intelligence, tab_discovery, tab_pipeline, tab_add, tab_lookup, tab_watch, tab_news = st.tabs([
        "IPO Intelligence",
        "SEC Discovery",
        "Pre-IPO Pipeline",
        "Add Company",
        "Company SEC Lookup",
        "Watchlist",
        "📰 News & Sentiment",
    ])

    # ========================================================
    # IPO INTELLIGENCE LANDING TAB
    # ========================================================
    with tab_intelligence:
        st.markdown("### IPO Intelligence Dashboard")
        st.caption(
            "Ranks discovered SEC filings by IPO probability, opportunity score, maturity stage, timeline estimate, sector, and SPAC classification."
        )

        filing_df = _load_discovered_filings(db, tenant_id, limit=1000)
        metrics = preipo_intelligence_summary_metrics(filing_df)

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total IPO Candidates", metrics["total_candidates"])
        k2.metric("Highest IPO Probability", f'{metrics["highest_probability"]:.0f}%')
        k3.metric("Average IPO Probability", f'{metrics["avg_probability"]:.1f}%')
        k4.metric("Near-Term IPOs", metrics["near_term"])

        k5, k6, k7, k8 = st.columns(4)
        k5.metric("Pricing Stage", metrics["pricing_stage"])
        k6.metric("SPAC Candidates", metrics["spac"])
        k7.metric("Tier-1 Underwriter Signals", metrics["tier1_underwriters"])
        k8.metric("Top Sector", metrics["top_sector"])

        st.divider()

        st.markdown("### Most Likely IPO Candidates")
        top_df = top_preipo_candidates_from_filings(filing_df, limit=30, min_probability=0)

        if top_df.empty:
            st.info("No IPO intelligence candidates available yet. Run SEC Discovery first.")
        else:
            top_df = _format_date_columns(top_df)
            st.dataframe(top_df, use_container_width=True, hide_index=True)

        st.divider()

        st.markdown("### Most Recent High-Probability Candidates")
        high_df = top_preipo_candidates_from_filings(filing_df, limit=25, min_probability=70)
        if high_df.empty:
            st.info("No candidates currently meet the 70+ probability threshold.")
        else:
            high_df = _format_date_columns(high_df)
            st.dataframe(high_df, use_container_width=True, hide_index=True)

        st.divider()

        f1, f2 = st.columns(2)
        with f1:
            st.markdown("### IPO Pipeline Funnel")
            funnel_df = preipo_pipeline_funnel(filing_df)
            if funnel_df.empty:
                st.info("No funnel data yet.")
            else:
                st.bar_chart(funnel_df.set_index("Stage"))

        with f2:
            st.markdown("### IPO Maturity Stage")
            maturity_df = preipo_maturity_breakdown(filing_df)
            if maturity_df.empty:
                st.info("No maturity data yet.")
            else:
                st.bar_chart(maturity_df.set_index("Stage"))

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### Sector Breakdown")
            sector_df = preipo_sector_breakdown(filing_df)
            if sector_df.empty:
                st.info("No sector data yet.")
            else:
                st.bar_chart(sector_df.set_index("Sector"))

        with c2:
            st.markdown("### IPO Probability Heatmap")
            distribution_df = preipo_probability_distribution(filing_df)
            if distribution_df.empty:
                st.info("No probability distribution yet.")
            else:
                st.bar_chart(distribution_df.set_index("Range"))

        st.divider()

        st.markdown("### Underwriter Leaderboard")
        underwriter_df = preipo_underwriter_leaderboard(filing_df)
        if underwriter_df.empty:
            st.info("No underwriter signals detected yet. This requires underwriter names in the SEC filing metadata or extracted filing text.")
        else:
            st.dataframe(underwriter_df.head(25), use_container_width=True, hide_index=True)

        st.divider()

        st.markdown("### Full IPO Intelligence Table")
        if filing_df.empty:
            st.info("No filings available.")
        else:
            visible_cols = [
                "Company",
                "Form",
                "Filing Date",
                "IPO Probability",
                "IPO Opportunity Score",
                "IPO Maturity Stage",
                "Timeline Estimate",
                "Sector",
                "SPAC Classification",
                "Underwriters",
                "Underwriter Strength",
                "Signal Summary",
                "SEC Link",
            ]
            visible_cols = [col for col in visible_cols if col in filing_df.columns]
            display_df = _format_date_columns(filing_df[visible_cols])
            st.dataframe(display_df, use_container_width=True, hide_index=True)

    # ========================================================
    # SEC DISCOVERY
    # ========================================================
    with tab_discovery:
        st.markdown("### Recent SEC IPO/SPAC Filing Discovery")
        st.caption(
            "Refreshes recent EDGAR filings and surfaces companies entering the IPO/SPAC pipeline."
        )

        c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
        days = c1.number_input("Lookback Days", min_value=1, max_value=365, value=90, step=15)
        form_filter = c2.selectbox(
            "Form Type",
            ["All", "S-1", "S-1/A", "F-1", "F-1/A", "424B4", "424B3", "S-4", "S-4/A", "SPAC"],
            index=0,
        )
        limit = c3.number_input("Max Results", min_value=25, max_value=1000, value=300, step=25)

        if c4.button("Refresh SEC Discovery", type="primary", use_container_width=True):
            with st.spinner("Scanning SEC EDGAR for IPO/SPAC filings..."):
                try:
                    result = refresh_recent_sec_discovery(
                        db=db,
                        tenant_id=tenant_id,
                        days=int(days),
                        form_type=form_filter,
                        limit=int(limit),
                    )
                    st.success(
                        f"SEC discovery complete: fetched {result['fetched']}, "
                        f"saved {result['saved']}, updated {result['updated']}, "
                        f"companies {result['companies']}."
                    )
                except Exception as e:
                    try:
                        db.rollback()
                    except Exception:
                        pass
                    st.error(f"SEC discovery failed: {e}")

        f1, f2, f3 = st.columns([1, 3, 1])
        view_form = f1.selectbox(
            "View Form",
            ["All", "S-1", "S-1/A", "F-1", "F-1/A", "424B4", "424B3", "S-4", "S-4/A", "SPAC"],
            index=0,
            key="preipo_discovery_view_form",
        )
        search = f2.text_input("Search discovered company, form, or accession", "")
        spac_only = f3.checkbox("SPAC Only", value=(view_form == "SPAC"))

        filings = list_preipo_filings(
            db=db,
            tenant_id=tenant_id,
            form_type=view_form,
            search=search,
            spac_only=spac_only,
            limit=500,
        )
        filing_df = preipo_filings_to_dataframe(filings)
        filing_df = enrich_preipo_filings_dataframe(filing_df)
        metrics = preipo_discovery_metrics(filing_df)

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Recent Filings", metrics["count"])
        m2.metric("S-1", metrics["s1"])
        m3.metric("F-1", metrics["f1"])
        m4.metric("SPAC", metrics["spac"])
        m5.metric("Amendments", metrics["amended"])

        if filing_df.empty:
            st.info("No discovered SEC filings yet. Click Refresh SEC Discovery to populate this list.")
        else:
            st.markdown("### Most Likely IPO Candidates")
            top_candidates = top_preipo_candidates_from_filings(filing_df, limit=15, min_probability=0)
            st.dataframe(_format_date_columns(top_candidates), use_container_width=True, hide_index=True)

            st.markdown("### Discovered SEC Filings")
            display_df = _format_date_columns(filing_df.copy())
            st.dataframe(display_df.drop(columns=["ID"], errors="ignore"), use_container_width=True, hide_index=True)

            st.markdown("### Add Discovered Filing to Watchlist")
            options = [f"{f.company_name} | {f.filing_type or 'N/A'} | {f.id}" for f in filings]
            selected = st.selectbox("Select filing", options, key="preipo_discovery_select") if options else None
            notes = st.text_area("Watchlist notes", "", height=80, key="preipo_discovery_notes")
            if st.button("Add Selected Filing to Watchlist", use_container_width=True):
                selected_id = selected.split("|")[-1].strip() if selected else None
                if selected_id:
                    ok = add_preipo_filing_to_watchlist(db, tenant_id, user_id, selected_id, notes=notes)
                    st.success("Added to Pre-IPO watchlist." if ok else "Unable to add filing.")
                    st.rerun()

    # ========================================================
    # PRE-IPO PIPELINE
    # ========================================================
    with tab_pipeline:
        f1, f2 = st.columns([2, 1])
        search = f1.text_input("Search company, ticker hint, or sector", "")
        min_score = f2.slider("Minimum IPO probability", 0, 100, 0, 5)

        companies = list_preipo_companies(db, tenant_id, search=search, min_score=min_score, limit=500)
        df = preipo_companies_to_dataframe(companies)

        if not df.empty:
            for fallback_col in ["IPO Probability", "Readiness", "Confidence"]:
                if fallback_col in df.columns:
                    df[fallback_col] = pd.to_numeric(df[fallback_col], errors="coerce").fillna(0).round(1)

        if df.empty:
            st.info("No pre-IPO companies yet. Run SEC Discovery or add a company manually.")
        else:
            show_df = df.drop(columns=["ID"], errors="ignore").copy()
            for col in ["Last Valuation", "Last Funding"]:
                if col in show_df.columns:
                    show_df[col] = show_df[col].apply(_fmt_money)
            st.dataframe(show_df, use_container_width=True, hide_index=True)

            st.markdown("### Add to Watchlist")
            options = [f"{c.company_name} | {c.ipo_probability_score or 0:.0f} | {c.id}" for c in companies]
            selected = st.selectbox("Select company", options) if options else None
            notes = st.text_area("Watchlist notes", "", height=80)
            if st.button("Add Selected Pre-IPO Company", use_container_width=True):
                selected_id = selected.split("|")[-1].strip() if selected else None
                company = next((c for c in companies if c.id == selected_id), None)
                if company:
                    add_preipo_watchlist_item(db, tenant_id, user_id, company, notes=notes)
                    st.success("Added to Pre-IPO watchlist.")
                    st.rerun()

    # ========================================================
    # ADD COMPANY
    # ========================================================
    with tab_add:
        st.markdown("### Add public/private-market company signal")
        c1, c2 = st.columns(2)
        company_name = c1.text_input("Company Name")
        ticker_hint = c2.text_input("Ticker Hint")
        sector = c1.text_input("Sector")
        industry = c2.text_input("Industry")
        valuation = c1.number_input("Last Known Valuation", min_value=0.0, value=0.0, step=1_000_000.0)
        funding = c2.number_input("Last Funding Amount", min_value=0.0, value=0.0, step=1_000_000.0)
        round_name = c1.text_input("Last Funding Round")
        lead_investors = c2.text_input("Lead Investors")
        source = st.text_input("Source", value="MANUAL")

        if st.button("Save Pre-IPO Company", type="primary"):
            if not company_name.strip():
                st.warning("Company name is required.")
            else:
                add_manual_preipo_company(db, tenant_id, {
                    "company_name": company_name,
                    "ticker_hint": ticker_hint or None,
                    "sector": sector or None,
                    "industry": industry or None,
                    "last_known_valuation": valuation or None,
                    "last_funding_amount": funding or None,
                    "last_funding_round": round_name or None,
                    "lead_investors": lead_investors or None,
                    "source": source or "MANUAL",
                })
                st.success("Pre-IPO company saved.")
                st.rerun()

    # ========================================================
    # COMPANY LOOKUP
    # ========================================================
    with tab_lookup:
        st.markdown("### Company SEC EDGAR Filing Lookup")
        st.caption("Use this when you already know the company name or ticker.")
        query = st.text_input("Company search", placeholder="Example: Reddit, Stripe, Arm")
        if st.button("Search and Save IPO Filings"):
            if not query.strip():
                st.warning("Enter a company name.")
            else:
                with st.spinner("Searching SEC EDGAR..."):
                    try:
                        result = refresh_sec_filings_for_company(db, tenant_id, query)
                        st.success(
                            f"SEC search complete: matches {result['matches']}, "
                            f"filings saved {result['filings_saved']}, updated {result['filings_updated']}."
                        )
                    except Exception as e:
                        try:
                            db.rollback()
                        except Exception:
                            pass
                        st.error(f"SEC search failed: {e}")

    # ========================================================
    # WATCHLIST
    # ========================================================
    with tab_watch:
        items = list_preipo_watchlist(db, tenant_id, user_id)
        if not items:
            st.info("No pre-IPO companies on your watchlist yet.")
        else:
            rows = []
            filing_df = _load_discovered_filings(db, tenant_id, limit=1000)
            for item in items:
                match = pd.DataFrame()
                if not filing_df.empty and "Company" in filing_df.columns:
                    match = filing_df[
                        filing_df["Company"].fillna("").str.upper() == str(item.company_name or "").upper()
                    ].head(1)

                latest = match.iloc[0].to_dict() if not match.empty else {}
                rows.append({
                    "Company": item.company_name,
                    "Status": item.status,
                    "Probability": latest.get("IPO Probability"),
                    "Opportunity Score": latest.get("IPO Opportunity Score"),
                    "Window": latest.get("Timeline Estimate"),
                    "Sector": latest.get("Sector"),
                    "Latest Filing": latest.get("Form"),
                    "Alerts": item.alert_enabled,
                    "Notes": item.notes,
                    "Created": item.created_at,
                })

            watch_df = _format_date_columns(pd.DataFrame(rows))
            st.dataframe(watch_df, use_container_width=True, hide_index=True)

    # ========================================================
    # NEWS & SENTIMENT
    # ========================================================
    with tab_news:
        render_news_sentiment_tab(db, user, context="preipo")