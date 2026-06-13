"""
modules/auth/entitlements.py

Feature entitlement system — maps plans to pages/features.

Plans: starter | pro | team | super_admin (bypasses all gates)

Usage in app.py page routing:
    from modules.auth.entitlements import check_plan, UPGRADE_PROMPT
    if not check_plan(user, "pro"):
        UPGRADE_PROMPT("pro")
        st.stop()

Usage in module UI:
    from modules.auth.entitlements import require_plan
    require_plan(user, "pro")  # stops page rendering if not entitled
"""
from __future__ import annotations
import streamlit as st

# ─────────────────────────────────────────────────────────────
# Plan hierarchy
# ─────────────────────────────────────────────────────────────

PLAN_RANK = {
    "student":    1,
    "starter":    2,
    "pro":        3,
    "team":       4,
    "super_admin":99,
    "tenant_admin":4,   # tenant_admin = team level
}

# ─────────────────────────────────────────────────────────────
# Feature → minimum plan required
# ─────────────────────────────────────────────────────────────

FEATURE_PLANS: dict[str, str] = {
    # ── Student (core only — $9/mo) ──────────────────────────
    "Watchlists":          "student",
    "Help":                "student",

    # ── Starter ($29/mo) ─────────────────────────────────────
    "Screener":            "starter",
    "Market Overview":     "starter",
    "Earnings":            "starter",
    "Stock Dashboard":     "starter",
    "Rankings":            "starter",
    "Analytics":           "starter",
    "Universe":            "starter",
    "Admin":               "starter",   # gated separately by role

    # ── Pro ──────────────────────────────────────────────────
    "Formula Builder":     "pro",
    "Intraday Charts":     "pro",
    "Options Flow":        "pro",
    "Options Trading":     "pro",
    "Crypto":              "pro",
    "Portfolio":           "pro",
    "Portfolio Construction": "pro",
    "Portfolio Deployment":"pro",
    "AI Rankings":         "pro",
    "AI Forecast":         "pro",
    "AI Scanner":          "pro",
    "AI Agent":            "pro",
    "AI Portfolio":        "pro",
    "Market Data":         "pro",
    "Analyst Consensus":   "pro",
    "Social Sentiment":    "pro",
    "Research Reports":    "pro",
    "Export / Sheets":     "pro",
    "Regime Engine":       "pro",
    "Strategy Lab":        "pro",
    "Strategy Discovery":  "pro",
    "Strategy Library":    "pro",
    "Smart Money":         "pro",
    "Alerts":              "pro",
    "Indicator Builder":   "pro",
    "Macro Dashboard":     "pro",

    # ── Pro (additional) ─────────────────────────────────────
    "IPO Intelligence":    "pro",
    "Pre-IPO Intelligence":"pro",

    # ── Team ─────────────────────────────────────────────────
    "Team Collaboration":  "team",
    "Team":                "team",
}

# ─────────────────────────────────────────────────────────────
# Plan metadata (for upgrade prompts)
# ─────────────────────────────────────────────────────────────

PLAN_META = {
    "student": {
        "name":    "Student",
        "price":   "$9/month",
        "color":   "#BA7517",
        "emoji":   "🎓",
        "features": [
            "Core Watchlists",
            "Basic Research Tools",
            "Learning-Friendly Workflow",
        ],
    },
    "starter": {
        "name":    "Starter",
        "price":   "$29/month",
        "color":   "#8B949E",
        "emoji":   "🥉",
        "features": [
            "Watchlists, Screener, Analytics",
            "Rankings & Daily Charting",
            "1 Portfolio, 1 Universe",
            "Formula Builder (read-only)",
            "Market Overview & Earnings",
        ],
    },
    "pro": {
        "name":    "Pro",
        "price":   "$79/month",
        "color":   "#2E75B6",
        "emoji":   "🥈",
        "features": [
            "Everything in Starter",
            "Formula Builder & Custom Screener",
            "Intraday Charts (1m–1W)",
            "Options Flow + Options Trading",
            "Full AI Suite (Rankings, Scanner, Agent, Forecast)",
            "Portfolio Construction & Deployment (Alpaca)",
            "Crypto Markets + AI Analysis",
            "Analyst Consensus & Social Sentiment",
            "PDF Research Reports",
            "Excel / Google Sheets Export",
            "Strategy Lab & Regime Engine",
        ],
    },
    "team": {
        "name":    "Team",
        "price":   "$149/seat/month",
        "color":   "#1D9E75",
        "emoji":   "🥇",
        "features": [
            "Everything in Pro",
            "Team Chat & Collaboration",
            "Shared Watchlists & Annotations",
            "Shared Screener Presets",
            "FINRA Dark Pool Data",
            "Activity Feed",
            "3-seat minimum",
        ],
    },
}

# ─────────────────────────────────────────────────────────────
# Core gate functions
# ─────────────────────────────────────────────────────────────

def get_user_plan(user: dict) -> str:
    """Get the effective plan for a user."""
    role = (user or {}).get("role", "")
    if role == "super_admin":
        return "super_admin"
    plan = (user or {}).get("plan", "student") or "student"
    # tenant_admin gets team-level access
    if role == "tenant_admin" and PLAN_RANK.get(plan, 1) < PLAN_RANK["team"]:
        return "team"
    return plan


