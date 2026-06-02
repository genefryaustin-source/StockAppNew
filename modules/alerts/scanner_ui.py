"""
modules/alerts/scanner_ui.py

AI Market Scanner — Streamlit UI.

Full page for:
  - Writing plain-English alert rules
  - Reviewing parsed conditions before saving
  - Managing saved rules (enable/disable/delete)
  - Running scans manually or on schedule
  - Viewing fired alerts

Add to app.py pages list: "AI Scanner"
Add route:
    elif page == "AI Scanner":
        from modules.alerts.scanner_ui import render_scanner_page
        render_scanner_page(db, user)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import streamlit as st
from sqlalchemy import text

from modules.alerts.scanner_engine import (
    ScanCondition,
    ScannerRule,
    evaluate_condition,
    run_scanner_rule,
    translate_rule,
)


# ─────────────────────────────────────────────────────────────
# Example rules shown to users
# ─────────────────────────────────────────────────────────────

EXAMPLE_RULES = [
    "Alert me when a stock breaks above its 52-week high on 2x average volume",
    "Notify me when any tech stock has RSI below 30 and composite score above 70",
    "Alert when any position drops more than 3% in a single day",
    "Find buy-rated stocks trading below their 200-day moving average",
    "Alert when a healthcare stock has momentum above 70 and risk below 40",
    "Notify me when any stock is within 1% of its support level",
    "Alert on stocks with composite above 80 and day gain over 2%",
    "Find oversold quality stocks in financials with RSI under 25",
]


# ─────────────────────────────────────────────────────────────
# DB helpers
# ─────────────────────────────────────────────────────────────

def _ensure_table(db):
    """Create scanner rules table if it doesn't exist."""
    try:
        from modules.db.core import engine as _engine
        ScannerRule.__table__.create(bind=_engine, checkfirst=True)
    except Exception as e:
        print(f"[scanner_ui] table create: {e}")


def _load_rules(db, tenant_id: str) -> list[ScannerRule]:
    try:
        return (
            db.query(ScannerRule)
            .filter(ScannerRule.tenant_id == tenant_id)
            .order_by(ScannerRule.created_at.desc())
            .all()
        )
    except Exception:
        return []


def _load_symbols(db, tenant_id: str) -> list[str]:
    """Pull symbols from analytics snapshots (user's universe)."""
    try:
        from modules.analytics.models import AnalyticsSnapshot
        rows = (
            db.query(AnalyticsSnapshot.symbol)
            .filter(AnalyticsSnapshot.tenant_id == tenant_id)
            .distinct()
            .all()
        )
        return sorted([r[0] for r in rows if r and r[0]])
    except Exception:
        return []


def _save_rule(
    db,
    tenant_id: str,
    user_id: str,
    name: str,
    description: str,
    condition: ScanCondition,
    scope: str = "universe",
) -> ScannerRule:
    rule = ScannerRule(
        tenant_id=tenant_id,
        user_id=user_id,
        name=name,
        description=description,
        condition=json.dumps(condition.to_dict()),
        scope=scope,
        active=True,
    )
    db.add(rule)
    db.commit()
    return rule


def _delete_rule(db, rule_id: str, tenant_id: str):
    try:
        rule = (
            db.query(ScannerRule)
            .filter(ScannerRule.id == rule_id,
                    ScannerRule.tenant_id == tenant_id)
            .first()
        )
        if rule:
            db.delete(rule)
            db.commit()
    except Exception as e:
        db.rollback()
        st.error(f"Delete failed: {e}")


def _toggle_rule(db, rule_id: str, tenant_id: str, active: bool):
    try:
        rule = (
            db.query(ScannerRule)
            .filter(ScannerRule.id == rule_id,
                    ScannerRule.tenant_id == tenant_id)
            .first()
        )
        if rule:
            rule.active = active
            db.commit()
    except Exception as e:
        db.rollback()


# ─────────────────────────────────────────────────────────────
# Main page
# ─────────────────────────────────────────────────────────────

def render_scanner_page(db, user: dict):
    tenant_id = user.get("tenant_id", "")
    user_id   = user.get("user_id", "")

    _ensure_table(db)

    st.header("🔭 AI Market Scanner")
    st.caption(
        "Write alert rules in plain English. Claude translates them into "
        "precise conditions that scan your universe automatically."
    )

    tab_create, tab_rules, tab_alerts = st.tabs([
        "✍️ Create Rule",
        "📋 My Rules",
        "🔔 Fired Alerts",
    ])

    with tab_create:
        _render_create_tab(db, tenant_id, user_id)

    with tab_rules:
        _render_rules_tab(db, tenant_id)

    with tab_alerts:
        _render_alerts_tab(db, tenant_id)


