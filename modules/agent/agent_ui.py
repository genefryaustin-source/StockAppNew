"""
modules/agent/agent_ui.py

Agentic Portfolio Manager — Streamlit UI.

Full page with:
  - Create agent: set budget, strategy instruction, risk level, schedule
  - Agent dashboard: P&L, position count, trade count, last run
  - Real-time activity feed: every decision with reasoning
  - Kill switch (one click, stops mid-cycle)
  - Run cycle manually
  - Per-agent portfolio view

Add to app.py:
    pages list: "AI Agent"
    elif page == "AI Agent":
        from modules.agent.agent_ui import render_agent_page
        render_agent_page(db, user)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import streamlit as st

from modules.agent.agent_engine import (
    AgentEngine,
    AgentPortfolio,
    create_agent_portfolio,
    ensure_tables,
    get_activity_log,
    kill_agent,
    list_agents,
    revive_agent,
)


# ─────────────────────────────────────────────────────────────
# Example strategy instructions
# ─────────────────────────────────────────────────────────────

STRATEGY_EXAMPLES = [
    "Growth tech stocks with strong momentum and composite score above 70",
    "High-quality defensive stocks: healthcare and consumer staples, low risk",
    "Momentum-driven portfolio: top 10 stocks by momentum score, rebalance weekly",
    "Diversified value play: cheap stocks with PE under 20 and strong quality",
    "AI and semiconductor sector focus with buy ratings only",
    "Balanced growth: mix of tech and healthcare, max 15% per position",
    "Aggressive growth: highest composite score stocks under $100",
    "Dividend-quality focus: financials and utilities with high quality scores",
]

EVENT_ICONS = {
    "CYCLE_START":     "🔄",
    "ANALYSIS":        "🔍",
    "DECISION":        "🧠",
    "TRADE_EXECUTED":  "✅",
    "TRADE_SKIPPED":   "⏭️",
    "REBALANCE":       "⚖️",
    "KILL_SWITCH":     "🛑",
    "ERROR":           "❌",
    "INFO":            "ℹ️",
}

ACTION_COLORS = {
    "BUY":  "🟢",
    "SELL": "🔴",
    "HOLD": "🟡",
    "SKIP": "⚫",
}


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _load_portfolios(db, tenant_id: str) -> list:
    """Load available paper portfolios to link the agent to."""
    try:
        from sqlalchemy import text
        rows = db.execute(text(
            "SELECT id, name FROM portfolios WHERE tenant_id = :tid ORDER BY created_at DESC"
        ), {"tid": tenant_id}).fetchall()
        return rows
    except Exception:
        return []


def _get_agent_metrics(db, agent: AgentPortfolio) -> dict:
    """Get P&L and position metrics for an agent's linked portfolio."""
    if not agent.portfolio_id:
        return {}
    try:
        from modules.portfolio.accounting_service import AccountingService
        acct   = AccountingService(db)
        totals = acct.portfolio_totals(agent.portfolio_id)
        return totals
    except Exception:
        return {}


def _format_ts(dt) -> str:
    if not dt:
        return "Never"
    try:
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.strftime("%b %d %H:%M")
    except Exception:
        return str(dt)[:16]


# ─────────────────────────────────────────────────────────────
# Main page
# ─────────────────────────────────────────────────────────────

def render_agent_page(db, user: dict):
    tenant_id = user.get("tenant_id", "")
    user_id   = user.get("user_id", "")

    ensure_tables(db)

    st.header("🤖 Agentic Portfolio Manager")
    st.caption(
        "Claude autonomously constructs and rebalances a portfolio within your set budget. "
        "Every decision is explained in the activity feed. Kill switch stops it instantly."
    )

    # ── Global kill-all banner ────────────────────────────────
    agents = list_agents(db, tenant_id)
    active_agents = [a for a in agents if a.active and not a.killed]

    if active_agents:
        col_status, col_killall = st.columns([4, 1])
        with col_status:
            st.success(f"✅ {len(active_agents)} agent(s) active")
        with col_killall:
            if st.button("🛑 Kill All Agents", type="secondary", use_container_width=True,
                         key="kill_all_agents"):
                for a in active_agents:
                    kill_agent(db, a.id, tenant_id, "Kill All activated by user")
                st.rerun()

    tab_agents, tab_create = st.tabs([
        f"🤖 My Agents ({len(agents)})",
        "➕ Create Agent",
    ])

    with tab_create:
        _render_create_tab(db, tenant_id, user_id)

    with tab_agents:
        _render_agents_tab(db, tenant_id, agents)


