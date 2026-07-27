"""
modules/forex/forex_portfolio_dashboard.py
"""


try:
    import streamlit as st
    import pandas as pd
except Exception:
    st=None
    pd=None

from modules.forex.forex_portfolio_manager import get_forex_portfolio_manager

class ForexPortfolioDashboard:

    def __init__(self, db=None):

        self.db = db

    def render(self, **kwargs):

        self.manager = get_forex_portfolio_manager(
            db=self.db,
            tenant_id=kwargs.get("tenant_id"),
            user_id=kwargs.get("user_id"),
            portfolio_id=kwargs.get("portfolio_id"),
        )

        if st is None:
            return

        stats = self.manager.portfolio_statistics()

        portfolios = self.manager.portfolio_list()

        active = self.manager.active_portfolio()

        report = {}

        if active:
            kwargs["portfolio_id"] = active["id"]

            # portfolio_summary() -> mark_positions() always reads live
            # quotes now regardless of any force_refresh flag passed in
            # (see that function's own docstring: "no effect... this
            # always reads live... now") -- so the fix can't be a flag
            # passed down to it; it has to skip the CALL itself when
            # throttled. Streamlit reruns this whole render() on every
            # widget interaction, and this was calling portfolio_
            # summary() (a real, live quote fetch across every open
            # position) unconditionally every single time, with no
            # throttle at all -- unlike forex_terminal_dashboard.py and
            # forex_trading_desk_dashboard.py, which already throttle
            # their equivalent live refresh to once per 15 seconds.
            # Mirrors that same approach here: reuse the last real
            # result from session_state within the throttle window
            # instead of skipping the call via a flag the callee
            # ignores.
            cache_key = f"fx_portfolio_dash_report:{active['id']}"
            ts_key = "fx_portfolio_dash_last_refresh_ts"

            if st is not None:
                import time as _time
                now_ts = _time.time()
                last_refresh_ts = st.session_state.get(ts_key, 0.0)
                cached_report = st.session_state.get(cache_key)

                if cached_report is not None and now_ts - last_refresh_ts < 15.0:
                    report = cached_report
                else:
                    report = self.manager.portfolio_summary(**kwargs)
                    st.session_state[ts_key] = now_ts
                    st.session_state[cache_key] = report
            else:
                report = self.manager.portfolio_summary(**kwargs)

        st.title("💼 Forex Portfolio Management")

        if not portfolios and not st.session_state.get("fx_new_portfolio", False):

            st.warning(
                "No Forex portfolios exist."
            )

            if st.button(
                    "Create First Portfolio",
                    key="fx_create_first_portfolio_btn",
            ):
                st.session_state["fx_new_portfolio"] = True
                st.rerun()
                return

        # ------------------------------------------------------------------
        # Create Portfolio
        # ------------------------------------------------------------------

        if st.session_state.get("fx_new_portfolio", False):

            st.divider()
            st.subheader("Create Forex Portfolio")

            with st.form(
                    "fx_create_portfolio_form",
                    clear_on_submit=False,
            ):

                portfolio_name = st.text_input(
                    "Portfolio Name",
                )

                description = st.text_area(
                    "Description",
                )

                base_currency = st.selectbox(
                    "Base Currency",
                    [
                        "USD",
                        "EUR",
                        "GBP",
                        "JPY",
                        "AUD",
                        "CAD",
                        "CHF",
                        "NZD",
                    ],
                )

                starting_balance = st.number_input(
                    "Starting Balance",
                    min_value=0.0,
                    value=100000.0,
                    step=1000.0,
                )

                default_portfolio = st.checkbox(
                    "Make Default Portfolio",
                    value=(len(portfolios) == 0),
                )

                c1, c2 = st.columns(2)

                create_clicked = c1.form_submit_button(
                    "Create Portfolio",
                    use_container_width=True,
                )

                cancel_clicked = c2.form_submit_button(
                    "Cancel",
                    use_container_width=True,
                )

            if cancel_clicked:
                st.session_state["fx_new_portfolio"] = False

                st.rerun()
                return

            if create_clicked:

                if not portfolio_name.strip():

                    st.error(
                        "Portfolio name is required."
                    )

                else:

                    portfolio_id = self.manager.create_portfolio(

                        name=portfolio_name.strip(),

                        description=description.strip(),

                        base_currency=base_currency,

                        starting_balance=starting_balance,

                        is_default=default_portfolio,

                    )

                    st.session_state["active_forex_portfolio"] = portfolio_id

                    st.session_state["fx_new_portfolio"] = False

                    st.success(
                        "Portfolio created successfully."
                    )

                    st.rerun()
                    return



        st.header("💼 Forex Portfolio")

        s=report.get("summary",{})
        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "Portfolios",
            stats["portfolio_count"],
        )

        c2.metric(
            "Default",
            stats["default_portfolio"] or "-",
        )

        c3.metric(
            "Starting Equity",
            f"${stats['combined_starting_balance']:,.2f}",
        )

        c4.metric(
            "Current Equity",
            f"${stats['combined_balance']:,.2f}",
        )
        st.divider()

        if portfolios:

            portfolio_lookup = {
                p["name"]: p
                for p in portfolios
            }

            current_name = None

            if active:
                current_name = active["name"]

            selected_name = st.selectbox(
                "Active Portfolio",
                options=list(portfolio_lookup.keys()),
                index=(
                    list(portfolio_lookup.keys()).index(current_name)
                    if current_name in portfolio_lookup
                    else 0
                ),
                key="fx_active_portfolio_selector",
            )

            selected = portfolio_lookup[selected_name]

            if (
                    active is None
                    or selected["id"] != active["id"]
            ):
                self.manager.set_default_portfolio(
                    selected["id"],
                )

                st.session_state[
                    "active_forex_portfolio"
                ] = selected["id"]

                st.rerun()
                return

            # ------------------------------------------------------------------
            # Portfolio Details
            # ------------------------------------------------------------------

            if active:

                st.divider()

                st.subheader("Portfolio Details")

                left, right = st.columns(2)

                with left:

                    st.text_input(
                        "Portfolio Name",
                        value=active["name"],
                        disabled=True,
                    )

                    st.text_input(
                        "Base Currency",
                        value=active["base_currency"],
                        disabled=True,
                    )

                    st.text_input(
                        "Status",
                        value=active["status"],
                        disabled=True,
                    )

                with right:

                    st.text_area(
                        "Description",
                        value=active.get("description", ""),
                        disabled=True,
                    )

                    st.text_input(
                        "Created",
                        value=str(active.get("created_at", "")),
                        disabled=True,
                    )

                    st.text_input(
                        "Updated",
                        value=str(active.get("updated_at", "")),
                        disabled=True,
                    )

                a, b, c = st.columns(3)

                if a.button(
                        "Edit Portfolio",
                        key="fx_edit_portfolio_btn",
                        use_container_width=True,
                ):
                    st.session_state["fx_edit_portfolio"] = True

                if b.button(
                        "Archive Portfolio",
                        key="fx_archive_portfolio_btn",
                        use_container_width=True,
                ):
                    st.session_state["fx_archive_portfolio"] = True

                if c.button(
                        "Delete Portfolio",
                        key="fx_delete_portfolio_btn",
                        use_container_width=True,
                ):
                    st.session_state["fx_delete_portfolio"] = True

                # ------------------------------------------------------------------
                # Edit Portfolio
                # ------------------------------------------------------------------

                if (
                        active
                        and st.session_state.get("fx_edit_portfolio", False)
                ):

                    st.divider()

                    st.subheader("Edit Portfolio")

                    with st.form("fx_edit_portfolio_form"):

                        name = st.text_input(
                            "Portfolio Name",
                            value=active["name"],
                        )

                        description = st.text_area(
                            "Description",
                            value=active.get("description", ""),
                        )

                        currency = st.selectbox(
                            "Base Currency",
                            [
                                "USD",
                                "EUR",
                                "GBP",
                                "JPY",
                                "AUD",
                                "CAD",
                                "CHF",
                                "NZD",
                            ],
                            index=[
                                "USD",
                                "EUR",
                                "GBP",
                                "JPY",
                                "AUD",
                                "CAD",
                                "CHF",
                                "NZD",
                            ].index(active["base_currency"]),
                        )

                        status = st.selectbox(
                            "Status",
                            [
                                "ACTIVE",
                                "ARCHIVED",
                            ],
                            index=0 if active["status"] == "ACTIVE" else 1,
                        )

                        c1, c2 = st.columns(2)

                        save = c1.form_submit_button(
                            "Save Changes",
                            use_container_width=True,
                        )

                        cancel = c2.form_submit_button(
                            "Cancel",
                            use_container_width=True,
                        )

                    if cancel:
                        st.session_state["fx_edit_portfolio"] = False

                        st.rerun()
                        return

                    if save:
                        self.manager.update_portfolio(

                            portfolio_id=active["id"],

                            name=name,

                            description=description,

                            base_currency=currency,

                            status=status,

                        )

                        st.session_state["fx_edit_portfolio"] = False

                        st.success("Portfolio updated.")

                        st.rerun()
                        return

                    if (
                            active
                            and st.session_state.get("fx_archive_portfolio", False)
                    ):

                        st.warning(
                            f"Archive '{active['name']}'?"
                        )

                        c1, c2 = st.columns(2)

                        if c1.button(
                                "Confirm Archive",
                                key="fx_confirm_archive_btn",
                        ):
                            self.manager.archive_portfolio(
                                active["id"],
                            )

                            st.session_state["fx_archive_portfolio"] = False

                            st.rerun()
                            return

                        if c2.button(
                                "Cancel",
                                key="fx_cancel_archive_btn",
                        ):
                            st.session_state["fx_archive_portfolio"] = False

                            st.rerun()
                            return
                    if (
                            active
                            and st.session_state.get("fx_delete_portfolio", False)
                    ):

                        st.error(
                            f"Delete '{active['name']}'?"
                        )

                        st.caption(
                            "This action cannot be undone."
                        )

                        c1, c2 = st.columns(2)

                        if c1.button(
                                "Delete Portfolio",
                                key="fx_confirm_delete_btn",
                        ):
                            self.manager.delete_portfolio(
                                active["id"],
                            )

                            st.session_state["fx_delete_portfolio"] = False

                            st.rerun()
                            return

                        if c2.button(
                                "Cancel",
                                key="fx_cancel_delete_btn",
                        ):
                            st.session_state["fx_delete_portfolio"] = False

                            st.rerun()
                            return

        # ------------------------------------------------------------------
        # Portfolio Workspace
        # ------------------------------------------------------------------

        # Every workspace tab below assumes an active portfolio (they all
        # read active["id"]) but this section previously ran unconditionally
        # - with zero portfolios, or portfolios existing but none yet marked
        # active, this crashed with TypeError: 'NoneType' object is not
        # subscriptable instead of showing the empty-state message the rest
        # of render() already has a pattern for.
        if not active:
            st.info("Select or create a portfolio above to view this workspace.")
            return

        workspace = st.radio(
            "Portfolio Workspace",
            [
                "Overview",
                "Positions",
                "Performance",
                "Transactions",
                "Risk",
                "Settings",
            ],
            horizontal=True,
            key="fx_portfolio_workspace",
        )

        # ==============================================================
        # OVERVIEW
        # ==============================================================

        if workspace == "Overview":

            report = self.manager.portfolio_summary(
                portfolio_id=active["id"],
            )

            summary = report.get("summary", {})

            a, b, c, d = st.columns(4)

            a.metric(
                "Cash",
                f"${summary.get('cash_balance', 0):,.2f}",
            )

            b.metric(
                "Equity",
                f"${summary.get('equity', 0):,.2f}",
            )

            c.metric(
                "Open Positions",
                summary.get("open_positions", 0),
            )

            d.metric(
                "Buying Power",
                f"${summary.get('buying_power', 0):,.2f}",
            )

            st.divider()

            st.subheader("Portfolio Snapshot")

            st.json(summary)

        # ==============================================================
        # POSITIONS
        # ==============================================================

        elif workspace == "Positions":

            positions = report.get(
                "positions",
                [],
            )

            tenant_id = kwargs.get("tenant_id") or "default"
            user_id = kwargs.get("user_id") or "default"

            if positions:

                st.dataframe(
                    pd.DataFrame(positions),
                    use_container_width=True,
                    hide_index=True,
                )

                st.divider()
                st.subheader("Manage Positions")

                from api.services.forex_position_management_api_service import (
                    ForexPositionManagementAPIService,
                )

                position_service = ForexPositionManagementAPIService(self.db)

                flatten_col, _ = st.columns([1, 3])
                if flatten_col.button(
                    "🚫 Flatten All Positions",
                    key="fx_flatten_all_btn",
                ):
                    result = position_service.flatten_account(
                        tenant_id=tenant_id,
                        user_id=user_id,
                        portfolio_id=active["id"],
                    )
                    st.success(
                        f"Closed {result['closed_count']} position(s)."
                    )
                    st.rerun()

                for position in positions:

                    position_id = position.get("id")
                    pair = position.get("pair", "?")
                    side = position.get("side", "?")
                    units = position.get("units", 0)

                    with st.expander(
                        f"{pair} — {side} {units:,.0f} units",
                    ):

                        c1, c2 = st.columns(2)

                        if c1.button(
                            "Close",
                            key=f"fx_close_{position_id}",
                        ):
                            result = position_service.close_position(
                                tenant_id=tenant_id,
                                user_id=user_id,
                                position_id=position_id,
                            )
                            if result is None:
                                st.error("Position not found.")
                            elif result["status"] in ("CLOSED", "PARTIALLY_CLOSED"):
                                st.success(f"Position {result['status'].lower()}.")
                                st.rerun()
                            else:
                                st.error(result.get("message") or "Close failed.")

                        if c2.button(
                            "Reverse",
                            key=f"fx_reverse_{position_id}",
                        ):
                            result = position_service.reverse_position(
                                tenant_id=tenant_id,
                                user_id=user_id,
                                position_id=position_id,
                            )
                            if result is None:
                                st.error("Position not found.")
                            elif result["status"] == "REVERSED":
                                st.success("Position reversed.")
                                st.rerun()
                            else:
                                st.error(result.get("message") or "Reverse failed.")

                        with st.form(f"fx_modify_form_{position_id}"):

                            st.caption("Update stop-loss / take-profit (leave blank to keep unchanged)")

                            mc1, mc2 = st.columns(2)
                            new_stop = mc1.number_input(
                                "Stop Price",
                                min_value=0.0,
                                value=float(position.get("stop_price") or 0.0),
                                key=f"fx_stop_{position_id}",
                            )
                            new_target = mc2.number_input(
                                "Target Price",
                                min_value=0.0,
                                value=float(position.get("target_price") or 0.0),
                                key=f"fx_target_{position_id}",
                            )

                            if st.form_submit_button("Update"):
                                result = position_service.modify_position(
                                    tenant_id=tenant_id,
                                    user_id=user_id,
                                    position_id=position_id,
                                    stop_price=new_stop if new_stop > 0 else None,
                                    target_price=new_target if new_target > 0 else None,
                                )
                                if result is None:
                                    st.error("Position not found.")
                                elif result["status"] == "MODIFIED":
                                    st.success("Position updated.")
                                    st.rerun()
                                else:
                                    st.error(result.get("message") or "Update failed.")

            else:

                st.info(
                    "No open positions."
                )

        # ==============================================================
        # PERFORMANCE
        # ==============================================================

        elif workspace == "Performance":

            perf = report.get(
                "performance",
                {},
            )

            c1, c2, c3, c4 = st.columns(4)

            c1.metric(
                "Total Return",
                f"{perf.get('return_pct', 0):.2f}%",
            )

            c2.metric(
                "Realized P&L",
                f"${perf.get('realized_pnl', 0):,.2f}",
            )

            c3.metric(
                "Unrealized P&L",
                f"${perf.get('unrealized_pnl', 0):,.2f}",
            )

            c4.metric(
                "Win Rate",
                f"{perf.get('win_rate', 0):.1f}%",
            )

            if perf.get("equity_curve"):

                equity = pd.DataFrame(
                    perf["equity_curve"]
                )

                if {
                    "date",
                    "equity",
                }.issubset(equity.columns):
                    st.line_chart(
                        equity.set_index("date")[
                            "equity"
                        ]
                    )

        # ==============================================================
        # TRANSACTIONS
        # ==============================================================

        elif workspace == "Transactions":

            tx = report.get(
                "transactions",
                [],
            )

            if tx:

                st.dataframe(
                    pd.DataFrame(tx),
                    use_container_width=True,
                    hide_index=True,
                )

            else:

                st.info(
                    "No transactions."
                )

        # ==============================================================
        # RISK
        # ==============================================================

        elif workspace == "Risk":

            st.json(
                report.get(
                    "risk",
                    {},
                )
            )

        # ==============================================================
        # SETTINGS
        # ==============================================================

        else:

            st.subheader(
                "Portfolio Settings"
            )

            st.write(
                f"Portfolio ID: {active['id']}"
            )

            st.write(
                f"Base Currency: {active['base_currency']}"
            )

            st.write(
                f"Status: {active['status']}"
            )

            if st.button(
                    "Refresh Portfolio",
                    key="fx_refresh_portfolio_btn",
                    use_container_width=True,
            ):
                st.rerun()
                return



_INSTANCE=None

def get_forex_portfolio_dashboard(db=None):

    global _INSTANCE

    if (
        _INSTANCE is None
        or _INSTANCE.db is not db
    ):

        _INSTANCE = ForexPortfolioDashboard(
            db=db,
        )

    return _INSTANCE

def render_forex_portfolio_dashboard(db=None, **kwargs):
    return get_forex_portfolio_dashboard(db=db).render(**kwargs)