# ─────────────────────────────────────────────────────────────
# Tab 1 — Create Rule
# ─────────────────────────────────────────────────────────────

def _render_create_tab(db, tenant_id: str, user_id: str):
    st.subheader("Write a new scanner rule")

    # Example chips
    with st.expander("💡 Example rules", expanded=False):
        cols = st.columns(2)
        for i, ex in enumerate(EXAMPLE_RULES):
            with cols[i % 2]:
                if st.button(ex, key=f"scanner_ex_{i}", use_container_width=True):
                    st.session_state["scanner_rule_input"] = ex

    rule_text = st.text_area(
        "Describe your alert rule",
        placeholder="e.g. Alert me when a stock breaks above its 52-week high on 2x average volume",
        key="scanner_rule_input",
        height=80,
    )

    col_parse, col_clear = st.columns([1, 5])
    with col_parse:
        parse_btn = st.button(
            "🧠 Parse Rule",
            type="primary",
            key="scanner_parse_btn",
            use_container_width=True,
        )
    with col_clear:
        if st.button("✕ Clear", key="scanner_clear_btn"):
            for k in ["scanner_rule_input", "scanner_parsed_condition"]:
                if k in st.session_state:
                    del st.session_state[k]
            st.rerun()

    if parse_btn and rule_text.strip():
        with st.spinner("Translating rule with Claude…"):
            condition = translate_rule(rule_text)
            st.session_state["scanner_parsed_condition"] = condition
            st.session_state["scanner_parsed_rule_text"] = rule_text

    condition: Optional[ScanCondition] = st.session_state.get("scanner_parsed_condition")

    if not condition:
        st.info("Enter a rule above and click **🧠 Parse Rule** to see how Claude interprets it.")
        return

    # ── Show parsed condition ─────────────────────────────────
    st.markdown("---")
    st.markdown("#### ✅ Parsed Condition")

    if condition.plain_summary:
        st.success(condition.plain_summary)

    for w in condition.warnings:
        st.warning(f"⚠️ {w}")

    _render_condition_badges(condition)

    # Show full condition detail
    with st.expander("View full parsed condition", expanded=False):
        st.json(condition.to_dict())

    # ── Test on one symbol ────────────────────────────────────
    st.markdown("#### 🧪 Test on a symbol")
    test_col, btn_col = st.columns([2, 1])
    with test_col:
        test_sym = st.text_input(
            "Test symbol", value="NVDA",
            key="scanner_test_sym",
            label_visibility="collapsed",
        )
    with btn_col:
        test_btn = st.button("▶ Test", key="scanner_test_btn", use_container_width=True)

    if test_btn and test_sym:
        with st.spinner(f"Evaluating {test_sym.upper()}…"):
            try:
                db.rollback()
            except Exception:
                pass
            fired, reason = evaluate_condition(
                test_sym.upper(), condition, db
            )
        if fired:
            st.success(f"✅ **{test_sym.upper()} WOULD FIRE** — {reason}")
        else:
            st.info(f"❌ {test_sym.upper()} would NOT fire — {reason}")

    # ── Save rule ─────────────────────────────────────────────
    st.markdown("#### 💾 Save Rule")
    rule_name = st.text_input(
        "Rule name",
        value=condition.alert_title or "My Scanner Rule",
        key="scanner_rule_name",
    )

    save_btn = st.button(
        "💾 Save & Activate Rule",
        type="primary",
        key="scanner_save_btn",
    )

    if save_btn and rule_name:
        rule_text_saved = st.session_state.get("scanner_parsed_rule_text", rule_text)
        rule = _save_rule(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            name=rule_name,
            description=rule_text_saved,
            condition=condition,
        )
        st.success(
            f"✅ Rule **{rule_name}** saved and active. "
            "Go to **My Rules** to run it against your universe."
        )
        # Clear the form
        for k in ["scanner_parsed_condition", "scanner_rule_input"]:
            if k in st.session_state:
                del st.session_state[k]


