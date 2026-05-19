
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




# --------------------------------------------------
# Helper: normalize timestamps
# --------------------------------------------------

def _to_aware_utc(dt):

    if dt is None:
        return None

    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except Exception:
            return None

    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)

    return dt.astimezone(UTC)



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

        if sym not in latest_by_symbol:
            latest_by_symbol[sym] = s
        else:
            if s.asof > latest_by_symbol[sym].asof:
                latest_by_symbol[sym] = s

    fresh = 0
    stale = 0
    last_refresh = None

    for sym in symbols:

        snap = latest_by_symbol.get(sym)

        if not snap:
            stale += 1
            continue

        snap_asof = _to_aware_utc(snap.asof)

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

                st.success("Universe created")
                st.rerun()
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

        st.success("Analytics snapshot history cleaned. Only latest snapshot per symbol remains.")

        st.rerun()

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

            st.rerun()

    # --------------------------------------------------
    # Symbols
    # --------------------------------------------------

    st.markdown("### Symbols")

    symbols = list_symbols(db, tenant_id, universe_id)

    if symbols:

        st.dataframe(
            pd.DataFrame({"symbol": symbols}),
            use_container_width=True,
            hide_index=True,
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

            st.rerun()

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

            st.success("Symbol removed")

            st.rerun()

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

            st.rerun()

    with colB:

        if st.button("Run Next Job", key=f"run_next_{universe_id}"):

            with st.spinner("Running job..."):

                job_id = run_one_queued_job(db, tenant_id, universe_id)

                if job_id:
                    st.success(f"Started job {job_id}")
                    st.rerun()
                else:
                    st.warning("No queued jobs found for this universe.")


    # --------------------------------------------------
    # Jobs Section
    # --------------------------------------------------
    # --------------------------------------------------
    # Jobs
    # --------------------------------------------------

    st.markdown("### Recent Jobs")

    jobs = list_jobs(db, tenant_id, universe_id=universe_id)

    if not jobs:

        st.info("No jobs yet.")

    else:

        header = st.columns([2, 2, 2, 2, 4])

        header[0].write("Job ID")
        header[1].write("Type")
        header[2].write("Status")
        header[3].write("Progress")
        header[4].write("Actions")

        for j in jobs:

            col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 4])

            progress_text = "—"

            done = getattr(j, "done", None)
            total = getattr(j, "total", None)

            if done is not None and total is not None:
                progress_text = f"{done}/{total}"

            col1.write(j.id[:8])
            col2.write(j.job_type)
            col3.write(j.status)
            col4.write(progress_text)

            with col5:

                a1, a2, a3 = st.columns(3)

                if j.status == "queued":

                    from modules.universe.job_runner import run_specific_job

                    if a1.button("Run", key=f"run_{j.id}"):
                        run_specific_job(db, j.id)
                        st.rerun()

                    if a2.button("Dequeue", key=f"dequeue_{j.id}"):
                        dequeue_job(db, j.id)
                        st.rerun()

                    if a3.button("Cancel", key=f"cancelq_{j.id}"):
                        cancel_job(db, j.id)
                        st.rerun()

                elif j.status == "running":

                    if a1.button("Stop", key=f"stop_{j.id}"):
                        stop_job(db, j.id)
                        st.rerun()

                    if a2.button("Cancel", key=f"cancelr_{j.id}"):
                        cancel_job(db, j.id)
                        st.rerun()

                elif j.status in ["failed", "cancelled", "stopped"]:

                    if a1.button("Requeue", key=f"requeue_{j.id}"):
                        requeue_job(db, j.id)
                        st.rerun()

            if getattr(j, "error", None):

                st.caption(f"Error: {j.error}")

            if getattr(j, "logs", None):

                with st.expander(f"Logs {j.id[:8]}", expanded=False):

                    st.code(j.logs)

    # --------------------------------------------------
    # Rankings
    # --------------------------------------------------

    st.divider()
    st.markdown("### Rank Universe")

    current_symbols = list_symbols(db, tenant_id, universe_id)

    if st.button("Run Rankings"):

        rows = rank_symbols(
            db=db,
            tenant_id=tenant_id,
            symbols=current_symbols,
        )

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
            for i, r in enumerate(rows[:25])
        ])

        st.dataframe(
            leaderboard,
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("### Sector Leaders")

        sectors = sector_leaderboards(rows)

        for sector, items in sectors.items():

            st.markdown(f"**{sector}**")

            sdf = pd.DataFrame([
                {
                    "Symbol": r.symbol,
                    "Composite": r.composite,
                    "Confidence": r.confidence,
                }
                for r in items
            ])

            st.dataframe(
                sdf,
                use_container_width=True,
                hide_index=True,
            )