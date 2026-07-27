"""
modules/screener/formula_ui.py

Custom Formula Builder UI — full Streamlit page.

Sections:
  1. Formula Builder    — write/edit formula with live validation + preview
  2. Formula Library    — built-in formulas + user's saved formulas
  3. Formula Screener   — run screener with custom formula columns + filters
  4. Formula Comparison — rank stocks by multiple formulas side-by-side

Add to app.py:
    elif page == "Formula Builder":
        from modules.screener.formula_ui import render_formula_page
        render_formula_page(db, user)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

try:
    import plotly.graph_objects as go
    PLOTLY = True
except ImportError:
    PLOTLY = False

from modules.screener.formula_engine import (
    AVAILABLE_FIELDS, BUILTIN_FORMULAS, Formula,
    apply_formulas_to_results, evaluate_formula,
    filter_by_formula, validate_formula,
    save_formula_session, load_formulas_session,
    delete_formula_session, save_formula_db, load_formulas_db,
)

GREEN = "#1D9E75"
RED   = "#E24B4A"
BLUE  = "#2E75B6"
NAVY  = "#1F3864"


# ─────────────────────────────────────────────────────────────
# Main page
# ─────────────────────────────────────────────────────────────

def render_formula_page(db, user: dict):
    tenant_id = (user or {}).get("tenant_id", "default_tenant")
    user_id   = (user or {}).get("user_id", "")

    st.header("🧮 Custom Formula Builder")
    st.caption(
        "Define your own screening metrics with math expressions · "
        "Screen and rank stocks on your formulas · "
        "Build factor blends, valuation composites, and technical-fundamental signals"
    )

    tabs = st.tabs([
        "📝 Formula Builder",
        "📚 Formula Library",
        "🔍 Formula Screener",
        "📊 Comparison Chart",
    ])

    with tabs[0]: _render_builder(db, tenant_id, user_id)
    with tabs[1]: _render_library(db, tenant_id, user_id)
    with tabs[2]: _render_screener(db, tenant_id, user_id)
    with tabs[3]: _render_comparison(db, tenant_id, user_id)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — FORMULA BUILDER
# ══════════════════════════════════════════════════════════════════════════════

def _render_builder(db, tenant_id: str, user_id: str):
    st.subheader("📝 Formula Builder")
    st.caption(
        "Write any math expression using the available fields. "
        "The engine safely evaluates your formula — no code execution."
    )

    col_main, col_ref = st.columns([3, 2])

    with col_main:
        # Formula name
        f_name = st.text_input(
            "Formula Name",
            value=st.session_state.get("fb_name", "My Formula"),
            placeholder="FCF Yield, GARP Score, Momentum Blend…",
            key="fb_name",
        )

        # Expression input with syntax highlighting hint
        st.markdown("**Expression**")
        st.caption(
            "Use field names + math operators (+, -, *, /, **, %) and "
            "functions: abs(), sqrt(), log(), min(), max(), round()"
        )

        # Quick-insert buttons for common patterns
        with st.expander("⚡ Quick-insert fields", expanded=False):
            cols = st.columns(4)
            fields_list = list(AVAILABLE_FIELDS.keys())
            for i, fname in enumerate(fields_list):
                with cols[i % 4]:
                    if st.button(fname, key=f"qi_{fname}", use_container_width=True,
                                  help=AVAILABLE_FIELDS[fname]):
                        current = st.session_state.get("fb_expr", "")
                        st.session_state["fb_expr"] = current + (
                            " " if current and not current.endswith(" ") else ""
                        ) + fname
                        st.rerun()

        expression = st.text_area(
            "Expression",
            value=st.session_state.get("fb_expr", ""),
            height=80,
            key="fb_expr",
            placeholder="e.g.  fcf_margin / pe_ttm * 100",
            label_visibility="collapsed",
        )

        # Live validation
        if expression and expression.strip():
            valid, msg = validate_formula(expression)
            if valid:
                st.success(msg)
            else:
                st.error(f"❌ {msg}")

        # Description and settings
        col_desc, col_hib = st.columns([3, 1])
        with col_desc:
            description = st.text_input(
                "Description (optional)",
                value=st.session_state.get("fb_desc", ""),
                key="fb_desc",
                placeholder="What does this formula measure?",
            )
        with col_hib:
            higher_is_better = st.checkbox(
                "↑ Higher = Better",
                value=True,
                key="fb_hib",
                help="Sort ascending or descending in screener results",
            )

        category = st.selectbox(
            "Category",
            ["Valuation", "Profitability", "Factor Blend", "Technical",
             "Technical-Fundamental", "Risk-Adjusted", "Custom"],
            key="fb_category",
        )

        col_share, col_save = st.columns([1, 2])
        with col_share:
            is_shared = st.checkbox("Share with team", key="fb_shared")
        with col_save:
            save_btn = st.button(
                "💾 Save Formula",
                type="primary",
                key="fb_save",
                use_container_width=True,
                disabled=not bool(f_name and expression),
            )

        if save_btn and f_name and expression:
            valid, msg = validate_formula(expression)
            if not valid:
                st.error(f"Cannot save — {msg}")
            else:
                formula = Formula(
                    id=str(uuid.uuid4()),
                    name=f_name.strip(),
                    expression=expression.strip(),
                    description=description.strip(),
                    higher_is_better=higher_is_better,
                    category=category,
                    created_at=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    is_shared=is_shared,
                )
                save_formula_session(formula)
                try:
                    save_formula_db(db, formula, tenant_id, user_id)
                except Exception:
                    pass
                st.success(f"✅ '{f_name}' saved!")
                st.rerun()

    with col_ref:
        st.markdown("#### 📖 Field Reference")
        for fname, fdesc in AVAILABLE_FIELDS.items():
            st.markdown(
                f"**`{fname}`** — {fdesc}",
                help=fdesc,
            )

        st.markdown("#### 💡 Formula Examples")
        examples = [
            ("FCF Yield",         "fcf_margin / pe_ttm * 100",
             "Cash flow per dollar paid"),
            ("Earnings Yield",    "100 / pe_ttm",
             "Inverse P/E — compare to bonds"),
            ("PEG",               "pe_ttm / revenue_cagr",
             "< 1 = cheap growth"),
            ("GARP",              "(growth * 0.4) + (value * 0.3) + (quality * 0.3)",
             "Growth at reasonable price"),
            ("Risk-adj Composite","composite * (1 - risk / 100)",
             "Quality penalized by risk"),
            ("Margin Quality",    "(gross_margin + operating_margin + fcf_margin) / 3",
             "Average of all margins"),
            ("Oversold Value",    "value * (1 - rsi_14 / 100)",
             "Value + oversold signal"),
            ("Upside Momentum",   "upside_to_resistance * momentum / 100",
             "Room to run with momentum"),
        ]

        for name, expr, hint in examples:
            with st.expander(f"**{name}**", expanded=False):
                st.code(expr)
                st.caption(hint)
                if st.button(f"Use this formula", key=f"use_{name}"):
                    st.session_state["fb_name"] = name
                    st.session_state["fb_expr"] = expr
                    st.session_state["fb_desc"] = hint
                    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — FORMULA LIBRARY
# ══════════════════════════════════════════════════════════════════════════════

def _render_library(db, tenant_id: str, user_id: str):
    st.subheader("📚 Formula Library")

    tab_builtin, tab_custom = st.tabs(["🏛️ Built-In Formulas", "👤 My Formulas"])

    with tab_builtin:
        st.caption(
            f"{len(BUILTIN_FORMULAS)} professional formulas ready to use. "
            "Click any formula to add it to your screener."
        )

        # Group by category
        categories = sorted(set(f.category for f in BUILTIN_FORMULAS))
        for cat in categories:
            cat_formulas = [f for f in BUILTIN_FORMULAS if f.category == cat]
            st.markdown(f"#### {cat}")
            for formula in cat_formulas:
                with st.container():
                    col_info, col_actions = st.columns([5, 2])
                    with col_info:
                        st.markdown(
                            f"**{formula.name}** "
                            f"({'↑ Higher better' if formula.higher_is_better else '↓ Lower better'})"
                        )
                        st.code(formula.expression, language="python")
                        st.caption(formula.description)
                    with col_actions:
                        st.write("")
                        if st.button("+ Add to My Formulas",
                                     key=f"add_builtin_{formula.id}",
                                     use_container_width=True):
                            new_f = Formula(
                                id=str(uuid.uuid4()),
                                name=formula.name,
                                expression=formula.expression,
                                description=formula.description,
                                higher_is_better=formula.higher_is_better,
                                category=formula.category,
                                created_at=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                            )
                            save_formula_session(new_f)
                            st.success(f"Added '{formula.name}'")
                            st.rerun()
                        if st.button("Edit",
                                     key=f"edit_builtin_{formula.id}",
                                     use_container_width=True):
                            st.session_state["fb_name"] = formula.name
                            st.session_state["fb_expr"] = formula.expression
                            st.session_state["fb_desc"] = formula.description
                            st.session_state["fb_hib"]  = formula.higher_is_better
                            st.success(f"Loaded '{formula.name}' into builder")
                st.markdown("---")

    with tab_custom:
        # Load from session + DB
        session_formulas = load_formulas_session()
        try:
            db_formulas = load_formulas_db(db, tenant_id, user_id)
        except Exception:
            db_formulas = []

        # Merge, dedup by expression
        all_custom = {f.id: f for f in session_formulas}
        for f in db_formulas:
            if f.id not in all_custom:
                all_custom[f.id] = f

        if not all_custom:
            st.info(
                "No custom formulas saved yet. "
                "Build one in the **Formula Builder** tab or add from the Built-In library."
            )
            return

        st.caption(f"{len(all_custom)} custom formula(s)")

        for fid, formula in all_custom.items():
            with st.container():
                col_i, col_a = st.columns([5, 2])
                with col_i:
                    shared_badge = " 🔗 Shared" if formula.is_shared else ""
                    st.markdown(
                        f"**{formula.name}**{shared_badge} — *{formula.category}* "
                        f"· {formula.created_at}"
                    )
                    st.code(formula.expression, language="python")
                    if formula.description:
                        st.caption(formula.description)
                with col_a:
                    st.write("")
                    if st.button("✏️ Edit", key=f"edit_c_{fid}",
                                  use_container_width=True):
                        st.session_state["fb_name"] = formula.name
                        st.session_state["fb_expr"] = formula.expression
                        st.session_state["fb_desc"] = formula.description
                        st.session_state["fb_hib"]  = formula.higher_is_better
                        st.info("Formula loaded into builder")
                    if st.button("🗑 Delete", key=f"del_c_{fid}",
                                  use_container_width=True):
                        delete_formula_session(fid)
                        st.rerun()
            st.markdown("---")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — FORMULA SCREENER
# ══════════════════════════════════════════════════════════════════════════════

def _render_screener(db, tenant_id: str, user_id: str):
    st.subheader("🔍 Formula Screener")
    st.caption(
        "Run the screener with your custom formula columns. "
        "Filter and sort results by any formula value."
    )

    # Collect all available formulas
    session_formulas = load_formulas_session()
    all_formulas = {f.id: f for f in BUILTIN_FORMULAS}
    all_formulas.update({f.id: f for f in session_formulas})
    formula_list = list(all_formulas.values())

    if not formula_list:
        st.info("No formulas available. Add some from the Library tab first.")
        return

    col_sel, col_run = st.columns([3, 1])
    with col_sel:
        selected_ids = st.multiselect(
            "Formulas to include",
            options=[f.id for f in formula_list],
            default=[f.id for f in formula_list[:3]],
            format_func=lambda fid: all_formulas[fid].name,
            key="fs_formulas",
        )

    # Standard screener filters
    with st.expander("📐 Standard Filters", expanded=False):
        sc1, sc2, sc3, sc4 = st.columns(4)
        with sc1:
            min_composite = st.slider("Min Composite", 0, 100, 0, key="fs_composite")
            sector_opts   = ["All"] + _get_sectors(db, tenant_id)
            sector        = st.selectbox("Sector", sector_opts, key="fs_sector")
        with sc2:
            min_quality  = st.slider("Min Quality", 0, 100, 0, key="fs_quality")
            rating_opts  = ["Any", "Buy", "Hold", "Sell"]
            rating       = st.selectbox("Rating", rating_opts, key="fs_rating")
        with sc3:
            min_momentum = st.slider("Min Momentum", 0, 100, 0, key="fs_momentum")
            max_risk     = st.slider("Max Risk", 0, 100, 100, key="fs_risk")
        with sc4:
            min_price  = st.number_input("Min Price", 0.0, step=1.0, key="fs_price")
            min_volume = st.number_input("Min Volume (M)", 0.0, step=0.1, key="fs_vol",
                                          format="%.1f")

    # Formula-specific filters
    selected_formulas = [all_formulas[fid] for fid in selected_ids if fid in all_formulas]

    formula_filters = {}
    if selected_formulas:
        with st.expander("🧮 Formula Filters", expanded=True):
            cols = st.columns(min(len(selected_formulas), 3))
            for i, formula in enumerate(selected_formulas):
                with cols[i % 3]:
                    st.markdown(f"**{formula.name}**")
                    col_mn, col_mx = st.columns(2)
                    with col_mn:
                        mn = st.number_input(
                            "Min",
                            value=None, step=0.1, format="%.2f",
                            key=f"ff_min_{formula.id}",
                            placeholder="—",
                        )
                    with col_mx:
                        mx = st.number_input(
                            "Max",
                            value=None, step=0.1, format="%.2f",
                            key=f"ff_max_{formula.id}",
                            placeholder="—",
                        )
                    formula_filters[formula.id] = (mn, mx)

    # Sort by
    sort_options = ["Composite"] + [f.name for f in selected_formulas]
    col_sort, col_lim, col_run_btn = st.columns([2, 1, 1])
    with col_sort:
        sort_by = st.selectbox("Sort by", sort_options, key="fs_sort")
    with col_lim:
        limit = st.selectbox("Max results", [25, 50, 100, 250], index=1, key="fs_limit")
    with col_run_btn:
        st.write("")
        run_btn = st.button("▶ Run Screener", type="primary",
                             key="fs_run", use_container_width=True)

    if run_btn:
        with st.spinner("Running screener with custom formulas…"):
            # Run base screener
            from modules.screener.service import run_screener
            symbols = _get_symbols(db, tenant_id)

            results = run_screener(
                db=db,
                tenant_id=tenant_id,
                symbols=symbols,
                min_composite=min_composite if min_composite > 0 else None,
                min_quality=min_quality     if min_quality > 0 else None,
                min_momentum=min_momentum   if min_momentum > 0 else None,
                max_risk=max_risk           if max_risk < 100 else None,
                min_price=min_price         if min_price > 0 else None,
                min_volume=min_volume * 1e6 if min_volume > 0 else None,
                sector=sector if sector != "All" else None,
                rating_in=[rating] if rating != "Any" else None,
            )

            # Apply formulas
            df = apply_formulas_to_results(results, selected_formulas)

            # Apply formula filters
            for formula in selected_formulas:
                mn, mx = formula_filters.get(formula.id, (None, None))
                if mn is not None or mx is not None:
                    df = filter_by_formula(df, formula.name, mn, mx)

            # Sort
            sort_col = sort_by
            if sort_col == "Composite":
                sort_col = "composite"
            if sort_col in df.columns:
                sort_formula = next(
                    (f for f in selected_formulas if f.name == sort_col), None
                )
                asc = not (sort_formula.higher_is_better if sort_formula else True)
                df = df.sort_values(sort_col, ascending=asc, na_position="last")

            st.session_state["fs_results"] = df.head(limit)
            st.session_state["fs_formulas_used"] = selected_formulas

    # Display results
    df = st.session_state.get("fs_results")
    formulas_used = st.session_state.get("fs_formulas_used", [])

    if df is None:
        st.info("Set your filters and click **Run Screener** to see results.")
        return

    if df.empty:
        st.warning("No stocks matched the filters.")
        return

    st.success(f"**{len(df)} stocks** matched")

    # Format and display
    display_cols = (
        ["symbol", "sector", "rating", "composite", "quality", "growth",
         "value", "momentum", "pe_ttm", "ps_ttm", "rsi_14"]
        + [f.name for f in formulas_used]
    )
    display_cols = [c for c in display_cols if c in df.columns]
    show_df = df[display_cols].copy()

    # Rename for display
    show_df.columns = [c.replace("_", " ").title() for c in show_df.columns]

    formula_display_cols = [f.name for f in formulas_used]

    def _score_color(val):
        try:
            v = float(val)
            return f"color: {GREEN}; font-weight: bold" if v >= 70 \
                   else f"color: {RED}; font-weight: bold" if v <= 30 \
                   else ""
        except Exception:
            return ""

    styled = show_df.style
    score_cols = ["Composite", "Quality", "Growth", "Value", "Momentum"]
    score_cols_present = [c for c in score_cols if c in show_df.columns]
    if score_cols_present:
        styled = styled.applymap(_score_color, subset=score_cols_present)

    fmt = {}
    for c in show_df.columns:
        if c in ("Pe Ttm", "Ps Ttm", "Ev Ebitda"):
            fmt[c] = "{:.1f}x"
        elif c == "Rsi 14":
            fmt[c] = "{:.1f}"
        elif c in ("Price",):
            fmt[c] = "${:.2f}"

    if fmt:
        styled = styled.format(fmt, na_rep="—")

    st.dataframe(styled, use_container_width=True, hide_index=True, height=450)

    # Download
    csv = df[display_cols].to_csv(index=False)
    st.download_button(
        "⬇️ Download CSV",
        data=csv,
        file_name=f"formula_screener_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
        key="fs_dl",
    )

    # Formula stats
    if formulas_used:
        st.markdown("#### Formula Statistics")
        stat_cols = st.columns(len(formulas_used))
        for i, formula in enumerate(formulas_used):
            if formula.name in df.columns:
                col_data = df[formula.name].dropna()
                if not col_data.empty:
                    with stat_cols[i]:
                        st.markdown(f"**{formula.name}**")
                        st.metric("Median", f"{col_data.median():.3f}")
                        st.metric("Top 10%", f"{col_data.quantile(0.9):.3f}")
                        st.metric("Bottom 10%", f"{col_data.quantile(0.1):.3f}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — COMPARISON CHART
# ══════════════════════════════════════════════════════════════════════════════

def _render_comparison(db, tenant_id: str, user_id: str):
    st.subheader("📊 Formula Comparison Chart")
    st.caption(
        "Visualize how stocks rank across multiple formulas simultaneously. "
        "Compare factor blends, valuation metrics, and custom signals."
    )

    df = st.session_state.get("fs_results")
    formulas_used = st.session_state.get("fs_formulas_used", [])

    if df is None or df.empty:
        st.info("Run the **Formula Screener** first to generate results for comparison.")
        return

    formula_cols = [f.name for f in formulas_used if f.name in df.columns]
    if not formula_cols:
        st.info("No formula columns in screener results.")
        return

    if not PLOTLY:
        st.info("Install plotly for comparison charts.")
        return

    col_type, col_n, col_formulas = st.columns([1, 1, 2])
    with col_type:
        chart_type = st.selectbox(
            "Chart type",
            ["Bar Race", "Scatter", "Radar", "Heatmap"],
            key="cc_type",
        )
    with col_n:
        top_n = st.slider("Top N stocks", 5, 50, 20, key="cc_n")
    with col_formulas:
        sel_cols = st.multiselect(
            "Formulas to plot",
            formula_cols,
            default=formula_cols[:2],
            key="cc_cols",
        )

    top_df = df.head(top_n).copy()

    if not sel_cols:
        st.info("Select at least one formula to plot.")
        return

    if chart_type == "Bar Race":
        # Side-by-side bar chart per formula
        if len(sel_cols) == 1:
            col = sel_cols[0]
            formula_obj = next((f for f in formulas_used if f.name == col), None)
            asc = not (formula_obj.higher_is_better if formula_obj else True)
            plot_df = top_df[["symbol", col]].dropna().sort_values(col, ascending=asc)

            fig = go.Figure(go.Bar(
                x=plot_df["symbol"],
                y=plot_df[col],
                marker_color=[
                    GREEN if v >= plot_df[col].median() else RED
                    for v in plot_df[col]
                ],
                text=plot_df[col].apply(lambda x: f"{x:.2f}"),
                textposition="outside",
            ))
            fig.update_layout(
                title=f"Top {top_n} stocks by {col}",
                template="plotly_dark",
                paper_bgcolor="#0F1117", plot_bgcolor="#161B22",
                height=420, margin=dict(l=0, r=0, t=40, b=60),
                xaxis=dict(tickangle=-45),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            # Grouped bars
            fig = go.Figure()
            for col in sel_cols:
                plot_df = top_df[["symbol", col]].dropna()
                fig.add_trace(go.Bar(
                    name=col,
                    x=plot_df["symbol"],
                    y=plot_df[col],
                ))
            fig.update_layout(
                barmode="group",
                title=f"Formula Comparison — Top {top_n}",
                template="plotly_dark",
                paper_bgcolor="#0F1117", plot_bgcolor="#161B22",
                height=450, margin=dict(l=0, r=0, t=40, b=60),
                xaxis=dict(tickangle=-45),
                legend=dict(orientation="h", y=1.05),
            )
            st.plotly_chart(fig, use_container_width=True)

    elif chart_type == "Scatter" and len(sel_cols) >= 2:
        x_col = sel_cols[0]
        y_col = sel_cols[1]
        size_col = sel_cols[2] if len(sel_cols) > 2 else "composite"
        plot_df = top_df[["symbol", x_col, y_col, size_col]].dropna()

        fig = go.Figure(go.Scatter(
            x=plot_df[x_col],
            y=plot_df[y_col],
            mode="markers+text",
            text=plot_df["symbol"],
            textposition="top center",
            marker=dict(
                size=plot_df[size_col].fillna(50) / 3 + 8,
                color=plot_df[size_col],
                colorscale="RdYlGn",
                showscale=True,
                colorbar=dict(title=size_col),
            ),
        ))
        fig.update_layout(
            title=f"{x_col} vs {y_col}",
            xaxis_title=x_col,
            yaxis_title=y_col,
            template="plotly_dark",
            paper_bgcolor="#0F1117", plot_bgcolor="#161B22",
            height=450, margin=dict(l=0, r=0, t=40, b=20),
        )
        st.plotly_chart(fig, use_container_width=True)

    elif chart_type == "Radar" and len(sel_cols) >= 3:
        top5 = top_df.head(5)
        fig = go.Figure()
        for _, row in top5.iterrows():
            vals = [row.get(c, 0) or 0 for c in sel_cols]
            # Normalize 0-100
            all_vals = pd.concat([top_df[c] for c in sel_cols if c in top_df.columns]).dropna()
            if all_vals.max() > 0:
                vals = [v / all_vals.max() * 100 for v in vals]
            vals.append(vals[0])  # close the polygon

            fig.add_trace(go.Scatterpolar(
                r=vals,
                theta=sel_cols + [sel_cols[0]],
                fill="toself",
                name=row.get("symbol", ""),
                opacity=0.7,
            ))
        fig.update_layout(
            polar=dict(
                radialaxis=dict(visible=True, range=[0, 100]),
                bgcolor="#161B22",
            ),
            title=f"Radar — Top 5 stocks across {len(sel_cols)} formulas",
            template="plotly_dark",
            paper_bgcolor="#0F1117",
            height=450, margin=dict(l=20, r=20, t=60, b=20),
        )
        st.plotly_chart(fig, use_container_width=True)

    elif chart_type == "Heatmap":
        plot_df = top_df.set_index("symbol")[sel_cols].dropna(how="all")
        # Normalize each column 0-100
        for c in sel_cols:
            mn = plot_df[c].min(); mx = plot_df[c].max()
            if mx > mn:
                plot_df[c] = (plot_df[c] - mn) / (mx - mn) * 100
        fig = go.Figure(go.Heatmap(
            z=plot_df.values.tolist(),
            x=sel_cols,
            y=plot_df.index.tolist(),
            colorscale="RdYlGn",
            text=[[f"{v:.1f}" for v in row] for row in plot_df.values],
            texttemplate="%{text}",
            colorbar=dict(title="Normalized Score"),
        ))
        fig.update_layout(
            title=f"Formula Heatmap (normalized 0–100) — Top {top_n}",
            template="plotly_dark",
            paper_bgcolor="#0F1117", plot_bgcolor="#161B22",
            height=max(350, top_n * 22),
            margin=dict(l=80, r=20, t=60, b=60),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Select at least 2 formulas for Scatter, 3+ for Radar.")


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _get_sectors(db, tenant_id: str) -> list[str]:
    try:
        from sqlalchemy import text
        rows = db.execute(text("""
            SELECT DISTINCT sector FROM analytics_snapshots
            WHERE tenant_id = :tid AND sector IS NOT NULL
            ORDER BY sector
        """), {"tid": tenant_id}).fetchall()
        return [r[0] for r in rows if r[0]]
    except Exception:
        return []


def _get_symbols(db, tenant_id: str) -> list[str] | None:
    """Get all symbols from the analytics snapshot."""
    try:
        from sqlalchemy import text
        rows = db.execute(text("""
            SELECT DISTINCT symbol FROM analytics_snapshots
            WHERE tenant_id = :tid
        """), {"tid": tenant_id}).fetchall()
        return [r[0] for r in rows] if rows else None
    except Exception:
        return None