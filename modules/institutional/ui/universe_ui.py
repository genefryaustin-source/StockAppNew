
import streamlit as st
import pandas as pd
from sqlalchemy import text
from modules.universe.service import (
    create_universe,
    list_universes,
    delete_universe,
    add_symbols,
    remove_symbol,
    list_symbols,
)
from modules.universe.auto_assign import auto_assign_universes
from modules.analytics.rankings import rank_symbols, sector_leaderboards
from modules.utils.symbol_utils import clean_symbol_list
from modules.universe.universe_pipeline import run_universe_pipeline
from modules.utils.datetime_utils import (
    to_aware_utc,
)



from datetime import datetime, UTC, timedelta
from modules.analytics.models import AnalyticsSnapshot
from modules.jobs.service import (
            enqueue_job,
            list_jobs,
            cancel_job,
            dequeue_job,
            stop_job,
            requeue_job,
        )

from modules.universe.job_runner import run_one_queued_job





MAX_UI_ROWS = 50
MAX_RANK_ROWS = 50
MAX_SECTOR_ROWS = 25


def _safe_clear_streamlit_cache():
    try:
        st.cache_data.clear()
    except Exception:
        pass


def _show_dataframe(df: pd.DataFrame, max_rows: int = MAX_UI_ROWS):
    if df is None or df.empty:
        st.info("No data to display.")
        return

    df = df.copy().reset_index(drop=True)

    total = len(df)

    if total > max_rows:
        st.caption(
            f"Showing first {max_rows:,} of {total:,} rows "
            f"to keep the Streamlit UI stable."
        )
        df = df.head(max_rows)

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
    )


# --------------------------------------------------
# Universe Health Dashboard
# --------------------------------------------------

def render_universe_dashboard(db, tenant_id, universe_id):

    symbols = list_symbols(db, tenant_id, universe_id)

    if not symbols:
        st.info("Universe empty.")
        return

    snapshots = (
        db.query(AnalyticsSnapshot)
        .filter(
            AnalyticsSnapshot.tenant_id == tenant_id,
            AnalyticsSnapshot.symbol.in_(symbols),
        )
        .all()
    )

    now = datetime.now(UTC)
    fresh_cutoff = now - timedelta(hours=24)

    latest_by_symbol = {}

    for s in snapshots:

        sym = s.symbol
        current_asof = to_aware_utc(s.asof)

        existing = latest_by_symbol.get(sym)

        if existing is None:
            latest_by_symbol[sym] = s
            continue

        existing_asof = to_aware_utc(existing.asof)

        if (
                current_asof
                and existing_asof
                and current_asof > existing_asof
        ):
            latest_by_symbol[sym] = s

    fresh = 0
    stale = 0
    last_refresh = None

    for sym in symbols:

        snap = latest_by_symbol.get(sym)

        if not snap:
            stale += 1
            continue

        snap_asof = to_aware_utc(snap.asof)

        if snap_asof and snap_asof >= fresh_cutoff:
            fresh += 1
        else:
            stale += 1

        if snap_asof and (last_refresh is None or snap_asof > last_refresh):
            last_refresh = snap_asof

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Universe Size", len(symbols))
    col2.metric("Fresh Symbols", fresh)
    col3.metric("Stale Symbols", stale)

    if last_refresh:
        col4.metric("Last Refresh", last_refresh.strftime("%Y-%m-%d %H:%M"))
    else:
        col4.metric("Last Refresh", "Never")

    if stale > 0:
        st.warning(f"{stale} symbols need refresh.")
    else:
        st.success("Universe fully refreshed.")


# --------------------------------------------------
# Text symbol parser
# --------------------------------------------------

def _parse_symbols(text: str):

    raw = text.replace("\n", ",").replace(" ", ",").split(",")

    cleaned = []

    for val in raw:

        if not val:
            continue

        sym = str(val).strip().upper()

        if sym:
            cleaned.append(sym)

    return clean_symbol_list(cleaned)


# --------------------------------------------------
# CSV symbol parser (FIXED)
# --------------------------------------------------

def _parse_symbols_from_csv(df):

    if "symbol" not in df.columns:
        raise Exception("CSV must contain 'symbol' column")

    symbols = []

    for val in df["symbol"]:

        if pd.isna(val):
            continue

        sym = str(val).strip().upper()

        if sym:
            symbols.append(sym)

    return clean_symbol_list(symbols)


