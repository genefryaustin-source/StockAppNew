import pandas as pd
import streamlit as st
from datetime import datetime, timedelta, UTC

from sqlalchemy import text


FRESHNESS_DAYS = 7


def _rows_to_df(rows, columns):
    """Convert SQLAlchemy rows to a DataFrame with stable columns."""
    if not rows:
        return pd.DataFrame(columns=columns)

    out = []
    for row in rows:
        if hasattr(row, "_mapping"):
            out.append(dict(row._mapping))
        else:
            out.append(dict(row))

    df = pd.DataFrame(out)

    for col in columns:
        if col not in df.columns:
            df[col] = None

    return df[columns]


def _safe_pct(numerator, denominator):
    try:
        denominator = int(denominator or 0)
        numerator = int(numerator or 0)

        if denominator <= 0:
            return 0.0

        return round((numerator / denominator) * 100, 1)

    except Exception:
        return 0.0


def _status_from_coverage(coverage_pct, fresh_pct):
    weakest = min(float(coverage_pct or 0), float(fresh_pct or 0))

    if weakest >= 99:
        return "🟢 Healthy"

    if weakest >= 95:
        return "🟡 Warning"

    if weakest >= 80:
        return "🟠 Degraded"

    return "🔴 Critical"


def render_analytics_freshness_dashboard(db, user):
    """
    Universe Analytics Freshness dashboard.

    Current architecture uses analytics_snapshots as the active analytics
    source of truth. fundamental_snapshots is intentionally not used here
    because it is no longer populated by the current analytics pipeline.
    """

    st.header("📊 Universe Analytics Freshness")
    st.caption(
        "Universe-level analytics coverage, freshness, missing symbols, and stale symbols. "
        "This dashboard uses analytics_snapshots as the active source of truth."
    )

    role = user.get("role")
    tenant_id = user.get("tenant_id")

    # NOW() - (n || ' days')::interval is Postgres-only syntax (string concat
    # + interval cast); SQLite has neither. Compute the cutoff once here in
    # Python and bind it as a plain literal -- works identically on both.
    freshness_cutoff = datetime.now(UTC) - timedelta(days=FRESHNESS_DAYS)

    if role == "super_admin":
        universe_sql = """
        WITH latest_analytics AS (
            SELECT
                symbol,
                MAX(asof) AS latest_asof
            FROM analytics_snapshots
            GROUP BY symbol
        )
        SELECT
            u.id AS universe_id,
            u.name AS universe,
            u.tenant_id,
            COALESCE(t.name, u.tenant_id) AS tenant,
            COUNT(DISTINCT us.symbol) AS symbol_count,

            COUNT(
                DISTINCT CASE
                    WHEN la.symbol IS NOT NULL
                    THEN us.symbol
                END
            ) AS analytics_symbols,

            COUNT(
                DISTINCT CASE
                    WHEN la.latest_asof >= :freshness_cutoff
                    THEN us.symbol
                END
            ) AS fresh_symbols,

            COUNT(
                DISTINCT CASE
                    WHEN la.symbol IS NULL
                    THEN us.symbol
                END
            ) AS missing_symbols,

            COUNT(
                DISTINCT CASE
                    WHEN la.symbol IS NOT NULL
                     AND la.latest_asof < :freshness_cutoff
                    THEN us.symbol
                END
            ) AS stale_symbols,

            MAX(la.latest_asof) AS latest_asof

        FROM universes u

        LEFT JOIN tenants t
            ON t.id = u.tenant_id

        LEFT JOIN universe_symbols us
            ON us.universe_id = u.id

        LEFT JOIN latest_analytics la
            ON la.symbol = us.symbol

        GROUP BY
            u.id,
            u.name,
            u.tenant_id,
            t.name

        ORDER BY
            COALESCE(t.name, u.tenant_id),
            u.name
        """

        universe_rows = db.execute(
            text(universe_sql),
            {"freshness_cutoff": freshness_cutoff},
        ).fetchall()

    else:
        universe_sql = """
        WITH latest_analytics AS (
            SELECT
                symbol,
                MAX(asof) AS latest_asof
            FROM analytics_snapshots
            GROUP BY symbol
        )
        SELECT
            u.id AS universe_id,
            u.name AS universe,
            u.tenant_id,
            COALESCE(t.name, u.tenant_id) AS tenant,
            COUNT(DISTINCT us.symbol) AS symbol_count,

            COUNT(
                DISTINCT CASE
                    WHEN la.symbol IS NOT NULL
                    THEN us.symbol
                END
            ) AS analytics_symbols,

            COUNT(
                DISTINCT CASE
                    WHEN la.latest_asof >= :freshness_cutoff
                    THEN us.symbol
                END
            ) AS fresh_symbols,

            COUNT(
                DISTINCT CASE
                    WHEN la.symbol IS NULL
                    THEN us.symbol
                END
            ) AS missing_symbols,

            COUNT(
                DISTINCT CASE
                    WHEN la.symbol IS NOT NULL
                     AND la.latest_asof < :freshness_cutoff
                    THEN us.symbol
                END
            ) AS stale_symbols,

            MAX(la.latest_asof) AS latest_asof

        FROM universes u

        LEFT JOIN tenants t
            ON t.id = u.tenant_id

        LEFT JOIN universe_symbols us
            ON us.universe_id = u.id

        LEFT JOIN latest_analytics la
            ON la.symbol = us.symbol

        WHERE u.tenant_id = :tenant_id

        GROUP BY
            u.id,
            u.name,
            u.tenant_id,
            t.name

        ORDER BY
            u.name
        """

        universe_rows = db.execute(
            text(universe_sql),
            {
                "tenant_id": tenant_id,
                "freshness_cutoff": freshness_cutoff,
            },
        ).fetchall()

    df = _rows_to_df(
        universe_rows,
        [
            "universe_id",
            "universe",
            "tenant_id",
            "tenant",
            "symbol_count",
            "analytics_symbols",
            "fresh_symbols",
            "missing_symbols",
            "stale_symbols",
            "latest_asof",
        ],
    )

    if df.empty:
        st.info("No universes found.")
        return

    df = df[df["symbol_count"].fillna(0).astype(int) > 0].copy()

    if df.empty:
        st.info("No universes with symbols found.")
        return

    df["Analytics Coverage %"] = df.apply(
        lambda r: _safe_pct(r["analytics_symbols"], r["symbol_count"]),
        axis=1,
    )

    df["Fresh Analytics %"] = df.apply(
        lambda r: _safe_pct(r["fresh_symbols"], r["symbol_count"]),
        axis=1,
    )

    df["Status"] = df.apply(
        lambda r: _status_from_coverage(
            r["Analytics Coverage %"],
            r["Fresh Analytics %"],
        ),
        axis=1,
    )

    healthy = len(df[df["Status"].str.contains("Healthy", na=False)])
    warning = len(df[df["Status"].str.contains("Warning", na=False)])
    degraded = len(df[df["Status"].str.contains("Degraded", na=False)])
    critical = len(df[df["Status"].str.contains("Critical", na=False)])

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric("Universes", len(df))
    c2.metric("Healthy", healthy)
    c3.metric("Warning", warning)
    c4.metric("Degraded", degraded)
    c5.metric("Critical", critical)

    display_cols = [
        "universe",
        "symbol_count",
        "analytics_symbols",
        "fresh_symbols",
        "missing_symbols",
        "stale_symbols",
        "Analytics Coverage %",
        "Fresh Analytics %",
        "latest_asof",
        "Status",
    ]

    if role == "super_admin":
        display_cols.insert(1, "tenant")

    st.dataframe(
        df[display_cols].rename(
            columns={
                "universe": "Universe",
                "tenant": "Tenant",
                "symbol_count": "Symbols",
                "analytics_symbols": "Analytics Symbols",
                "fresh_symbols": "Fresh Symbols",
                "missing_symbols": "Missing Symbols",
                "stale_symbols": "Stale Symbols",
                "latest_asof": "Latest AsOf",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.download_button(
        "⬇️ Export Universe Analytics Health CSV",
        df.to_csv(index=False),
        file_name="universe_analytics_health.csv",
        mime="text/csv",
        key="analytics_freshness_export_health",
    )

    st.divider()
    st.subheader("Universe Drilldown")

    universe_options = {
        (
            f"{row['tenant']} — {row['universe']}"
            if role == "super_admin"
            else row["universe"]
        ): row["universe_id"]
        for _, row in df.iterrows()
    }

    selected_label = st.selectbox(
        "Universe",
        list(universe_options.keys()),
        key="analytics_freshness_universe_drilldown",
    )

    selected_universe_id = universe_options[selected_label]

    selected_row = df[df["universe_id"] == selected_universe_id].iloc[0]

    d1, d2, d3, d4, d5 = st.columns(5)

    d1.metric("Symbols", int(selected_row["symbol_count"]))
    d2.metric("Coverage", f"{selected_row['Analytics Coverage %']}%")
    d3.metric("Fresh", f"{selected_row['Fresh Analytics %']}%")
    d4.metric("Missing", int(selected_row["missing_symbols"]))
    d5.metric("Stale", int(selected_row["stale_symbols"]))

    st.json(
        {
            "Universe": selected_row["universe"],
            "Tenant": selected_row["tenant"],
            "Symbols": int(selected_row["symbol_count"]),
            "Analytics Symbols": int(selected_row["analytics_symbols"]),
            "Fresh Symbols": int(selected_row["fresh_symbols"]),
            "Missing Symbols": int(selected_row["missing_symbols"]),
            "Stale Symbols": int(selected_row["stale_symbols"]),
            "Analytics Coverage": selected_row["Analytics Coverage %"],
            "Fresh Analytics": selected_row["Fresh Analytics %"],
            "Latest AsOf": str(selected_row["latest_asof"]),
            "Status": selected_row["Status"],
            "Freshness Window Days": FRESHNESS_DAYS,
        }
    )

    missing_sql = """
    WITH latest_analytics AS (
        SELECT
            symbol,
            MAX(asof) AS latest_asof
        FROM analytics_snapshots
        GROUP BY symbol
    )
    SELECT
        us.symbol
    FROM universe_symbols us
    LEFT JOIN latest_analytics la
        ON la.symbol = us.symbol
    WHERE us.universe_id = :universe_id
      AND la.symbol IS NULL
    ORDER BY us.symbol
    """

    stale_sql = """
    WITH latest_analytics AS (
        SELECT
            symbol,
            MAX(asof) AS latest_asof
        FROM analytics_snapshots
        GROUP BY symbol
    )
    SELECT
        us.symbol,
        la.latest_asof
    FROM universe_symbols us
    JOIN latest_analytics la
        ON la.symbol = us.symbol
    WHERE us.universe_id = :universe_id
      AND la.latest_asof < :freshness_cutoff
    ORDER BY la.latest_asof ASC, us.symbol
    """

    present_sql = """
    WITH latest_analytics AS (
        SELECT
            symbol,
            MAX(asof) AS latest_asof
        FROM analytics_snapshots
        GROUP BY symbol
    )
    SELECT
        us.symbol,
        la.latest_asof,
        CASE
            WHEN la.latest_asof >= :freshness_cutoff
            THEN 'FRESH'
            ELSE 'STALE'
        END AS analytics_state
    FROM universe_symbols us
    JOIN latest_analytics la
        ON la.symbol = us.symbol
    WHERE us.universe_id = :universe_id
    ORDER BY us.symbol
    """

    missing_rows = db.execute(
        text(missing_sql),
        {"universe_id": selected_universe_id},
    ).fetchall()

    stale_rows = db.execute(
        text(stale_sql),
        {
            "universe_id": selected_universe_id,
            "freshness_cutoff": freshness_cutoff,
        },
    ).fetchall()

    present_rows = db.execute(
        text(present_sql),
        {
            "universe_id": selected_universe_id,
            "freshness_cutoff": freshness_cutoff,
        },
    ).fetchall()

    missing_df = _rows_to_df(
        missing_rows,
        ["symbol"],
    ).rename(columns={"symbol": "Symbol"})

    stale_df = _rows_to_df(
        stale_rows,
        ["symbol", "latest_asof"],
    )

    if not stale_df.empty:
        stale_df["days_old"] = (
            pd.to_datetime(datetime.now(UTC))
            - pd.to_datetime(stale_df["latest_asof"], utc=True, errors="coerce")
        ).dt.days
    else:
        stale_df["days_old"] = pd.Series(dtype="float64")

    stale_df = stale_df.rename(
        columns={
            "symbol": "Symbol",
            "latest_asof": "Latest Analytics AsOf",
            "days_old": "Days Old",
        }
    )

    present_df = _rows_to_df(
        present_rows,
        ["symbol", "latest_asof", "analytics_state"],
    ).rename(
        columns={
            "symbol": "Symbol",
            "latest_asof": "Latest Analytics AsOf",
            "analytics_state": "Analytics State",
        }
    )

    tab_missing, tab_stale, tab_present = st.tabs(
        [
            "Missing Analytics",
            "Stale Analytics",
            "Symbols With Analytics",
        ]
    )

    with tab_missing:
        st.metric("Missing Analytics Symbols", len(missing_df))

        if missing_df.empty:
            st.success("No missing analytics symbols.")
        else:
            st.dataframe(
                missing_df,
                use_container_width=True,
                hide_index=True,
            )

            st.download_button(
                "⬇️ Export Missing Analytics Symbols",
                missing_df.to_csv(index=False),
                file_name=f"{selected_label}_missing_analytics.csv".replace(" ", "_"),
                mime="text/csv",
                key="analytics_freshness_export_missing",
            )

    with tab_stale:
        st.metric("Stale Analytics Symbols", len(stale_df))

        if stale_df.empty:
            st.success("No stale analytics symbols.")
        else:
            st.dataframe(
                stale_df,
                use_container_width=True,
                hide_index=True,
            )

            st.download_button(
                "⬇️ Export Stale Analytics Symbols",
                stale_df.to_csv(index=False),
                file_name=f"{selected_label}_stale_analytics.csv".replace(" ", "_"),
                mime="text/csv",
                key="analytics_freshness_export_stale",
            )

    with tab_present:
        st.metric("Symbols With Analytics", len(present_df))

        if present_df.empty:
            st.info("No analytics snapshots found for this universe.")
        else:
            state_filter = st.multiselect(
                "Filter Analytics State",
                ["FRESH", "STALE"],
                default=["FRESH", "STALE"],
                key="analytics_freshness_state_filter",
            )

            filtered_present_df = present_df[
                present_df["Analytics State"].isin(state_filter)
            ]

            st.dataframe(
                filtered_present_df,
                use_container_width=True,
                hide_index=True,
            )

            st.download_button(
                "⬇️ Export Symbols With Analytics",
                filtered_present_df.to_csv(index=False),
                file_name=f"{selected_label}_symbols_with_analytics.csv".replace(" ", "_"),
                mime="text/csv",
                key="analytics_freshness_export_present",
            )