# ─────────────────────────────────────────────────────────────
# Create tab
# ─────────────────────────────────────────────────────────────

def _render_create_tab(db, tenant_id: str, user_id: str):
    st.subheader("Configure a new AI agent")

    # Example strategy chips
    with st.expander("💡 Example strategies", expanded=False):
        cols = st.columns(2)
        for i, ex in enumerate(STRATEGY_EXAMPLES):
            with cols[i % 2]:
                if st.button(ex, key=f"agent_ex_{i}", use_container_width=True):
                    st.session_state["agent_strategy_input"] = ex

    with st.form("create_agent_form"):
        st.markdown("#### Strategy")
        strategy = st.text_area(
            "What should the agent invest in?",
            placeholder="e.g. Growth tech stocks with strong momentum and composite score above 70",
            key="agent_strategy_input",
            height=80,
        )

        st.markdown("#### Budget & Risk")
        c1, c2, c3 = st.columns(3)
        with c1:
            budget = st.number_input(
                "Agent budget ($)", min_value=1000.0, max_value=1000000.0,
                value=10000.0, step=1000.0,
            )
        with c2:
            max_pos = st.slider("Max positions", 3, 25, 10)
        with c3:
            risk_level = st.selectbox(
                "Risk level", ["conservative", "moderate", "aggressive"],
                index=1,
            )

        st.markdown("#### Linked Portfolio")
        portfolios = _load_portfolios(db, tenant_id)
        port_options = {str(p[0]): p[1] for p in portfolios} if portfolios else {}

        if port_options:
            linked_port = st.selectbox(
                "Link to paper portfolio",
                options=list(port_options.keys()),
                format_func=lambda x: port_options[x],
                help="The agent will execute trades in this paper portfolio.",
            )
        else:
            st.warning(
                "No paper portfolios found. Create one in the Portfolio page first. "
                "The agent needs a portfolio to execute trades in."
            )
            linked_port = None

        agent_name = st.text_input(
            "Agent name", value="My AI Agent",
            placeholder="e.g. Growth Tech Agent",
        )

        st.caption(
            "⚠️ This agent will autonomously execute paper trades using the AI ranking engine. "
            "It only trades in paper mode. You can kill it at any time."
        )

        submit = st.form_submit_button("🚀 Launch Agent", type="primary")

    if submit:
        if not strategy.strip():
            st.error("Please enter a strategy instruction.")
            return
        if not linked_port:
            st.error("Please create a paper portfolio first.")
            return

        agent = create_agent_portfolio(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            name=agent_name.strip() or "My AI Agent",
            strategy_instruction=strategy.strip(),
            budget=budget,
            max_positions=max_pos,
            risk_level=risk_level,
            linked_portfolio_id=linked_port,
        )

        st.success(
            f"✅ Agent **{agent.name}** launched! "
            "Go to **My Agents** tab and click **▶ Run Cycle** to start."
        )
        st.rerun()


# ─────────────────────────────────────────────────────────────
# Agents tab
# ─────────────────────────────────────────────────────────────

def _render_agents_tab(db, tenant_id: str, agents: list):
    if not agents:
        st.info(
            "No agents yet. Go to **➕ Create Agent** to launch your first AI agent."
        )
        return

    for agent in agents:
        _render_agent_card(db, tenant_id, agent)


