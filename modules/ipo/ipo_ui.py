# ============================================================
# modules/ipo/ipo_ui.py
# IPO Intelligence Center UI
# ============================================================

from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.ipo.news_ui import render_news_sentiment_tab
from modules.ipo.service import (
    refresh_ipo_calendar,
    list_ipo_events,
    ipo_events_to_dataframe,
    ipo_summary_metrics,
    add_to_ipo_watchlist,
    list_ipo_watchlist,
    remove_ipo_watchlist_item,
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


def _fmt_price(value):
    try:
        if value is None or pd.isna(value):
            return "N/A"
        return f"${float(value):,.2f}"
    except Exception:
        return "N/A"


def render_ipo_center(db, user):
    tenant_id = user.get("tenant_id", "default_tenant")
    user_id = user.get("user_id") or user.get("id") or user.get("email")

    st.header("IPO Intelligence Center")
    st.caption("Upcoming IPOs · Deal sizes · IPO watchlist · Provider-backed IPO calendar")

    with st.expander("Refresh IPO calendar", expanded=False):
        c1, c2, c3 = st.columns([1, 1, 2])
        days_back = c1.number_input("Days Back", min_value=0, max_value=365, value=30, step=15)
        days_forward = c2.number_input("Days Forward", min_value=30, max_value=730, value=180, step=30)

        if c3.button("Refresh IPO Calendar", type="primary", use_container_width=True):
            with st.spinner("Fetching IPO calendar..."):
                try:
                    result = refresh_ipo_calendar(
                        db=db,
                        tenant_id=tenant_id,
                        days_back=int(days_back),
                        days_forward=int(days_forward),
                    )
                    skipped_msg = f", skipped {result['skipped']} duplicates" if result.get("skipped") else ""
                    st.success(
                        f"IPO refresh complete: fetched {result['fetched']}, upserted {result['upserted']}"
                        f"{skipped_msg} · {result['from']} to {result['to']}."
                    )
                except Exception as e:
                    st.error(f"IPO refresh failed: {e}")

    tab_calendar, tab_watchlist, tab_analytics, tab_news = st.tabs(
        ["Upcoming / Recent IPOs", "IPO Watchlist", "IPO Analytics", "📰 News & Sentiment"]
    )

    with tab_calendar:
        f1, f2 = st.columns([1, 3])
        status_filter = f1.selectbox("Status", ["all", "upcoming", "priced", "withdrawn", "unknown"], index=0)
        search = f2.text_input("Search company, ticker, sector, or industry", "")

        events = list_ipo_events(
            db=db,
            tenant_id=tenant_id,
            status=status_filter,
            search=search,
            limit=500,
        )
        df = ipo_events_to_dataframe(events)
        metrics = ipo_summary_metrics(df)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("IPO Events", metrics["count"])
        m2.metric("Total Deal Size", _fmt_money(metrics["total_deal_size"]))
        m3.metric("Avg Deal Size", _fmt_money(metrics["avg_deal_size"]))
        m4.metric("With Tickers", metrics["with_symbols"])

        if df.empty:
            st.info("No IPO records found. Refresh the IPO calendar to load upcoming IPOs.")
        else:
            display_df = df.copy()
            if "IPO Date" in display_df.columns:
                display_df["IPO Date"] = pd.to_datetime(display_df["IPO Date"], errors="coerce").dt.strftime("%Y-%m-%d")

            st.dataframe(display_df, use_container_width=True, hide_index=True)

            st.markdown("### Add IPO to Watchlist")
            options = [f"{e.company_name} | {e.symbol or 'N/A'} | {e.id}" for e in events]
            selected = st.selectbox("Select IPO", options) if options else None
            notes = st.text_area("Notes", "", height=80)

            if st.button("Add Selected IPO to Watchlist", use_container_width=True):
                if selected:
                    selected_id = selected.split("|")[-1].strip()
                    event = next((e for e in events if e.id == selected_id), None)
                    if event:
                        ok = add_to_ipo_watchlist(
                            db=db,
                            tenant_id=tenant_id,
                            user_id=user_id,
                            ipo_event_id=event.id,
                            company_name=event.company_name,
                            symbol=event.symbol,
                            notes=notes,
                        )
                        st.success("Added to IPO watchlist." if ok else "Unable to add IPO.")
                        st.rerun()

    with tab_watchlist:
        items = list_ipo_watchlist(db, tenant_id, user_id)

        if not items:
            st.info("No IPOs on your watchlist yet.")
        else:
            rows = []
            for item in items:
                rows.append(
                    {
                        "Company": item.company_name,
                        "Symbol": item.symbol,
                        "Status": item.status,
                        "Alerts": item.alert_enabled,
                        "Notes": item.notes,
                        "Created": item.created_at,
                        "ID": item.id,
                    }
                )

            watch_df = pd.DataFrame(rows)
            show_df = watch_df.drop(columns=["ID"], errors="ignore")
            st.dataframe(show_df, use_container_width=True, hide_index=True)

            remove_option = st.selectbox(
                "Remove watchlist item",
                [f"{row['Company']} | {row['Symbol'] or 'N/A'} | {row['ID']}" for row in rows],
            )

            if st.button("Remove Selected", type="secondary"):
                item_id = remove_option.split("|")[-1].strip()
                if remove_ipo_watchlist_item(db, item_id):
                    st.success("Removed from watchlist.")
                    st.rerun()

    with tab_analytics:
        events = list_ipo_events(db=db, tenant_id=tenant_id, limit=1000)
        df = ipo_events_to_dataframe(events)

        if df.empty:
            st.info("No IPO data available for analytics yet.")
            return

        st.markdown("### IPO Pipeline by Exchange")
        if "Exchange" in df.columns:
            exchange_counts = df["Exchange"].fillna("Unknown").value_counts().reset_index()
            exchange_counts.columns = ["Exchange", "Count"]
            st.bar_chart(exchange_counts.set_index("Exchange"))

        st.markdown("### IPO Pipeline by Sector")
        if "Sector" in df.columns:
            sector_counts = df["Sector"].fillna("Unknown").value_counts().head(20).reset_index()
            sector_counts.columns = ["Sector", "Count"]
            st.bar_chart(sector_counts.set_index("Sector"))

        st.markdown("### Largest Deals")
        if "Deal Size" in df.columns:
            largest = df.copy()
            largest["Deal Size"] = pd.to_numeric(largest["Deal Size"], errors="coerce")
            largest = largest.sort_values("Deal Size", ascending=False).head(25)
            st.dataframe(largest, use_container_width=True, hide_index=True)

    with tab_news:
        render_news_sentiment_tab(db, user, context="ipo")