def _render_condition_badges(condition: ScanCondition):
    """Render a compact visual summary of the parsed condition."""
    badge_map = [
        ("price_above_52w_high",     lambda v: "📈 52-week breakout"       if v else None),
        ("price_below_52w_low",      lambda v: "📉 52-week breakdown"       if v else None),
        ("price_above_sma",          lambda v: f"Price > SMA{v}"),
        ("price_below_sma",          lambda v: f"Price < SMA{v}"),
        ("day_change_pct_above",     lambda v: f"Day gain > {v:+.1f}%"),
        ("day_change_pct_below",     lambda v: f"Day drop < {v:+.1f}%"),
        ("price_above",              lambda v: f"Price > ${v:,.2f}"),
        ("price_below",              lambda v: f"Price < ${v:,.2f}"),
        ("volume_vs_avg_multiplier", lambda v: f"Volume > {v:.1f}x avg"),
        ("min_volume",               lambda v: f"Volume > {v/1e6:.1f}M"),
        ("rsi_above",                lambda v: f"RSI > {v:.0f}"),
        ("rsi_below",                lambda v: f"RSI < {v:.0f}"),
        ("composite_above",          lambda v: f"Composite > {v:.0f}"),
        ("composite_below",          lambda v: f"Composite < {v:.0f}"),
        ("momentum_above",           lambda v: f"Momentum > {v:.0f}"),
        ("risk_below",               lambda v: f"Risk < {v:.0f}"),
        ("quality_above",            lambda v: f"Quality > {v:.0f}"),
        ("rating_in",                lambda v: f"Rating: {'/'.join(v)}"),
        ("sector",                   lambda v: f"Sector: {v}"),
        ("near_support_pct",         lambda v: f"Within {v:.1f}% of support"),
        ("near_resistance_pct",      lambda v: f"Within {v:.1f}% of resistance"),
    ]

    badges = []
    for attr, fmt in badge_map:
        val = getattr(condition, attr, None)
        if val is not None and val is not False:
            try:
                label = fmt(val)
                if label:
                    badges.append(label)
            except Exception:
                pass

    if badges:
        st.markdown(
            " &nbsp;·&nbsp; ".join(f"<code>{b}</code>" for b in badges),
            unsafe_allow_html=True,
        )
        st.markdown("")


# ─────────────────────────────────────────────────────────────
# Tab 2 — My Rules
# ─────────────────────────────────────────────────────────────

def _render_rules_tab(db, tenant_id: str):
    st.subheader("Active scanner rules")

    rules = _load_rules(db, tenant_id)
    symbols = _load_symbols(db, tenant_id)

    if not rules:
        st.info(
            "No scanner rules yet. Go to **✍️ Create Rule** to write your first rule."
        )
        return

    st.caption(
        f"{len(rules)} rule(s) · {len(symbols)} symbols in universe"
    )

    # Run all active rules button
    if st.button(
        f"▶ Run All Active Rules ({len([r for r in rules if r.active])})",
        type="primary",
        key="scanner_run_all",
    ):
        if not symbols:
            st.warning("No symbols in universe. Run analytics first.")
        else:
            total_fired = 0
            for rule in rules:
                if not rule.active:
                    continue
                with st.spinner(f"Running '{rule.name}'…"):
                    fired = run_scanner_rule(db, rule, tenant_id, symbols)
                    total_fired += len(fired)
                    if fired:
                        for f in fired:
                            st.success(
                                f"🔔 **{f['symbol']}** — {f['title']} · {f['reason']}"
                            )
            if total_fired == 0:
                st.info("No alerts fired. All conditions checked.")
            else:
                st.success(f"Scan complete. {total_fired} alert(s) fired → check **Fired Alerts** tab.")

    st.markdown("---")

    # Rule cards
    for rule in rules:
        condition = ScanCondition.from_dict(json.loads(rule.condition))

        status_emoji = "🟢" if rule.active else "⚫"
        last_run_str = (
            rule.last_run.strftime("%b %d %H:%M") if rule.last_run else "Never"
        )
        last_fired_str = (
            rule.last_fired.strftime("%b %d %H:%M") if rule.last_fired else "Never"
        )

        with st.expander(
            f"{status_emoji} **{rule.name}** · Last run: {last_run_str} · Fired: {rule.fire_count}×",
            expanded=False,
        ):
            st.caption(f"Rule: {rule.description}")
            _render_condition_badges(condition)

            c1, c2, c3, c4, c5 = st.columns(5)

            # Run this rule now
            with c1:
                if st.button(
                    "▶ Run Now",
                    key=f"run_{rule.id}",
                    use_container_width=True,
                ):
                    if not symbols:
                        st.warning("No symbols in universe.")
                    else:
                        with st.spinner(f"Scanning {len(symbols)} symbols…"):
                            fired = run_scanner_rule(db, rule, tenant_id, symbols)
                        if fired:
                            for f in fired:
                                st.success(f"🔔 **{f['symbol']}** — {f['reason']}")
                        else:
                            st.info(f"No matches found in {len(symbols)} symbols.")
                        st.rerun()

            # Test on symbol
            with c2:
                test_sym = st.text_input(
                    "", placeholder="Test symbol",
                    key=f"test_sym_{rule.id}",
                    label_visibility="collapsed",
                )
            with c3:
                if st.button("🧪 Test", key=f"test_{rule.id}", use_container_width=True):
                    if test_sym:
                        try:
                            db.rollback()
                        except Exception:
                            pass
                        fired, reason = evaluate_condition(
                            test_sym.upper(), condition, db
                        )
                        if fired:
                            st.success(f"✅ WOULD FIRE — {reason}")
                        else:
                            st.info(f"❌ Would not fire — {reason}")

            # Toggle active
            with c4:
                toggle_label = "⏸ Pause" if rule.active else "▶ Enable"
                if st.button(toggle_label, key=f"toggle_{rule.id}", use_container_width=True):
                    _toggle_rule(db, rule.id, rule.id, not rule.active)
                    st.rerun()

            # Delete
            with c5:
                if st.button("🗑 Delete", key=f"del_{rule.id}", use_container_width=True):
                    _delete_rule(db, rule.id, tenant_id)
                    st.rerun()

            st.caption(
                f"Created: {rule.created_at.strftime('%b %d %Y') if rule.created_at else '—'} · "
                f"Last fired: {last_fired_str} · "
                f"Fire count: {rule.fire_count}"
            )