def _render_agent_card(db, tenant_id: str, agent: AgentPortfolio):
    """Render one agent card with status, metrics, activity feed, and controls."""

    is_killed = bool(agent.killed)
    is_active = bool(agent.active) and not is_killed

    status_icon  = "🟢" if is_active else "🔴"
    status_label = "Active" if is_active else ("Killed" if is_killed else "Paused")

    with st.expander(
        f"{status_icon} **{agent.name}** · {status_label} · "
        f"${agent.budget:,.0f} budget · "
        f"{agent.run_count or 0} runs · "
        f"{agent.total_trades or 0} trades",
        expanded=True,
    ):

        # ── Header metrics ────────────────────────────────────
        metrics = _get_agent_metrics(db, agent)

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Status",        f"{status_icon} {status_label}")
        c2.metric("Budget",        f"${agent.budget:,.0f}")
        c3.metric("Equity",        f"${metrics.get('equity', 0):,.2f}" if metrics else "—")
        c4.metric("Net P&L",       f"${metrics.get('net_pnl', 0):+,.2f}" if metrics else "—",
                  delta_color="normal" if metrics.get("net_pnl", 0) >= 0 else "inverse")
        c5.metric("Trades",        agent.total_trades or 0)

        # Strategy + last run
        st.markdown(f"**Strategy:** {agent.strategy_instruction}")
        st.caption(
            f"Risk: {agent.risk_level} · "
            f"Max positions: {agent.max_positions} · "
            f"Last run: {_format_ts(agent.last_run)} · "
            f"Created: {_format_ts(agent.created_at)}"
        )

        if is_killed and agent.kill_reason:
            st.error(f"🛑 Killed: {agent.kill_reason}")

        # ── Action buttons ────────────────────────────────────
        st.markdown("---")
        btn_cols = st.columns(5)

        with btn_cols[0]:
            run_btn = st.button(
                "▶ Run Cycle",
                key=f"agent_run_{agent.id}",
                type="primary",
                disabled=is_killed,
                use_container_width=True,
            )

        with btn_cols[1]:
            if is_killed:
                revive_btn = st.button(
                    "🔄 Revive",
                    key=f"agent_revive_{agent.id}",
                    use_container_width=True,
                )
                if revive_btn:
                    revive_agent(db, agent.id, tenant_id)
                    st.rerun()
            else:
                kill_btn = st.button(
                    "🛑 Kill Switch",
                    key=f"agent_kill_{agent.id}",
                    type="secondary",
                    use_container_width=True,
                )
                if kill_btn:
                    kill_agent(db, agent.id, tenant_id)
                    st.rerun()

        with btn_cols[2]:
            refresh_btn = st.button(
                "↺ Refresh Feed",
                key=f"agent_refresh_{agent.id}",
                use_container_width=True,
            )

        with btn_cols[3]:
            # Auto-refresh toggle
            auto_key = f"agent_auto_{agent.id}"
            auto = st.toggle("Auto-refresh", key=auto_key, value=False)

        with btn_cols[4]:
            delete_btn = st.button(
                "🗑 Delete",
                key=f"agent_delete_{agent.id}",
                use_container_width=True,
            )
            if delete_btn:
                try:
                    db.delete(agent)
                    db.commit()
                    st.rerun()
                except Exception as e:
                    db.rollback()
                    st.error(f"Delete failed: {e}")

        # ── Run cycle ─────────────────────────────────────────
        if run_btn:
            if is_killed:
                st.error("Agent is killed. Click Revive first.")
            else:
                with st.spinner(
                    f"Running agent cycle… Claude is analysing your universe and making decisions."
                ):
                    engine = AgentEngine(db, agent)
                    result = engine.run_cycle()

                trades = result.get("trades", 0)
                status = result.get("status", "")

                if status == "killed":
                    st.error("🛑 Agent was killed during execution.")
                elif status == "no_data":
                    st.warning("No universe data found. Run analytics first.")
                elif status in ("api_error", "no_plan"):
                    st.error(f"Cycle failed: {status}. Check ANTHROPIC_API_KEY.")
                elif trades == 0:
                    st.info("✅ Cycle complete — no trades needed. Portfolio aligned with strategy.")
                else:
                    st.success(f"✅ Cycle complete — {trades} trade(s) executed.")

                st.rerun()

        # ── Auto-refresh ──────────────────────────────────────
        if auto:
            import time
            time.sleep(5)
            st.rerun()

        # ── Activity feed ─────────────────────────────────────
        st.markdown("#### 📡 Activity Feed")

        log_entries = get_activity_log(db, agent.id, limit=50)

        if not log_entries:
            st.info("No activity yet. Click **▶ Run Cycle** to start the agent.")
        else:
            _render_activity_feed(log_entries)

        # ── Current positions ─────────────────────────────────
        if agent.portfolio_id and metrics:
            st.markdown("#### 📊 Current Positions")
            _render_positions(db, agent)