def check_plan(user: dict, required_plan: str) -> bool:
    """Return True if user's plan meets or exceeds the required plan."""
    user_plan  = get_user_plan(user)
    user_rank  = PLAN_RANK.get(user_plan, 1)
    req_rank   = PLAN_RANK.get(required_plan, 1)
    return user_rank >= req_rank


def check_page(user: dict, page: str, db=None) -> bool:
    """
    Return True if user can access the given page.
    Checks: plan entitlement → tenant module override (if db provided).
    """
    required   = FEATURE_PLANS.get(page, "pro")
    plan_ok    = check_plan(user, required)

    # Check tenant-level override if DB available
    if db is not None:
        tenant_id = (user or {}).get("tenant_id", "")
        if tenant_id:
            try:
                from modules.auth.custom_plan_service import check_module_access
                return check_module_access(db, tenant_id, page, plan_ok)
            except Exception:
                pass

    return plan_ok


def require_plan(user: dict, required_plan: str, feature_name: str = ""):
    """
    Gate a feature — shows upgrade prompt and stops execution if not entitled.
    Call at the top of any page render function.
    """
    if not check_plan(user, required_plan):
        _show_upgrade_prompt(user, required_plan, feature_name)
        st.stop()


def require_page(user: dict, page: str, db=None):
    """Gate a full page by page name, with optional tenant override check."""
    if not check_page(user, page, db):
        required = FEATURE_PLANS.get(page, "pro")
        _show_upgrade_prompt(user, required, page)
        st.stop()


# ─────────────────────────────────────────────────────────────
# Upgrade prompt UI
# ─────────────────────────────────────────────────────────────

def _show_upgrade_prompt(user: dict, required_plan: str, feature_name: str = ""):
    user_plan = get_user_plan(user)
    req_meta  = PLAN_META.get(required_plan, PLAN_META["pro"])
    cur_meta  = PLAN_META.get(user_plan, PLAN_META["starter"])

    color = req_meta["color"]
    emoji = req_meta["emoji"]
    name  = req_meta["name"]
    price = req_meta["price"]

    st.markdown(
        f"<div style='text-align:center;padding:40px 20px'>"
        f"<h2>{emoji} {name} Feature</h2>"
        f"<p style='color:#8B949E;font-size:16px'>"
        f"{'<b>' + feature_name + '</b> requires' if feature_name else 'This feature requires'} "
        f"the <span style='color:{color}'><b>{name}</b></span> plan.</p>"
        f"<p style='color:#8B949E'>You are currently on the "
        f"<b>{cur_meta['name']}</b> plan.</p>"
        f"</div>",
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(
            f"<div style='background:#161B22;border:1px solid {color};"
            f"border-radius:8px;padding:20px;text-align:center'>"
            f"<h3 style='color:{color}'>{emoji} {name} — {price}</h3>",
            unsafe_allow_html=True,
        )
        for feat in req_meta["features"]:
            st.markdown(f"✅ {feat}")

        st.markdown("</div>", unsafe_allow_html=True)
        st.write("")
        st.button(
            f"⬆️ Upgrade to {name}",
            type="primary",
            use_container_width=True,
            key=f"upgrade_btn_{required_plan}",
            help="Contact your administrator or visit the billing page to upgrade",
            on_click=lambda: st.session_state.update({"show_upgrade_modal": True}),
        )
        st.caption(
            "Contact your administrator or email **billing@yourdomain.com** to upgrade."
        )

    # Show plan comparison
    with st.expander("📊 Compare all plans", expanded=False):
        cols = st.columns(4)
        for i, (plan_key, meta) in enumerate(PLAN_META.items()):
            with cols[i]:
                is_current = (plan_key == user_plan)
                is_required = (plan_key == required_plan)
                border = f"2px solid {meta['color']}" if (is_current or is_required) else "1px solid #30363D"
                label  = " ← Current" if is_current else (" ← Required" if is_required else "")
                st.markdown(
                    f"<div style='border:{border};border-radius:8px;padding:12px'>"
                    f"<h4 style='color:{meta['color']}'>{meta['emoji']} {meta['name']}{label}</h4>"
                    f"<p style='color:{meta['color']};font-size:18px;font-weight:bold'>{meta['price']}</p>",
                    unsafe_allow_html=True,
                )
                for feat in meta["features"]:
                    st.markdown(f"<p style='font-size:12px;margin:2px 0'>✅ {feat}</p>",
                                unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# Admin helper — update plan in DB
# ─────────────────────────────────────────────────────────────

def set_user_plan(db, user_id: str, plan: str):
    """Update a user's plan in the database."""
    from sqlalchemy import text
    db.execute(text("""
        UPDATE users SET plan = :plan WHERE id = :uid
    """), {"plan": plan, "uid": user_id})
    db.commit()


def get_all_plans() -> list[str]:
    return ["student", "starter", "pro", "team"]


def sidebar_plan_badge(user: dict):
    """Show a small plan badge in the sidebar."""
    plan = get_user_plan(user)
    meta = PLAN_META.get(plan, PLAN_META["starter"])
    st.sidebar.markdown(
        f"<div style='background:#161B22;border:1px solid {meta['color']};"
        f"border-radius:4px;padding:4px 8px;margin:4px 0;text-align:center;"
        f"font-size:12px;color:{meta['color']}'>"
        f"{meta['emoji']} <b>{meta['name']}</b> Plan</div>",
        unsafe_allow_html=True,
    )