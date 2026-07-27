"""
modules/risk_layer/risk_ui.py

"Risk Layer" page -- the cross-asset Internal Risk Layer dashboard. Reads
positions across every connected broker (paper/Alpaca/Tradier/IBKR) for a
tenant, and surfaces exposure, concentration, VaR/ES, regime context,
AI Scanner flags, valuation flags, options context, a survival score, and
a defense directive -- all from modules.risk_layer.engine.compute_risk_snapshot.

Wire into app.py the same way other pages are:

    elif page == "Risk Layer":
        if not check_page(user, "Risk Layer", db):
            require_page(user, "Risk Layer", db)
            st.stop()
        try:
            from modules.risk_layer.risk_ui import render_risk_layer_page
            run_page("Risk Layer", render_risk_layer_page, db, user)
        except Exception as e:
            safe_rollback(db)
            st.error("Risk Layer failed to load.")
            st.exception(e)
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from models.trading import Portfolio
from modules.risk_layer.engine import compute_risk_snapshot
from modules.risk_layer.limits import get_limits, set_limit, reset_limit, DEFAULT_LIMITS, LIMIT_DESCRIPTIONS

ASSET_CLASS_LABELS = {
    "equity": "Equities", "option": "Options", "crypto": "Crypto",
    "forex": "Forex", "real_world_asset": "Real-World Assets",
}


def render_risk_layer_page(db, user):
    st.header("🛡️ Internal Risk Layer")
    st.caption(
        "Cross-asset risk across every connected broker — equities, options, crypto, and forex "
        "today, with real-world assets ready to slot in. Pulls live from Portfolio, the Regime "
        "Engine, the AI Scanner, and Valuation rather than keeping a separate copy of the truth. "
        "Optional external risk vendors (Admin > Risk Providers) add a cross-check on top."
    )

    tenant_id = user.get("tenant_id")

    portfolios = (
        db.query(Portfolio)
        .filter(Portfolio.tenant_id == tenant_id, Portfolio.is_active == True)  # noqa: E712
        .order_by(Portfolio.created_at.asc())
        .all()
    )
    if not portfolios:
        st.info("No active portfolios yet — create one under Portfolio to start tracking risk.")
        return

    scope_options = {"All portfolios (aggregate)": None}
    scope_options.update({p.name: p.id for p in portfolios})

    c1, c2 = st.columns([2, 1])
    with c1:
        scope_label = st.selectbox("Scope", list(scope_options.keys()), key="risk_layer_scope")
    with c2:
        refresh = st.button("↺ Recompute", key="risk_layer_refresh", use_container_width=True)

    if scope_options[scope_label] is not None:
        st.caption(
            "Forex positions aren't tied to a specific portfolio here, so they only appear "
            "under **All portfolios (aggregate)**."
        )

    cache_key = f"risk_snapshot_{tenant_id}_{scope_options[scope_label]}"
    if refresh or cache_key not in st.session_state:
        with st.spinner("Computing risk snapshot across positions, regime, scanner, and valuation…"):
            try:
                st.session_state[cache_key] = compute_risk_snapshot(
                    db, tenant_id=tenant_id, portfolio_id=scope_options[scope_label],
                )
            except Exception as e:
                st.error(f"Could not compute risk snapshot: {e}")
                return

    snap = st.session_state[cache_key]

    tabs = st.tabs(["Overview", "Exposure & Concentration", "Positions Risk Flags",
                    "Options", "External Risk Providers", "Defense Directive", "Risk Limits"])

    with tabs[0]:
        _render_overview(snap)
    with tabs[1]:
        _render_exposure(snap)
    with tabs[2]:
        _render_position_flags(snap)
    with tabs[3]:
        _render_options(snap)
    with tabs[4]:
        _render_external_providers(snap)
    with tabs[5]:
        _render_defense(snap)
    with tabs[6]:
        _render_limits_tab(db, user, tenant_id)


def _render_overview(snap: dict) -> None:
    dq_warnings = snap.get("data_quality_warnings", [])
    if dq_warnings:
        st.error(f"🚩 {len(dq_warnings)} data quality warning(s) -- numbers below may be unreliable:")
        for w in dq_warnings:
            st.write(f"- {w}")
        st.divider()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Equity", f"${snap['equity']:,.0f}")
    m2.metric("Gross Exposure", f"${snap['gross_exposure']:,.0f}",
               f"{(snap['gross_exposure'] / snap['equity'] * 100):.0f}% of equity" if snap['equity'] else None)
    m3.metric("1-Day VaR (95%)", f"${snap['var_95_1d']:,.0f}")
    m4.metric("Survival Score", f"{snap['survival_score']:.0f}/100")

    regime = snap["market_regime"]
    reg_color = {"Risk-On": "🟢", "Risk-Off": "🔴", "Transition": "🟡"}.get(regime["label"], "⚪")
    st.markdown(
        f"**Market Regime:** {reg_color} {regime['label']} "
        f"(trend: {regime['trend']}, risk-on breadth: {regime['risk_on_breadth']}, "
        f"defensive breadth: {regime['defensive_breadth']})"
    )
    st.caption(
        f"Regime-adjusted exposure multiplier: {snap['regime_risk_multiplier']:.2f}x — "
        "tightens limits automatically in Risk-Off conditions."
    )

    dd = snap["drawdown"]
    vr = snap["volatility_regime"]
    d1, d2, d3 = st.columns(3)
    d1.metric("Current Drawdown", f"{dd.get('current_drawdown', 0.0):.1%}",
               "⚠️ Halt level breached" if dd.get("triggered") else None)
    d2.metric("Annualized Volatility", f"{vr.get('annualized_vol', 0.0):.1%}", vr.get("regime", "Unknown"))
    d3.metric("Expected Shortfall (95%)", f"${snap['expected_shortfall_95']:,.0f}")

    breaches = snap["breaches"]
    if breaches:
        st.error(f"⚠️ {len(breaches)} risk limit breach(es):")
        for b in breaches:
            st.write(f"- **{b['limit']}** — {b['message']}")
    else:
        st.success("✅ No risk limit breaches.")

    _render_advanced_risk_cross_check(snap)


def _render_advanced_risk_cross_check(snap: dict) -> None:
    adv = snap.get("advanced_risk", {})
    garch = adv.get("garch", {})
    rf = adv.get("riskfolio", {})
    if not garch.get("available") and not rf.get("available"):
        return  # nothing to show -- packages not installed or too little history

    with st.expander("🧪 Advanced risk model cross-check (GARCH + Riskfolio-Lib)", expanded=False):
        st.caption(
            "Open-source cross-checks on the numbers above — GARCH(1,1) volatility forecasting "
            "(arch) and Entropic/Conditional VaR (Riskfolio-Lib). Supplemental, not authoritative."
        )
        c1, c2, c3 = st.columns(3)
        if garch.get("available"):
            c1.metric("GARCH(1,1) Annualized Vol", f"{garch['annualized_vol']:.1%}",
                       f"vs. {snap['volatility_regime'].get('annualized_vol', 0):.1%} realized")
        else:
            c1.caption(f"GARCH unavailable: {garch.get('reason', 'n/a')}")

        if rf.get("available"):
            c2.metric("Riskfolio CVaR (95%)", f"${rf.get('cvar_dollar', rf['cvar']):,.0f}"
                       if "cvar_dollar" in rf else f"{rf['cvar']:.2%}",
                       f"vs. our ${snap['expected_shortfall_95']:,.0f}")
            c3.metric("Riskfolio EVaR (95%)", f"${rf.get('evar_dollar', rf['evar']):,.0f}"
                       if "evar_dollar" in rf else f"{rf['evar']:.2%}",
                       help="Entropic VaR — a more conservative, tail-thickness-aware risk measure "
                            "not present in our own simple historical VaR/ES calculation.")
        else:
            c2.caption(f"Riskfolio-Lib unavailable: {rf.get('reason', 'n/a')}")


def _render_exposure(snap: dict) -> None:
    st.subheader("Exposure by Asset Class")
    by_class = snap["exposure_by_asset_class"]
    if by_class:
        df = pd.DataFrame([
            {"Asset Class": ASSET_CLASS_LABELS.get(k, k.title()), "Exposure ($)": v,
             "% of Gross": (v / snap["gross_exposure"] * 100) if snap["gross_exposure"] else 0}
            for k, v in by_class.items()
        ]).sort_values("Exposure ($)", ascending=False)
        st.dataframe(df.style.format({"Exposure ($)": "${:,.0f}", "% of Gross": "{:.1f}%"}),
                     use_container_width=True, hide_index=True)
    else:
        st.info("No open positions in scope.")

    st.subheader("Concentration")
    conc = snap["concentration"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Max Single-Name Weight", f"{conc.get('max_weight', 0):.1%}")
    c2.metric("HHI Index", f"{conc.get('hh_index', 0):.3f}")
    c3.metric("Effective # of Names", f"{conc.get('effective_n', 0):.1f}")

    st.subheader("Positions")
    positions = snap["positions"]
    if positions is not None and not positions.empty:
        show = positions.copy()
        show["Asset Class"] = show["Asset Class"].map(lambda k: ASSET_CLASS_LABELS.get(k, k.title()))
        cols = ["Symbol", "Asset Class", "Quantity", "Market Price", "Market Value", "Weight",
                "Unrealized P&L", "Leverage", "Margin Required"]
        cols = [c for c in cols if c in show.columns]
        fmt = {
            "Market Price": "${:,.2f}", "Market Value": "${:,.0f}",
            "Weight": "{:.1%}", "Unrealized P&L": "${:,.0f}",
            "Leverage": "{:.0f}x", "Margin Required": "${:,.0f}",
        }
        st.dataframe(
            show[cols].style.format({k: v for k, v in fmt.items() if k in cols}, na_rep=""),
            use_container_width=True, hide_index=True,
        )
        if "Margin Required" in show.columns and show["Margin Required"].sum() > 0:
            st.caption(
                f"💱 Includes ${show['Margin Required'].sum():,.0f} in FX margin required "
                f"across leveraged forex positions — margin usage is a liquidity risk, not "
                f"reflected in Market Value or gross exposure above."
            )
    else:
        st.info("No open positions in scope.")

    if positions is not None and not positions.empty and "real_world_asset" in positions.get("Asset Class", pd.Series()).values:
        with st.expander("🔗 Verify a tokenized position on-chain"):
            st.caption(
                "Cross-checks a custodian-reported tokenized asset quantity against the real "
                "token balance on-chain, rather than trusting the custodian API's report alone."
            )
            vc1, vc2 = st.columns(2)
            with vc1:
                contract_addr = st.text_input("Token contract address", key="rwa_verify_contract")
                wallet_addr = st.text_input("Wallet/custody address", key="rwa_verify_wallet")
            with vc2:
                chain = st.selectbox("Chain", ["ethereum", "polygon", "arbitrum", "optimism",
                                                 "avalanche", "bnb chain", "base"], key="rwa_verify_chain")
                expected_qty = st.number_input("Expected quantity (from custodian)", min_value=0.0,
                                                 step=0.01, key="rwa_verify_qty")
            if st.button("Verify on-chain", key="rwa_verify_btn"):
                from modules.tokenized_assets.onchain_verification import verify_position_onchain
                with st.spinner("Reading on-chain balance…"):
                    result = verify_position_onchain(contract_addr, wallet_addr, expected_qty, chain=chain)
                if not result.get("available"):
                    st.error(result.get("reason", "Verification unavailable."))
                elif result["verified"]:
                    st.success(f"✅ On-chain balance ({result['onchain_qty']:.4f}) matches within "
                               f"{result['tolerance_pct']}% tolerance.")
                else:
                    st.error(f"❌ {result['note']}")

    st.subheader("Stress Test")
    stress = snap["stress_test"]
    if stress is not None and not stress.empty:
        st.dataframe(stress.style.format({"Shock": "{:.0%}", "Estimated P&L Impact": "${:,.0f}"}),
                     use_container_width=True, hide_index=True)


def _render_position_flags(snap: dict) -> None:
    st.subheader("AI Scanner Risk Flags")
    st.caption("Runs the AI Scanner's own condition evaluator against every held symbol.")
    scanner_flags = snap["scanner_flags"]
    if scanner_flags:
        for symbol, flags in scanner_flags.items():
            with st.expander(f"⚠️ {symbol} — {len(flags)} flag(s)"):
                for f in flags:
                    st.write(f"- **{f['preset']}**: {f['reason']}")
    else:
        st.success("No scanner risk flags fired on current positions.")

    st.subheader("Valuation Flags (Equities)")
    st.caption("Flags positions trading at rich multiples per modules.valuation.compute_valuation.")
    val_flags = snap["valuation_flags"]
    flagged = {s: v for s, v in val_flags.items() if v.get("flag")}
    if flagged:
        df = pd.DataFrame([
            {"Symbol": s, "P/E (TTM)": v.get("pe_ttm"), "P/S (TTM)": v.get("ps_ttm"), "Flag": v["flag"]}
            for s, v in flagged.items()
        ])
        st.dataframe(df, use_container_width=True, hide_index=True)
    elif val_flags:
        st.success("No equity positions flagged as richly valued.")
    else:
        st.info("No fundamentals snapshot available for held equities yet.")


def _render_options(snap: dict) -> None:
    opts = snap["options"]
    if not opts.get("available"):
        st.info(opts.get("reason", "Options context unavailable."))
        return

    if opts.get("position_count", 0) == 0:
        st.info("No open options positions.")
        return

    c1, c2 = st.columns(2)
    c1.metric("Options Positions", opts["position_count"])
    c2.metric("Total Options Notional", f"${opts['total_notional']:,.0f}")

    if not opts.get("greeks_available", False):
        st.warning(opts.get("greeks_note", "Greeks unavailable."))
    else:
        st.subheader("Net Greeks (QuantLib, IV backed out from each position's own mark price)")
        g = opts["greeks"]
        gc1, gc2, gc3, gc4 = st.columns(4)
        gc1.metric("Net Delta", f"{g['net_delta']:.1f}" if g["net_delta"] is not None else "n/a",
                    help="Dollar-equivalent underlying shares of directional exposure.")
        gc2.metric("Net Gamma", f"{g['net_gamma']:.2f}" if g["net_gamma"] is not None else "n/a")
        gc3.metric("Net Theta/day", f"${g['net_theta_per_day']:,.0f}" if g["net_theta_per_day"] is not None else "n/a",
                    help="American-exercise positions don't get a theta estimate in this build -- "
                         "see positions_contributing for how many positions this includes.")
        gc4.metric("Net Vega", f"${g['net_vega']:,.0f}" if g["net_vega"] is not None else "n/a")
        contributing = g["positions_contributing"]
        st.caption(
            f"Delta from {contributing['delta']}/{opts['position_count']} positions, "
            f"gamma from {contributing['gamma']}, theta from {contributing['theta']}, "
            f"vega from {contributing['vega']}."
        )
        if opts.get("greeks_note"):
            st.caption(f"⚠️ {opts['greeks_note']}")
        with st.expander("Greeks by position"):
            rows = []
            for symbol, pg in g["by_position"].items():
                rows.append({
                    "Symbol": symbol, "IV": pg["implied_vol"],
                    "Delta": pg["delta"], "Gamma": pg["gamma"],
                    "Theta": pg["theta"], "Vega": pg["vega"],
                })
            if rows:
                st.dataframe(pd.DataFrame(rows).style.format({
                    "IV": "{:.1%}", "Delta": "{:.3f}", "Gamma": "{:.4f}",
                    "Theta": "{:.3f}", "Vega": "{:.3f}",
                }, na_rep="—"), use_container_width=True, hide_index=True)

    st.subheader("Concentration by Underlying")
    by_u = opts.get("by_underlying_weight", {})
    if by_u:
        df = pd.DataFrame([{"Underlying": u, "Weight": w} for u, w in by_u.items()])
        st.dataframe(df.style.format({"Weight": "{:.1%}"}), use_container_width=True, hide_index=True)

    near_term = opts.get("near_term_expiry", [])
    if near_term:
        st.subheader(f"Near-Term Expiry Risk (≤ {opts['near_term_dte_threshold']} DTE)")
        st.dataframe(pd.DataFrame(near_term), use_container_width=True, hide_index=True)


def _render_external_providers(snap: dict) -> None:
    st.caption(
        "Cross-checks from external risk vendors, shown alongside the Internal Risk Layer's "
        "own VaR/ES above -- these are supplemental, not authoritative. Enable vendors and "
        "add credentials under Admin > Risk Providers and Admin > API Keys."
    )
    providers = snap.get("external_risk_providers", {})
    if not providers:
        st.info("No external risk providers enabled for this tenant yet.")
        return

    from modules.risk_providers.registry import RISK_PROVIDER_INFO
    for name, result in providers.items():
        label = RISK_PROVIDER_INFO.get(name, (name.title(),))[0]
        if not result.get("available"):
            st.warning(f"**{label}**: {result.get('error', 'unavailable')}")
            continue

        st.markdown(f"**{label}**")
        c1, c2 = st.columns(2)
        our_var = snap.get("var_95_1d")
        vendor_var = result.get("var")
        c1.metric(f"{label} VaR (95%)", f"${vendor_var:,.0f}" if vendor_var is not None else "n/a",
                   f"vs. our ${our_var:,.0f}" if our_var is not None and vendor_var is not None else None)
        vendor_es = result.get("expected_shortfall")
        c2.metric(f"{label} Expected Shortfall", f"${vendor_es:,.0f}" if vendor_es is not None else "n/a")

        if result.get("factor_exposures"):
            with st.expander(f"{label} factor exposures"):
                st.json(result["factor_exposures"])
        if result.get("stress_scenarios"):
            with st.expander(f"{label} stress scenarios"):
                st.json(result["stress_scenarios"])
        st.divider()


def _render_defense(snap: dict) -> None:
    d = snap["defense_directive"]
    severity_color = {"low": "🟢", "moderate": "🟡", "high": "🟠", "critical": "🔴"}.get(
        str(d.get("severity", "")).lower(), "⚪"
    )
    st.markdown(f"### {severity_color} {d.get('directive_type', 'Directive')} — severity: {d.get('severity', 'unknown')}")
    st.write(d.get("rationale", ""))

    c1, c2, c3 = st.columns(3)
    c1.metric("Recommended Cash", f"{d.get('recommended_cash', 0):.1f}%")
    c2.metric("Suggested Hedge Level", f"{d.get('hedge_level', 0):.1f}%")
    c3.metric("Suggested Exposure Reduction", f"{d.get('reduce_exposure', 0):.1f}%")

    if d.get("actions"):
        st.subheader("Suggested Actions")
        for a in d["actions"]:
            st.write(f"- {a}")
    if d.get("target_sectors"):
        st.write(f"**Favor:** {', '.join(d['target_sectors'])}")
    if d.get("avoid_sectors"):
        st.write(f"**Avoid:** {', '.join(d['avoid_sectors'])}")
    if d.get("warnings"):
        for w in d["warnings"]:
            st.warning(w)

    st.caption(
        "Generated by modules.risk.autonomous_defense_engine — directional guidance based on "
        "the current risk snapshot, not an automated trading action."
    )


def _render_limits_tab(db, user, tenant_id: str) -> None:
    role = user.get("role")
    st.caption(
        "Configure this tenant's risk limits. Exposure-style limits are automatically "
        "tightened further in Risk-Off regimes — see the multiplier on the Overview tab."
    )
    if role not in ("tenant_admin", "super_admin"):
        st.info("Only tenant admins and super admins can edit risk limits.")
        current = get_limits(db, tenant_id)
        st.json(current)
        return

    current = get_limits(db, tenant_id)
    for name, default in DEFAULT_LIMITS.items():
        c1, c2, c3 = st.columns([3, 1.2, 0.8])
        with c1:
            st.write(f"**{LIMIT_DESCRIPTIONS.get(name, name)}**")
            st.caption(f"Default: {default}")
        with c2:
            new_value = st.number_input(
                name, value=float(current[name]), key=f"risk_limit_{tenant_id}_{name}",
                label_visibility="collapsed", format="%.4f",
            )
        with c3:
            if st.button("Reset", key=f"risk_limit_reset_{tenant_id}_{name}"):
                reset_limit(db, tenant_id, name)
                st.rerun()
        if new_value != current[name]:
            set_limit(db, tenant_id, name, new_value, user_id=user.get("user_id"))
            st.success(f"Updated {name} to {new_value}.")
            st.rerun()
        st.divider()