# ─────────────────────────────────────────────────────────────
# Tab 3 — Fired Alerts
# ─────────────────────────────────────────────────────────────

def _render_alerts_tab(db, tenant_id: str):
    st.subheader("Scanner alerts")

    try:
        from modules.alerts.models import AlertEvent
        alerts = (
            db.query(AlertEvent)
            .filter(
                AlertEvent.tenant_id == tenant_id,
                AlertEvent.alert_type == "SCANNER",
            )
            .order_by(AlertEvent.created_at.desc())
            .limit(100)
            .all()
        )
    except Exception as e:
        st.error(f"Could not load alerts: {e}")
        return

    col_filter, col_ack_all = st.columns([2, 1])
    with col_filter:
        only_unack = st.checkbox("Unacknowledged only", value=True, key="scanner_unack")
    with col_ack_all:
        if st.button("✅ Acknowledge All", key="scanner_ack_all"):
            try:
                for a in alerts:
                    if not a.acknowledged:
                        a.acknowledged = True
                        a.acknowledged_at = datetime.now(timezone.utc)
                db.commit()
                st.success("All acknowledged.")
                st.rerun()
            except Exception as e:
                db.rollback()
                st.error(f"Failed: {e}")

    if only_unack:
        alerts = [a for a in alerts if not a.acknowledged]

    if not alerts:
        st.info("No scanner alerts found.")
        return

    st.caption(f"{len(alerts)} alert(s)")

    rows = []
    for a in alerts:
        rows.append({
            "Time":    a.created_at.strftime("%b %d %H:%M") if a.created_at else "—",
            "Symbol":  a.symbol,
            "Alert":   a.title,
            "Detail":  a.message[:120] + "…" if len(a.message) > 120 else a.message,
            "Ack":     "✅" if a.acknowledged else "🔔",
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Acknowledge individual
    unack = [a for a in alerts if not a.acknowledged]
    if unack:
        st.markdown("#### Acknowledge")
        pick_id = st.selectbox(
            "Select alert to acknowledge",
            [a.id for a in unack],
            format_func=lambda i: next(
                f"{a.symbol} — {a.title}" for a in unack if a.id == i
            ),
            key="scanner_ack_pick",
        )
        if st.button("Acknowledge Selected", key="scanner_ack_btn"):
            try:
                target = next(a for a in unack if a.id == pick_id)
                target.acknowledged = True
                target.acknowledged_at = datetime.now(timezone.utc)
                db.commit()
                st.success("Acknowledged.")
                st.rerun()
            except Exception as e:
                db.rollback()
                st.error(f"Failed: {e}")