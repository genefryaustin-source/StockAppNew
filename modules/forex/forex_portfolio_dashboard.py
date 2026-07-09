
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

            report = self.manager.portfolio_summary(
                **kwargs,
            )

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

                        if c2.button(
                                "Cancel",
                                key="fx_cancel_archive_btn",
                        ):
                            st.session_state["fx_archive_portfolio"] = False

                            st.rerun()
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

                        if c2.button(
                                "Cancel",
                                key="fx_cancel_delete_btn",
                        ):
                            st.session_state["fx_delete_portfolio"] = False

                            st.rerun()

        # ------------------------------------------------------------------
        # Portfolio Workspace
        # ------------------------------------------------------------------

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

            if positions:

                st.dataframe(
                    pd.DataFrame(positions),
                    use_container_width=True,
                    hide_index=True,
                )

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