# --------------------------------------------------
# Main UI
# --------------------------------------------------

def render_universe(db, user):

    tenant_id = user["tenant_id"]
    user_id = user.get("user_id")

    st.subheader("Universe Builder")
    st.caption(
        "Create ticker universes, queue analytics refresh, manage jobs, and rank the full set."
    )

    # --------------------------------------------------
    # Create universe
    # --------------------------------------------------

    with st.expander("Create New Universe", expanded=False):

        name = st.text_input("Universe Name", key="universe_name")
        description = st.text_area("Description", key="universe_desc")

        if st.button("Create Universe", key="universe_create_btn"):

            if not name.strip():
                st.error("Universe name required.")
            else:

                create_universe(
                    db=db,
                    tenant_id=tenant_id,
                    name=name.strip(),
                    description=description,
                    created_by_user_id=user_id,
                )
                db.commit()
                _safe_clear_streamlit_cache()
                st.success("Universe created")
                _safe_clear_streamlit_cache()
                st.info("Operation complete. Refresh manually if the table does not update immediately.")
    # --------------------------------------------------
    # Delete Old Analytics Refresh Data
    #---------------------------------------------------
    st.divider()
    st.subheader("Analytics Snapshot Cleanup")

    st.warning(
        """
    ⚠️ **Warning**

    This will permanently delete all historical analytics snapshots and keep **only the newest snapshot per symbol**.

    This cannot be undone.

    Use this if you no longer require analytics history and want faster refresh and query performance.
    """
    )

    # Show how many rows would be removed
    rows_to_delete = db.execute(
        text("""
        SELECT COUNT(*)
        FROM analytics_snapshots
        WHERE id NOT IN (
            SELECT MAX(id)
            FROM analytics_snapshots
            GROUP BY symbol
        )
        """)
    ).scalar()
    db.commit()
    _safe_clear_streamlit_cache()
    st.info(f"{rows_to_delete} historical analytics rows can be deleted.")

    if st.button("Clean Analytics Snapshot History"):

        with st.spinner("Cleaning analytics snapshot history..."):

            db.execute(
                text("""
                DELETE FROM analytics_snapshots
                WHERE id NOT IN (
                    SELECT MAX(id)
                    FROM analytics_snapshots
                    GROUP BY symbol
                )
                """)
            )

            db.commit()
            _safe_clear_streamlit_cache()

        st.success("Analytics snapshot history cleaned. Only latest snapshot per symbol remains.")

        _safe_clear_streamlit_cache()
        st.info("Operation complete. Refresh manually if the table does not update immediately.")

    # --------------------------------------------------
    # Select universe
    # --------------------------------------------------

    universes = list_universes(db, tenant_id)

    if not universes:
        st.info("No universes yet.")
        return

    u_map = {f"{u.name} ({u.id[:6]})": u.id for u in universes}

    selected = st.selectbox("Select Universe", list(u_map.keys()))

    universe_id = u_map[selected]

    with st.expander("Delete Universe", expanded=False):

        if st.button("Delete Selected Universe"):

            delete_universe(db, tenant_id, universe_id)

            st.warning("Universe deleted")

            _safe_clear_streamlit_cache()
            st.info("Operation complete. Refresh manually if the table does not update immediately.")

    # --------------------------------------------------
    # Symbols
    # --------------------------------------------------

    st.markdown("### Symbols")

    symbols = list_symbols(db, tenant_id, universe_id)

    if symbols:

        st.caption(
            f"Universe contains {len(symbols):,} symbols. "
            f"Showing first {MAX_UI_ROWS:,}."
        )

        preview_symbols = symbols[:MAX_UI_ROWS]

        st.code(
            ", ".join(preview_symbols),
            language="text",
        )

    else:
        st.info("Universe empty.")

    col1, col2 = st.columns([2, 1])

    with col1:

        symbol_text = st.text_area(
            "Add Symbols (comma / space / newline separated)"
        )

    with col2:

        uploaded = st.file_uploader(
            "Upload CSV (column: symbol)",
            type=["csv"],
        )

    if st.button("Add Symbols"):

        symbols_to_add = []

        # Text input
        if symbol_text.strip():
            symbols_to_add.extend(_parse_symbols(symbol_text))

        # CSV upload
        if uploaded is not None:

            try:

                df = pd.read_csv(uploaded)

                csv_symbols = _parse_symbols_from_csv(df)

                symbols_to_add.extend(csv_symbols)

            except Exception as e:

                st.error(f"CSV parse failed: {e}")

        # Clean and deduplicate
        symbols_to_add = sorted(set(clean_symbol_list(symbols_to_add)))

        if not symbols_to_add:

            st.warning("No valid symbols provided.")

        else:

            inserted = add_symbols(
                db,
                tenant_id,
                universe_id,
                symbols_to_add,
            )

            st.success(f"Added {inserted} symbols")

            _safe_clear_streamlit_cache()
            st.info("Operation complete. Refresh manually if the table does not update immediately.")

    # --------------------------------------------------
    # Remove symbol
    # --------------------------------------------------

    remove_symbol_text = st.text_input("Remove Symbol")

    if st.button("Remove Symbol"):

        if remove_symbol_text.strip():

            remove_symbol(
                db,
                tenant_id,
                universe_id,
                remove_symbol_text.upper(),
            )
            db.commit()
            _safe_clear_streamlit_cache()
            st.success("Symbol removed")

            _safe_clear_streamlit_cache()
            st.info("Operation complete. Refresh manually if the table does not update immediately.")

    # ---------------------------------------
    # Universe Pipeline
    # ---------------------------------------

    st.divider()
    st.subheader("Universe Pipeline")

    col1, col2 = st.columns(2)

    with col1:
        classify_limit = st.number_input(
            "Pipeline limit (0 = all)",
                min_value=0,
                value=0,
                step=100,
                key="universe_pipeline_limit",
            )

    with col2:
        run_pipeline = st.button("Run Universe Pipeline", type="primary")

    if run_pipeline:
        with st.spinner("Running universe pipeline..."):
            result = run_universe_pipeline(
                db,
                tenant_id=user["tenant_id"],
                limit=classify_limit,
            )

        st.success(
            f"Seeded: {result['seeded']} | "
            f"Processed: {result['total']} | "
            f"Updated assignments: {result['updated']}"
        )


    # ---------------------------------------
    # AUTO CLASSIFICATION (NEW)
    # ---------------------------------------
    from modules.universe.auto_assign import auto_assign_universes

    st.divider()
    st.subheader("⚙️ Auto Classify Universes")

    col1, col2 = st.columns(2)

    with col1:
        limit = st.number_input(
            "Limit symbols (0 = all)",
            min_value=0,
            value=0,
            step=100
        )

    with col2:
        run_classify = st.button("Run Auto Classification", type="primary")

    if run_classify:

        with st.spinner("Classifying symbols..."):

            result = auto_assign_universes(
                db,
                tenant_id=user["tenant_id"],
                limit=limit
            )

        st.success(f"""
    ✅ Classification Complete

    Updated: {result['updated']}
    Total: {result['total']}
    """)

    # --------------------------------------------------
    # Health dashboard
    # --------------------------------------------------

    st.divider()
    st.markdown("### Universe Health Dashboard")

    render_universe_dashboard(db, tenant_id, universe_id)

    # --------------------------------------------------
    # Refresh / queue
    # --------------------------------------------------

    st.divider()
    st.markdown("### Universe Refresh Engine")

    colA, colB = st.columns(2)

    with colA:

        if st.button("Queue Universe Refresh"):

            enqueue_job(
                db=db,
                tenant_id=tenant_id,
                job_type="universe_refresh",
                universe_id=universe_id,
                payload={
                    "universe_id": universe_id,
                    "max_age_hours": 72,
                    "batch_size": 25,
                    "parallel": True,
                    "max_workers": 4,
                },
            )

            st.success("Refresh job queued")

            _safe_clear_streamlit_cache()
            st.info("Operation complete. Refresh manually if the table does not update immediately.")

    with colB:

        if st.button("Run Next Job", key=f"run_next_{universe_id}"):

            with st.spinner("Running job..."):

                job_id = run_one_queued_job(db, tenant_id, universe_id)

                if job_id:
                    st.success(f"Started job {job_id}")
                    _safe_clear_streamlit_cache()
                    st.info("Operation complete. Refresh manually if the table does not update immediately.")
                else:
                    st.warning("No queued jobs found for this universe.")



    # --------------------------------------------------
    # Jobs
    # --------------------------------------------------

    st.markdown("### Recent Jobs")

    jobs = list_jobs(
        db,
        tenant_id,
        universe_id=universe_id,
    )

    jobs = jobs[:50]

    rows = []

    for j in jobs:
        rows.append({
            "Job ID": j.id,
            "Type": j.job_type,
            "Status": j.status,
            "Progress": (
                f"{getattr(j, 'done', 0)}/"
                f"{getattr(j, 'total', 0)}"
            ),
            "Error": getattr(j, "error", ""),
        })

    jobs_df = pd.DataFrame(rows)

    st.dataframe(
        jobs_df,
        use_container_width=True,
        hide_index=True,
    )
    job_map = {
        f"{j.id[:8]} | {j.status} | {j.job_type}": j
        for j in jobs
    }

    selected_job_key = st.selectbox(
        "Select Job",
        list(job_map.keys()),
    )

    selected_job = job_map.get(selected_job_key)

    st.markdown("### Job Controls")


    c1, c2, c3, c4 = st.columns(4)

    if c1.button("Run Job"):
        from modules.universe.job_runner import (
            run_specific_job,
        )

        run_specific_job(db, selected_job.id)

        db.commit()

        st.success("Job started.")

    if c2.button("Stop Job"):
        stop_job(db, selected_job.id)

        db.commit()

        st.success("Stop requested.")

    if c3.button("Cancel Job"):
        cancel_job(db, selected_job.id)

        db.commit()

        st.success("Job cancelled.")

    if c4.button("Requeue Job"):
        requeue_job(db, selected_job.id)

        db.commit()

        st.success("Job requeued.")

    #st.markdown("### Job Logs")

    #logs = getattr(selected_job, "logs", "")

    #if logs:
        #st.text(logs[-5000:])
    # --------------------------------------------------
    # Delete Job
    # --------------------------------------------------

    if selected_job is not None:

        st.markdown("### Delete Selected Job")

        st.warning(
            "Deleting a job permanently removes it "
            "from the job history table."
        )

        confirm_delete = st.checkbox(
            "I understand this cannot be undone",
            key=f"confirm_delete_{selected_job.id}",
        )

        if st.button(
                "Delete Job",
                key=f"delete_job_{selected_job.id}",
        ):

            if not confirm_delete:

                st.warning(
                    "Please confirm deletion first."
                )

            else:

                try:

                    db.delete(selected_job)

                    db.commit()

                    st.success(
                        f"Deleted job "
                        f"{selected_job.id[:8]}"
                    )

                except Exception as e:

                    db.rollback()

                    st.error(
                        f"Delete failed: {e}"
                    )


    # --------------------------------------------------
    # Rankings
    # --------------------------------------------------

    st.divider()
    st.markdown("### Rank Universe")

    current_symbols = list_symbols(db, tenant_id, universe_id)

    if st.button("Run Rankings", key=f"run_rankings_{universe_id}"):

        if not current_symbols:
            st.warning("Universe has no symbols to rank.")
            return

        st.caption(
            f"Ranking {len(current_symbols):,} symbols. "
            f"Large universes may take time. Results are capped in the UI."
        )

        with st.spinner(f"Ranking {len(current_symbols):,} symbols..."):

            try:
                rows = rank_symbols(
                    db=db,
                    tenant_id=tenant_id,
                    symbols=current_symbols,
                )

                db.commit()
                _safe_clear_streamlit_cache()

            except Exception as e:
                st.error("Ranking failed.")
                st.exception(e)
                return

        if not rows:
            st.warning("No ranked results found. Run refresh first.")
            return

        leaderboard = pd.DataFrame([
            {
                "Rank": i + 1,
                "Symbol": r.symbol,
                "Sector": r.sector or "Unknown",
                "Composite": r.composite,
                "Confidence": r.confidence,
            }
            for i, r in enumerate(rows[:MAX_RANK_ROWS])
        ])

        st.success(
            f"Ranking complete. Showing top "
            f"{min(len(rows), MAX_RANK_ROWS):,} of {len(rows):,} results."
        )

        _show_dataframe(leaderboard, MAX_RANK_ROWS)

        st.markdown("### Sector Leaders")

        sectors = sector_leaderboards(rows)

        for sector, items in sectors.items():
            st.markdown(f"**{sector or 'Unknown'}**")

            sdf = pd.DataFrame([
                {
                    "Symbol": r.symbol,
                    "Composite": r.composite,
                    "Confidence": r.confidence,
                }
                for r in items[:MAX_SECTOR_ROWS]
            ])

            _show_dataframe(sdf, MAX_SECTOR_ROWS)