def _render_activity_feed(entries: list):
    """Render the real-time activity feed."""
    for entry in entries:
        event_type = entry.event_type or "INFO"
        icon       = EVENT_ICONS.get(event_type, "•")
        ts         = _format_ts(entry.created_at)

        # Color coding
        if event_type == "TRADE_EXECUTED":
            action_icon = ACTION_COLORS.get(entry.action, "")
            header = f"{icon} {action_icon} **{entry.symbol}** {entry.action}"
            if entry.qty and entry.price:
                header += f" · {entry.qty:.2f} shares @ ${entry.price:.2f}"
            if entry.notional:
                header += f" · ${entry.notional:,.2f}"
            st.success(f"`{ts}` {header}")
            if entry.reasoning:
                st.caption(f"&nbsp;&nbsp;&nbsp;&nbsp;{entry.reasoning}")

        elif event_type == "KILL_SWITCH":
            st.error(f"`{ts}` {icon} {entry.reasoning}")

        elif event_type == "ERROR":
            st.error(f"`{ts}` {icon} {entry.reasoning}")
            if entry.error_message:
                st.caption(f"&nbsp;&nbsp;&nbsp;&nbsp;Error: {entry.error_message}")

        elif event_type == "DECISION":
            st.info(f"`{ts}` {icon} {entry.reasoning}")

        elif event_type == "TRADE_SKIPPED":
            sym = entry.symbol or ""
            action_icon = ACTION_COLORS.get(entry.action, "⚫")
            st.markdown(
                f"`{ts}` {icon} {action_icon} **{sym}** SKIPPED — {entry.reasoning}",
            )

        elif event_type == "CYCLE_START":
            if "complete" in (entry.reasoning or "").lower():
                st.markdown(f"`{ts}` {icon} {entry.reasoning}")
            else:
                st.markdown(f"---")
                st.markdown(f"`{ts}` {icon} **{entry.reasoning}**")

        else:
            st.markdown(f"`{ts}` {icon} {entry.reasoning}")


def _render_positions(db, agent: AgentPortfolio):
    """Show current positions in the agent's linked portfolio."""
    try:
        from sqlalchemy import text
        rows = db.execute(text("""
            SELECT symbol, qty, avg_cost, market_value
            FROM portfolio_positions
            WHERE portfolio_id = :pid AND qty > 0
        """), {"pid": agent.portfolio_id}).mappings().fetchall()

        if not rows:
            st.caption("No open positions.")
            return

        total_mv = sum(float(r["market_value"] or 0) for r in rows)
        data = [{
            "Symbol":        r["symbol"],
            "Qty":           f"{float(r['qty']):.2f}",
            "Avg Cost":      f"${float(r['avg_cost'] or 0):,.2f}",
            "Market Value":  f"${float(r['market_value'] or 0):,.2f}",
            "Weight":        f"{float(r['market_value'] or 0) / total_mv * 100:.1f}%"
                             if total_mv else "—",
        } for r in rows]

        st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)

    except Exception as e:
        st.caption(f"Position load error: {e}")