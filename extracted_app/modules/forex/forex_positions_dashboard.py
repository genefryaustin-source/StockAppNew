"""
modules/forex/forex_positions_dashboard.py

Sprint FX

Forex Positions Dashboard

Phase 1

Institutional Live Positions Workspace

Features
--------
✓ Live Positions
✓ Position Summary
✓ Filters
✓ Position Selection
✓ Position Details
✓ Execution Timeline
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from modules.forex.forex_position_management_engine import (
    get_forex_position_management_engine,
)

from modules.execution.execution_event_explorer import (
    get_execution_event_explorer,
)


# ==============================================================================
# Dashboard
# ==============================================================================


def render_forex_positions_dashboard(
    *,
    db,
    portfolio_engine,
    account=None,
    tenant_id=None,
    user_id=None,
    portfolio_id=None,
):

    st.title("📈 Live Forex Positions")

    engine = get_forex_position_management_engine(

        db=db,

        portfolio_engine=portfolio_engine,

    )

    explorer = get_execution_event_explorer(
        db=db,
    )

    # ----------------------------------------------------------------------
    # Toolbar
    # ----------------------------------------------------------------------

    c1, c2, c3, c4 = st.columns([2, 2, 2, 1])

    with c1:

        symbol_filter = st.text_input(
            "Pair",
        ).upper()

    with c2:

        side_filter = st.selectbox(

            "Direction",

            [

                "ALL",

                "BUY",

                "SELL",

            ],

        )

    with c3:

        status_filter = st.selectbox(

            "Status",

            [

                "ALL",

                "OPEN",

                "ACTIVE",

                "LIVE",

            ],

        )

    with c4:

        if st.button(

            "Refresh",

            use_container_width=True,

        ):

            st.rerun()

    st.divider()

    # ----------------------------------------------------------------------
    # Load Positions
    # ----------------------------------------------------------------------

    positions = engine.load_positions(

        account_id=getattr(
            account,
            "id",
            None,
        ),

        portfolio_id=portfolio_id,

    )

    filtered = []

    for row in positions:

        symbol = str(
            row.get(
                "symbol",
                "",
            )
        ).upper()

        side = str(
            row.get(
                "side",
                "",
            )
        ).upper()

        status = str(
            row.get(
                "status",
                "",
            )
        ).upper()

        if symbol_filter:

            if symbol_filter not in symbol:
                continue

        if side_filter != "ALL":

            if side != side_filter:
                continue

        if status_filter != "ALL":

            if status != status_filter:
                continue

        filtered.append(
            row,
        )

    # ----------------------------------------------------------------------
    # Summary
    # ----------------------------------------------------------------------

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(

        "Positions",

        len(filtered),

    )

    c2.metric(

        "Long",

        sum(

            1

            for x in filtered

            if str(
                x.get(
                    "side",
                    "",
                )
            ).upper() == "BUY"

        ),

    )

    c3.metric(

        "Short",

        sum(

            1

            for x in filtered

            if str(
                x.get(
                    "side",
                    "",
                )
            ).upper() == "SELL"

        ),

    )

    c4.metric(

        "Updated",

        datetime.utcnow().strftime(
            "%H:%M:%S"
        ),

    )

    st.divider()

    # ----------------------------------------------------------------------
    # Position Grid
    # ----------------------------------------------------------------------

    if not filtered:

        st.info(
            "No live positions."
        )

        return

    df = pd.DataFrame(filtered)

    columns = [

        c

        for c in [

            "position_id",

            "symbol",

            "side",

            "quantity",

            "avg_price",

            "current_price",

            "stop_price",

            "target_price",

            "status",

            "opened_at",

        ]

        if c in df.columns

    ]

    st.dataframe(

        df[columns],

        use_container_width=True,

        hide_index=True,

    )

    st.divider()

    # ----------------------------------------------------------------------
    # Position Selection
    # ----------------------------------------------------------------------

    selected = st.selectbox(

        "Select Position",

        df["position_id"],

    )

    position = next(

        x

        for x in filtered

        if x["position_id"] == selected

    )

    # ----------------------------------------------------------------------
    # Details
    # ----------------------------------------------------------------------

    st.subheader(
        "Position Details"
    )

    left, right = st.columns(2)

    with left:

        st.json(
            position,
        )

    with right:

        try:

            timeline = explorer.timeline(

                position_id=selected,

            )

            if timeline:

                st.dataframe(

                    pd.DataFrame(
                        timeline,
                    ),

                    use_container_width=True,

                    hide_index=True,

                )

            else:

                st.info(
                    "No execution events."
                )

        except Exception:

            st.info(
                "Timeline unavailable."
            )

    st.divider()

    # ----------------------------------------------------------------------
    # Position Overview
    # ----------------------------------------------------------------------

    st.subheader(
        "Current Position"
    )

    m1, m2, m3, m4 = st.columns(4)

    m1.metric(

        "Pair",

        position.get(
            "symbol",
            "-",
        ),

    )

    m2.metric(

        "Direction",

        position.get(
            "side",
            "-",
        ),

    )

    m3.metric(

        "Units",

        position.get(
            "quantity",
            0,
        ),

    )

    m4.metric(

        "Status",

        position.get(
            "status",
            "-",
        ),

    )

    st.caption(
        "Forex Position Dashboard • Phase 1"
    )
    # ----------------------------------------------------------------------
    # Position Actions
    # ----------------------------------------------------------------------

    st.divider()

    st.subheader("Position Management")

    edit_col1, edit_col2 = st.columns(2)

    with edit_col1:

        new_stop = st.number_input(

            "Stop Loss",

            value=float(
                position.get(
                    "stop_price",
                    0.0,
                ) or 0.0
            ),

            format="%.5f",

        )

    with edit_col2:

        new_target = st.number_input(

            "Take Profit",

            value=float(
                position.get(
                    "target_price",
                    0.0,
                ) or 0.0
            ),

            format="%.5f",

        )

    modify_col1, modify_col2 = st.columns(2)

    with modify_col1:

        if st.button(

            "Update Stop",

            use_container_width=True,

        ):

            try:

                result = engine.modify_position(

                    selected,

                    stop_price=new_stop,

                )

                st.success(result.message)

                st.rerun()

            except Exception as exc:

                st.error(exc)

    with modify_col2:

        if st.button(

            "Update Target",

            use_container_width=True,

        ):

            try:

                result = engine.modify_position(

                    selected,

                    target_price=new_target,

                )

                st.success(result.message)

                st.rerun()

            except Exception as exc:

                st.error(exc)

    st.divider()

    # ----------------------------------------------------------------------
    # Scaling
    # ----------------------------------------------------------------------

    st.subheader("Scale Position")

    scale_units = st.number_input(

        "Units",

        min_value=1.0,

        value=1000.0,

        step=1000.0,

    )

    scale_col1, scale_col2 = st.columns(2)

    with scale_col1:

        if st.button(

            "Scale In",

            use_container_width=True,

        ):

            try:

                result = engine.scale_in(

                    selected,

                    quantity=scale_units,

                )

                st.success(result.message)

                st.rerun()

            except Exception as exc:

                st.error(exc)

    with scale_col2:

        if st.button(

            "Scale Out",

            use_container_width=True,

        ):

            try:

                result = engine.scale_out(

                    selected,

                    quantity=scale_units,

                )

                st.success(result.message)

                st.rerun()

            except Exception as exc:

                st.error(exc)

    st.divider()

    # ----------------------------------------------------------------------
    # Position Exit
    # ----------------------------------------------------------------------

    st.subheader("Exit Position")

    close_price = st.number_input(

        "Requested Exit Price",

        value=0.0,

        format="%.5f",

    )

    exit_col1, exit_col2 = st.columns(2)

    with exit_col1:

        if st.button(

            "Close Position",

            use_container_width=True,

        ):

            try:

                kwargs = {}

                if close_price > 0:

                    kwargs["requested_price"] = close_price

                result = engine.close_position(

                    selected,

                    **kwargs,

                )

                st.success(result.message)

                st.rerun()

            except Exception as exc:

                st.error(exc)

    with exit_col2:

        if st.button(

            "Reverse Position",

            use_container_width=True,

        ):

            try:

                kwargs = {}

                if close_price > 0:

                    kwargs["requested_price"] = close_price

                result = engine.reverse_position(

                    selected,

                    **kwargs,

                )

                st.success(result.message)

                st.rerun()

            except Exception as exc:

                st.error(exc)

    st.divider()

    # ----------------------------------------------------------------------
    # Flatten Operations
    # ----------------------------------------------------------------------

    st.subheader("Flatten")

    flat_col1, flat_col2 = st.columns(2)

    with flat_col1:

        if st.button(

            "Flatten Symbol",

            use_container_width=True,

        ):

            try:

                results = engine.flatten_symbol(

                    symbol=position["symbol"],

                    account_id=getattr(

                        account,

                        "id",

                        None,

                    ),

                )

                st.success(

                    f"{len(results)} position(s) closed."

                )

                st.rerun()

            except Exception as exc:

                st.error(exc)

    with flat_col2:

        if st.button(

            "Flatten Account",

            use_container_width=True,

        ):

            try:

                results = engine.flatten_account(

                    account_id=getattr(

                        account,

                        "id",

                        None,

                    )

                )

                st.success(

                    f"{len(results)} position(s) closed."

                )

                st.rerun()

            except Exception as exc:

                st.error(exc)
    # ----------------------------------------------------------------------
    # Live Position Analytics
    # ----------------------------------------------------------------------

    st.divider()

    st.subheader("Live Position Analytics")

    #
    # Current values
    #

    entry_price = float(

        position.get(
            "avg_price",
            0,
        ) or 0

    )

    current_price = float(

        position.get(
            "current_price",
            entry_price,
        ) or entry_price

    )

    units = float(

        position.get(
            "quantity",
            0,
        ) or 0

    )

    side = str(

        position.get(
            "side",
            "",
        )

    ).upper()

    #
    # Pips
    #

    if "JPY" in str(

        position.get(
            "symbol",
            "",
        )

    ).upper():

        pip_size = 0.01

    else:

        pip_size = 0.0001

    if side == "BUY":

        pip_gain = (

            current_price
            - entry_price

        ) / pip_size

    else:

        pip_gain = (

            entry_price
            - current_price

        ) / pip_size

    #
    # Unrealized PnL
    #

    if side == "BUY":

        unrealized = (

            current_price
            - entry_price

        ) * units

    else:

        unrealized = (

            entry_price
            - current_price

        ) * units

    #
    # Margin
    #

    leverage = float(

        position.get(
            "leverage",
            50,
        ) or 50

    )

    if leverage <= 0:

        leverage = 50

    margin_used = (

        current_price
        * units

    ) / leverage

    #
    # Holding Time
    #

    age = "-"

    opened = (

        position.get(
            "opened_at",
        )

        or

        position.get(
            "created_at",
        )

    )

    try:

        if isinstance(
            opened,
            str,
        ):

            opened = datetime.fromisoformat(
                opened
            )

        delta = datetime.utcnow() - opened

        age = str(delta).split(".")[0]

    except Exception:

        pass

    #
    # Risk
    #

    stop = float(

        position.get(
            "stop_price",
            0,
        ) or 0

    )

    if stop:

        if side == "BUY":

            risk = (

                entry_price
                - stop

            ) * units

        else:

            risk = (

                stop
                - entry_price

            ) * units

    else:

        risk = 0

    #
    # Reward
    #

    target = float(

        position.get(
            "target_price",
            0,
        ) or 0

    )

    if target:

        if side == "BUY":

            reward = (

                target
                - entry_price

            ) * units

        else:

            reward = (

                entry_price
                - target

            ) * units

    else:

        reward = 0

    if risk:

        rr = reward / risk

    else:

        rr = 0

    # ------------------------------------------------------------------
    # KPI Cards
    # ------------------------------------------------------------------

    r1, r2, r3, r4 = st.columns(4)

    r1.metric(

        "Entry",

        f"{entry_price:.5f}",

    )

    r2.metric(

        "Current",

        f"{current_price:.5f}",

        delta=f"{pip_gain:.1f} pips",

    )

    r3.metric(

        "Unrealized PnL",

        f"{unrealized:,.2f}",

    )

    r4.metric(

        "Margin Used",

        f"{margin_used:,.2f}",

    )

    r5, r6, r7, r8 = st.columns(4)

    r5.metric(

        "Risk",

        f"{risk:,.2f}",

    )

    r6.metric(

        "Reward",

        f"{reward:,.2f}",

    )

    r7.metric(

        "Risk / Reward",

        f"{rr:.2f}",

    )

    r8.metric(

        "Position Age",

        age,

    )

    st.divider()

    # ------------------------------------------------------------------
    # Analytics Table
    # ------------------------------------------------------------------

    analytics = pd.DataFrame(

        [

            {

                "Metric": "Entry Price",

                "Value": entry_price,

            },

            {

                "Metric": "Current Price",

                "Value": current_price,

            },

            {

                "Metric": "Position Size",

                "Value": units,

            },

            {

                "Metric": "Direction",

                "Value": side,

            },

            {

                "Metric": "Pips",

                "Value": round(
                    pip_gain,
                    2,
                ),

            },

            {

                "Metric": "Unrealized PnL",

                "Value": round(
                    unrealized,
                    2,
                ),

            },

            {

                "Metric": "Margin Used",

                "Value": round(
                    margin_used,
                    2,
                ),

            },

            {

                "Metric": "Stop",

                "Value": stop,

            },

            {

                "Metric": "Target",

                "Value": target,

            },

            {

                "Metric": "Risk",

                "Value": round(
                    risk,
                    2,
                ),

            },

            {

                "Metric": "Reward",

                "Value": round(
                    reward,
                    2,
                ),

            },

            {

                "Metric": "Risk/Reward",

                "Value": round(
                    rr,
                    2,
                ),

            },

            {

                "Metric": "Holding Time",

                "Value": age,

            },

        ]

    )

    st.dataframe(

        analytics,

        use_container_width=True,

        hide_index=True,

    )
    # ----------------------------------------------------------------------
    # Institutional Analytics
    # Part 3B-1
    # ----------------------------------------------------------------------

    st.divider()

    st.subheader("Institutional Position Analytics")

    positions = filtered

    # ------------------------------------------------------------------
    # Currency Exposure
    # ------------------------------------------------------------------

    currency_exposure = {}

    pair_exposure = {}

    total_notional = 0.0

    for row in positions:

        symbol = str(
            row.get("symbol", "")
        ).upper()

        qty = abs(float(
            row.get("quantity", 0) or 0
        ))

        price = float(
            row.get(
                "current_price",
                row.get(
                    "avg_price",
                    0,
                ),
            ) or 0
        )

        notional = qty * price

        total_notional += notional

        pair_exposure.setdefault(
            symbol,
            0.0,
        )

        pair_exposure[symbol] += notional

        #
        # EURUSD
        # EUR/USD
        #

        if "/" in symbol:

            base, quote = symbol.split("/")

        elif len(symbol) == 6:

            base = symbol[:3]

            quote = symbol[3:]

        else:

            continue

        currency_exposure.setdefault(
            base,
            0.0,
        )

        currency_exposure.setdefault(
            quote,
            0.0,
        )

        if str(
            row.get(
                "side",
                "",
            )
        ).upper() == "BUY":

            currency_exposure[base] += notional

            currency_exposure[quote] -= notional

        else:

            currency_exposure[base] -= notional

            currency_exposure[quote] += notional

    c1, c2 = st.columns(2)

    with c1:

        st.markdown("#### Currency Exposure")

        exposure_df = pd.DataFrame(

            [

                {

                    "Currency": k,

                    "Exposure": round(v, 2),

                }

                for k, v in sorted(
                    currency_exposure.items()
                )

            ]

        )

        if not exposure_df.empty:

            st.dataframe(

                exposure_df,

                use_container_width=True,

                hide_index=True,

            )

            st.bar_chart(

                exposure_df.set_index(
                    "Currency"
                )

            )

    with c2:

        st.markdown("#### Pair Exposure")

        pair_df = pd.DataFrame(

            [

                {

                    "Pair": k,

                    "Exposure": round(v, 2),

                }

                for k, v in sorted(

                    pair_exposure.items(),

                    key=lambda x: abs(x[1]),

                    reverse=True,

                )

            ]

        )

        if not pair_df.empty:

            st.dataframe(

                pair_df,

                use_container_width=True,

                hide_index=True,

            )

            st.bar_chart(

                pair_df.set_index(
                    "Pair"
                )

            )

    st.divider()

    # ------------------------------------------------------------------
    # Position Statistics
    # ------------------------------------------------------------------

    st.subheader(
        "Position Statistics"
    )

    #
    # Placeholder values until the analytics engine
    # provides historical excursions.
    #

    mae = position.get(
        "mae",
        0.0,
    )

    mfe = position.get(
        "mfe",
        0.0,
    )

    drawdown = position.get(
        "drawdown",
        0.0,
    )

    swap = position.get(
        "swap",
        0.0,
    )

    financing = position.get(
        "financing",
        swap,
    )

    stat1, stat2, stat3, stat4 = st.columns(4)

    stat1.metric(

        "MAE",

        f"{mae:,.2f}",

    )

    stat2.metric(

        "MFE",

        f"{mfe:,.2f}",

    )

    stat3.metric(

        "Drawdown",

        f"{drawdown:,.2f}",

    )

    stat4.metric(

        "Swap",

        f"{swap:,.2f}",

    )

    stats = pd.DataFrame(

        [

            {

                "Metric": "Maximum Adverse Excursion",

                "Value": mae,

            },

            {

                "Metric": "Maximum Favorable Excursion",

                "Value": mfe,

            },

            {

                "Metric": "Drawdown",

                "Value": drawdown,

            },

            {

                "Metric": "Swap",

                "Value": swap,

            },

            {

                "Metric": "Financing",

                "Value": financing,

            },

            {

                "Metric": "Portfolio Notional",

                "Value": round(
                    total_notional,
                    2,
                ),

            },

        ]

    )

    st.dataframe(

        stats,

        use_container_width=True,

        hide_index=True,

    )

    st.divider()

    # ------------------------------------------------------------------
    # Position Performance
    # ------------------------------------------------------------------

    st.subheader(
        "Portfolio Performance"
    )

    perf_rows = []

    for row in positions:

        entry = float(

            row.get(
                "avg_price",
                0,
            ) or 0

        )

        current = float(

            row.get(
                "current_price",
                entry,
            ) or entry

        )

        qty = float(

            row.get(
                "quantity",
                0,
            ) or 0

        )

        side = str(

            row.get(
                "side",
                "",
            )

        ).upper()

        pnl = (

            current - entry

        ) * qty

        if side == "SELL":

            pnl *= -1

        perf_rows.append(

            {

                "Pair":

                    row.get(
                        "symbol",
                    ),

                "PnL":

                    round(
                        pnl,
                        2,
                    ),

            }

        )

    perf_df = pd.DataFrame(
        perf_rows,
    )

    if not perf_df.empty:

        st.dataframe(

            perf_df,

            use_container_width=True,

            hide_index=True,

        )

        st.bar_chart(

            perf_df.set_index(
                "Pair"
            )

        )

    else:

        st.info(
            "No performance data available."
        )
        # ----------------------------------------------------------------------
        # AI Trade Summary
        # ----------------------------------------------------------------------

        st.divider()

        st.subheader("AI Trade Summary")

        ai_summary = {

            "Executive AI":
                position.get(
                    "executive_ai",
                    "Unavailable",
                ),

            "Macro Regime":
                position.get(
                    "macro_regime",
                    "Unknown",
                ),

            "Currency Strength":
                position.get(
                    "currency_strength",
                    "N/A",
                ),

            "Sentiment":
                position.get(
                    "sentiment",
                    "Neutral",
                ),

            "Intermarket":
                position.get(
                    "intermarket_signal",
                    "None",
                ),

            "Carry Score":
                position.get(
                    "carry_score",
                    "-",
                ),

            "Institutional Bias":
                position.get(
                    "institutional_bias",
                    "-",
                ),

            "Alpha Score":
                position.get(
                    "alpha_score",
                    "-",
                ),

            "AI Confidence":
                position.get(
                    "confidence_score",
                    "-",
                ),

            "Recommendation":
                position.get(
                    "recommendation",
                    "HOLD",
                ),

        }

        left, right = st.columns([1, 2])

        with left:

            st.dataframe(

                pd.DataFrame(

                    [

                        {

                            "Metric": k,

                            "Value": v,

                        }

                        for k, v in ai_summary.items()

                    ]

                ),

                use_container_width=True,

                hide_index=True,

            )

        with right:

            recommendation = str(

                ai_summary["Recommendation"]

            ).upper()

            if recommendation in {

                "BUY",

                "STRONG_BUY",

            }:

                st.success(

                    f"Recommendation: {recommendation}"

                )

            elif recommendation in {

                "SELL",

                "STRONG_SELL",

            }:

                st.error(

                    f"Recommendation: {recommendation}"

                )

            else:

                st.warning(

                    f"Recommendation: {recommendation}"

                )

            st.write(

                "Confidence:",

                ai_summary["AI Confidence"],

            )

            st.write(

                "Macro Regime:",

                ai_summary["Macro Regime"],

            )

            st.write(

                "Institutional Bias:",

                ai_summary["Institutional Bias"],

            )

        # ----------------------------------------------------------------------
        # Portfolio Distribution
        # ----------------------------------------------------------------------

        st.divider()

        st.subheader(
            "Portfolio Distribution"
        )

        distribution = []

        total_units = sum(

            abs(

                float(

                    x.get(
                        "quantity",
                        0,
                    ) or 0

                )

            )

            for x in filtered

        )

        for row in filtered:

            qty = abs(

                float(

                    row.get(
                        "quantity",
                        0,
                    ) or 0

                )

            )

            pct = 0

            if total_units > 0:
                pct = (

                              qty

                              / total_units

                      ) * 100

            distribution.append(

                {

                    "Pair":

                        row.get(
                            "symbol",
                        ),

                    "Units":

                        qty,

                    "Allocation %":

                        round(
                            pct,
                            2,
                        ),

                }

            )

        distribution_df = pd.DataFrame(
            distribution,
        )

        if not distribution_df.empty:
            st.dataframe(

                distribution_df,

                use_container_width=True,

                hide_index=True,

            )

            st.bar_chart(

                distribution_df.set_index(
                    "Pair"
                )[
                    "Allocation %"
                ]

            )

        # ----------------------------------------------------------------------
        # Auto Refresh
        # ----------------------------------------------------------------------

        st.divider()

        st.subheader(
            "Workspace Controls"
        )

        auto_refresh = st.checkbox(

            "Enable Auto Refresh",

            value=False,

        )

        refresh_seconds = st.slider(

            "Refresh Interval (seconds)",

            min_value=5,

            max_value=120,

            value=30,

            step=5,

        )

        if auto_refresh:
            st.info(

                f"Dashboard configured to refresh every "

                f"{refresh_seconds} seconds."

            )

            #
            # Hook for your global refresh framework.
            #
            # Example:
            #
            # refresh_manager.register(
            #     interval=refresh_seconds
            # )
            #

        st.caption(

            "Institutional Forex Position Workspace"

        )
        # ----------------------------------------------------------------------
        # Export Center
        # ----------------------------------------------------------------------

        st.divider()

        st.subheader("Export Center")

        export_format = st.selectbox(

            "Export Format",

            [

                "CSV",

                "JSON",

                "Position Snapshot",

                "Execution Timeline",

            ],

        )

        export_payload = ""

        filename = ""

        if export_format == "CSV":

            export_payload = distribution_df.to_csv(
                index=False,
            )

            filename = "forex_positions.csv"

        elif export_format == "JSON":

            export_payload = pd.DataFrame(
                filtered,
            ).to_json(
                orient="records",
                indent=4,
            )

            filename = "forex_positions.json"

        elif export_format == "Position Snapshot":

            snapshot = {

                "generated_at":
                    datetime.utcnow().isoformat(),

                "positions":
                    filtered,

                "summary": {

                    "positions":
                        len(filtered),

                    "long":

                        sum(

                            1

                            for x in filtered

                            if str(

                                x.get(
                                    "side",
                                    "",
                                )

                            ).upper() == "BUY"

                        ),

                    "short":

                        sum(

                            1

                            for x in filtered

                            if str(

                                x.get(
                                    "side",
                                    "",
                                )

                            ).upper() == "SELL"

                        ),

                },

            }

            import json

            export_payload = json.dumps(

                snapshot,

                indent=4,

                default=str,

            )

            filename = "position_snapshot.json"

        else:

            timeline = explorer.timeline(

                position_id=selected,

            )

            import json

            export_payload = json.dumps(

                timeline,

                indent=4,

                default=str,

            )

            filename = "execution_timeline.json"

        st.download_button(

            "Download",

            export_payload,

            file_name=filename,

            mime="application/octet-stream",

            use_container_width=True,

        )

        # ----------------------------------------------------------------------
        # Dashboard Health
        # ----------------------------------------------------------------------

        st.divider()

        st.subheader(
            "Dashboard Health"
        )

        health = {

            "Dashboard":

                "Forex Positions",

            "Engine":

                engine.health(),

            "Loaded Positions":

                len(filtered),

            "Selected Position":

                selected,

            "Execution Events":

                len(

                    explorer.timeline(

                        position_id=selected,

                    )

                ),

            "Generated":

                datetime.utcnow().isoformat(),

        }

        st.json(

            health,

            expanded=False,

        )

        # ----------------------------------------------------------------------
        # Master Workspace Integration
        # ----------------------------------------------------------------------

        st.divider()

        st.subheader(
            "Workspace Integration"
        )

        integration = {

            "Trading Desk":

                True,

            "Pending Orders":

                True,

            "Execution Service":

                True,

            "Position Engine":

                True,

            "Trade Management":

                True,

            "Risk Dashboard":

                False,

            "Portfolio Optimizer":

                False,

            "Executive AI":

                False,

            "Autonomous Trader":

                False,

        }

        integration_df = pd.DataFrame(

            [

                {

                    "Module": k,

                    "Integrated": v,

                }

                for k, v in integration.items()

            ]

        )

        st.dataframe(

            integration_df,

            use_container_width=True,

            hide_index=True,

        )

        # ----------------------------------------------------------------------
        # Footer
        # ----------------------------------------------------------------------

        st.divider()

        st.caption(

            "Forex Position Dashboard"

            " • Institutional Trading Platform"

            " • Sprint FX"

        )

