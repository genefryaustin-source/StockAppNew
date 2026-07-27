"""
modules/collab/collab_ui.py

Team Collaboration — Streamlit UI.

Tabs:
  💬 Team Chat         — internal messaging with $TICKER tagging
  📌 Annotations       — per-symbol notes visible to whole team
  👁 Shared Watchlists — share/browse team watchlists
  🔍 Screener Presets  — save and share screener configurations
  📊 Activity Feed     — what the team has been doing (last 24h)

Add to app.py:
    elif page == "Team":
        from modules.collab.collab_ui import render_team_page
        render_team_page(db, user)

Also provides render_annotation_widget(db, user, ticker) for embedding
in Stock Dashboard / price chart pages.
"""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from modules.collab.collab_service import (
    add_annotation,
    delete_annotation,
    get_activity_feed,
    get_annotations,
    get_messages,
    get_screener_presets,
    get_shared_watchlists,
    get_team_members,
    save_screener_preset,
    send_message,
    share_watchlist,
    unshare_watchlist,
    delete_screener_preset,
    log_activity,
)


# ─────────────────────────────────────────────────────────────
# Main page
# ─────────────────────────────────────────────────────────────

def render_team_page(db, user: dict):
    tenant_id = user.get("tenant_id", "")
    user_id   = user.get("user_id", "")
    email     = user.get("email", "")
    name      = email.split("@")[0]

    st.header("👥 Team Collaboration")
    st.caption(
        f"Logged in as **{name}** · Team workspace shared with all users "
        f"in your organisation"
    )

    # Team member count
    members = get_team_members(db, tenant_id)
    if len(members) > 1:
        st.info(
            f"👥 **{len(members)} team members:** "
            f"{', '.join(m['name'] for m in members[:5])}"
            + (f" + {len(members)-5} more" if len(members) > 5 else "")
        )
    else:
        st.info(
            "💡 **Solo workspace** — invite colleagues by creating user accounts "
            "with the same `tenant_id` in the admin panel. "
            "All features work solo too."
        )

    tab_chat, tab_ann, tab_watch, tab_screen, tab_feed = st.tabs([
        "💬 Team Chat",
        "📌 Annotations",
        "👁 Shared Watchlists",
        "🔍 Screener Presets",
        "📊 Activity Feed",
    ])

    with tab_chat:
        _render_chat(db, tenant_id, user_id, email, name)

    with tab_ann:
        _render_annotations(db, tenant_id, user_id, email)

    with tab_watch:
        _render_shared_watchlists(db, tenant_id, user_id, email)

    with tab_screen:
        _render_screener_presets(db, tenant_id, user_id, email)

    with tab_feed:
        _render_activity_feed(db, tenant_id)


# ─────────────────────────────────────────────────────────────
# Tab 1 — Team Chat
# ─────────────────────────────────────────────────────────────

def _render_chat(db, tenant_id: str, user_id: str, email: str, name: str):
    st.subheader("💬 Team Chat")
    st.caption(
        "Internal messaging for your team. Tag tickers with $ to link to them — "
        "e.g. *What does everyone think about $NVDA after earnings?*"
    )

    # Ticker filter
    col_f, col_r = st.columns([3, 1])
    with col_f:
        ticker_filter = st.text_input(
            "Filter by ticker (optional)",
            placeholder="NVDA",
            key="chat_filter",
        ).upper().strip()
    with col_r:
        st.write("")
        if st.button("↺ Refresh", key="chat_refresh", use_container_width=True):
            if "chat_messages" in st.session_state:
                del st.session_state["chat_messages"]

    # Load messages
    cache_key = f"chat_messages_{ticker_filter}"
    if cache_key not in st.session_state:
        st.session_state[cache_key] = get_messages(
            db, tenant_id,
            limit=50,
            ticker=ticker_filter or None,
        )

    messages = st.session_state[cache_key]

    # Message display
    st.markdown("---")
    if not messages:
        st.info(
            "No messages yet. "
            + (f"No messages about ${ticker_filter}." if ticker_filter
               else "Send the first message below!")
        )
    else:
        for msg in messages:
            is_mine = msg["user_email"] == email
            align   = "right" if is_mine else "left"
            bg      = "#1F3864" if is_mine else "#21262D"
            color   = "#BDD7EE" if is_mine else "#C9D1D9"

            # Ticker tag pills
            tags_html = ""
            if msg.get("ticker_tags"):
                for tag in msg["ticker_tags"].split(","):
                    tags_html += (
                        f"<span style='background:#2E75B6;color:white;"
                        f"padding:1px 6px;border-radius:3px;font-size:11px;"
                        f"margin-right:3px'>{tag}</span>"
                    )

            st.markdown(
                f"<div style='text-align:{align};margin-bottom:8px'>"
                f"<div style='display:inline-block;background:{bg};color:{color};"
                f"padding:8px 12px;border-radius:8px;max-width:75%;text-align:left'>"
                f"<div style='font-size:11px;color:#8B949E;margin-bottom:3px'>"
                f"{'You' if is_mine else msg['user_name']} · {msg['created_at']}</div>"
                f"<div>{msg['body']}</div>"
                f"{'<div style=margin-top:4px>' + tags_html + '</div>' if tags_html else ''}"
                f"</div></div>",
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # Message input
    col_msg, col_send = st.columns([5, 1])
    with col_msg:
        msg_text = st.text_input(
            "Message",
            placeholder="Type a message… use $TICKER to tag stocks",
            key="chat_input",
            label_visibility="collapsed",
        )
    with col_send:
        send_btn = st.button("Send", key="chat_send",
                             type="primary", use_container_width=True)

    if send_btn and msg_text.strip():
        send_message(db, tenant_id, user_id, email, msg_text.strip())
        # Clear cache so new message shows
        for k in list(st.session_state.keys()):
            if k.startswith("chat_messages"):
                del st.session_state[k]
        st.rerun()


# ─────────────────────────────────────────────────────────────
# Tab 2 — Annotations
# ─────────────────────────────────────────────────────────────

def _render_annotations(db, tenant_id: str, user_id: str, email: str):
    st.subheader("📌 Chart Annotations")
    st.caption(
        "Team notes on any ticker — visible to everyone. "
        "Annotate support levels, earnings catalysts, thesis changes, alerts."
    )

    col_sym, col_ref = st.columns([3, 1])
    with col_sym:
        symbol = st.text_input(
            "Symbol", placeholder="NVDA",
            key="ann_symbol",
        ).upper().strip()
    with col_ref:
        st.write("")
        if st.button("↺", key="ann_refresh", use_container_width=True):
            for k in list(st.session_state.keys()):
                if k.startswith("ann_cache_"):
                    del st.session_state[k]

    if not symbol:
        st.info("Enter a ticker to view and add annotations.")
        return

    _render_annotation_widget(db, user, symbol,
                               tenant_id=tenant_id, user_id=user_id, email=email,
                               expanded=True)


def _render_annotation_widget(db, user, symbol: str,
                                tenant_id: str = None, user_id: str = None,
                                email: str = None, expanded: bool = False):
    """
    Embeddable annotation widget for Stock Dashboard / price charts.
    Call with just db + user + symbol for embedding elsewhere.
    """
    if not tenant_id:
        tenant_id = (user or {}).get("tenant_id", "")
    if not user_id:
        user_id = (user or {}).get("user_id", "")
    if not email:
        email = (user or {}).get("email", "")

    cache_key = f"ann_cache_{tenant_id}_{symbol}"
    if cache_key not in st.session_state:
        st.session_state[cache_key] = get_annotations(db, tenant_id, symbol)

    annotations = st.session_state[cache_key]

    if annotations:
        for ann in annotations:
            type_icons = {
                "bullish": "🟢", "bearish": "🔴",
                "alert": "🔔", "note": "📌",
            }
            icon    = type_icons.get(ann["annotation_type"], "📌")
            pinned  = " 📍" if ann["is_pinned"] else ""
            is_mine = ann["user_email"] == email

            with st.container():
                col_body, col_del = st.columns([10, 1])
                with col_body:
                    price_str = f" @ ${ann['price_at']}" if ann.get("price_at") else ""
                    st.markdown(
                        f"{icon}{pinned} **{ann['user_name']}** "
                        f"<span style='color:#8B949E;font-size:11px'>"
                        f"{ann['created_at']}{price_str}</span>",
                        unsafe_allow_html=True,
                    )
                    st.markdown(ann["body"])
                with col_del:
                    if is_mine or (user or {}).get("role") == "super_admin":
                        if st.button("🗑", key=f"del_ann_{ann['id']}",
                                     help="Delete annotation"):
                            delete_annotation(db, ann["id"], user_id, tenant_id)
                            del st.session_state[cache_key]
                            st.rerun()
            st.markdown("---")
    else:
        st.caption(f"No team annotations for {symbol} yet.")

    # Add annotation form
    with st.expander("➕ Add annotation", expanded=expanded and not annotations):
        ann_type = st.selectbox(
            "Type",
            ["note", "bullish", "bearish", "alert"],
            key=f"ann_type_{symbol}",
            format_func=lambda x: {"note":"📌 Note","bullish":"🟢 Bullish",
                                    "bearish":"🔴 Bearish","alert":"🔔 Alert"}[x],
        )
        ann_body = st.text_area(
            "Note",
            placeholder=f"Add a note about {symbol}…",
            key=f"ann_body_{symbol}",
            height=80,
        )
        col_pin, col_save = st.columns([2, 1])
        with col_pin:
            pin = st.checkbox("Pin to top", key=f"ann_pin_{symbol}")
        with col_save:
            if st.button("Save Note", key=f"ann_save_{symbol}",
                         type="primary", use_container_width=True):
                if ann_body.strip():
                    add_annotation(
                        db, tenant_id, user_id, email, symbol,
                        ann_body.strip(), ann_type, is_pinned=pin,
                    )
                    del st.session_state[cache_key]
                    st.rerun()


# ─────────────────────────────────────────────────────────────
# Tab 3 — Shared Watchlists
# ─────────────────────────────────────────────────────────────

def _render_shared_watchlists(db, tenant_id: str, user_id: str, email: str):
    st.subheader("👁 Shared Watchlists")
    st.caption("Share your watchlists with the team or browse what colleagues have shared.")

    tab_browse, tab_share = st.tabs(["Browse Shared", "Share My Watchlist"])

    with tab_browse:
        shared = get_shared_watchlists(db, tenant_id)
        if not shared:
            st.info("No shared watchlists yet. Share one in the 'Share My Watchlist' tab.")
        else:
            for wl in shared:
                with st.container():
                    col_info, col_btn = st.columns([4, 1])
                    with col_info:
                        edit_badge = " ✏️ editable" if wl["can_edit"] else " 👁 view only"
                        st.markdown(
                            f"**{wl['name']}** — "
                            f"{wl['item_count']} symbols · "
                            f"shared by **{wl['shared_by']}** on {wl['shared_at']}"
                            f"{edit_badge}"
                        )
                        if wl.get("note"):
                            st.caption(wl["note"])
                    with col_btn:
                        if st.button("Open", key=f"open_wl_{wl['watchlist_id']}",
                                     use_container_width=True):
                            st.session_state["nav_watchlist_id"] = wl["watchlist_id"]
                            st.info(f"✅ Opened '{wl['name']}' — navigate to Watchlists to view.")
                st.markdown("---")

    with tab_share:
        # Get user's own watchlists
        try:
            from sqlalchemy import text as _text
            wls = db.execute(_text("""
                SELECT w.id, w.name,
                       (SELECT COUNT(*) FROM watchlist_items wi WHERE wi.watchlist_id = w.id) as cnt,
                       (SELECT id FROM watchlist_shares ws
                        WHERE ws.watchlist_id = w.id AND ws.tenant_id = :tid LIMIT 1) as share_id
                FROM watchlists w
                WHERE w.tenant_id = :tid
                ORDER BY w.name
            """), {"tid": tenant_id}).fetchall()
        except Exception:
            wls = []

        if not wls:
            st.info("No watchlists found. Create one in the Watchlists page first.")
        else:
            for wl in wls:
                wl_id   = str(wl[0])
                wl_name = str(wl[1])
                cnt     = int(wl[2] or 0)
                is_shared = bool(wl[3])

                col_name, col_edit, col_toggle = st.columns([3, 1, 1])
                with col_name:
                    st.markdown(f"**{wl_name}** — {cnt} symbols")
                with col_edit:
                    can_edit = st.checkbox(
                        "Allow edits",
                        key=f"wl_edit_{wl_id}",
                        value=False,
                    )
                with col_toggle:
                    if is_shared:
                        if st.button("Unshare", key=f"unshare_{wl_id}",
                                     use_container_width=True):
                            unshare_watchlist(db, wl_id, tenant_id)
                            st.rerun()
                    else:
                        if st.button("Share", key=f"share_{wl_id}",
                                     type="primary", use_container_width=True):
                            share_watchlist(db, wl_id, tenant_id, user_id, can_edit)
                            log_activity(db, tenant_id, user_id, email,
                                         "watchlist_add", detail=f"Shared watchlist '{wl_name}'")
                            st.success(f"✅ '{wl_name}' shared with team")
                            st.rerun()

            st.caption(
                "Shared watchlists are visible to all team members with the same tenant. "
                "'Allow edits' lets others add/remove symbols."
            )


# ─────────────────────────────────────────────────────────────
# Tab 4 — Screener Presets
# ─────────────────────────────────────────────────────────────

def _render_screener_presets(db, tenant_id: str, user_id: str, email: str):
    st.subheader("🔍 Screener Presets")
    st.caption(
        "Save screener filter configurations and share them with the team. "
        "Load any preset directly into the NL Screener or AI Scanner."
    )

    tab_browse, tab_save = st.tabs(["Browse Presets", "Save New Preset"])

    with tab_browse:
        presets = get_screener_presets(db, tenant_id, user_id)
        if not presets:
            st.info("No screener presets saved yet. Save one in the 'Save New Preset' tab.")
        else:
            my_presets    = [p for p in presets if p["owner"] == email.split("@")[0]]
            shared_presets= [p for p in presets if p["is_shared"] and p["owner"] != email.split("@")[0]]

            if my_presets:
                st.markdown("**My Presets**")
                for p in my_presets:
                    _render_preset_card(db, p, user_id, tenant_id, is_mine=True)

            if shared_presets:
                st.markdown("**Shared by Team**")
                for p in shared_presets:
                    _render_preset_card(db, p, user_id, tenant_id, is_mine=False)

    with tab_save:
        st.markdown("**Save current screener as a preset**")

        col1, col2 = st.columns(2)
        with col1:
            preset_name = st.text_input(
                "Preset name",
                placeholder="High momentum small caps",
                key="preset_name",
            )
            preset_desc = st.text_input(
                "Description (optional)",
                placeholder="RSI > 60, market cap < $2B, composite > 70",
                key="preset_desc",
            )
        with col2:
            preset_query = st.text_area(
                "Screener query / filters",
                placeholder="Paste your NL screener query or describe the filters…",
                key="preset_query",
                height=80,
            )
            is_shared = st.checkbox("Share with team", value=True, key="preset_shared")

        if st.button("💾 Save Preset", type="primary", key="preset_save"):
            if preset_name.strip() and preset_query.strip():
                pid = save_screener_preset(
                    db, tenant_id, user_id, email,
                    name=preset_name.strip(),
                    filters={"query": preset_query.strip()},
                    query_text=preset_query.strip(),
                    is_shared=is_shared,
                    description=preset_desc.strip() or None,
                )
                st.success(f"✅ Preset '{preset_name}' saved"
                           + (" and shared with team!" if is_shared else "!"))
                st.rerun()
            else:
                st.warning("Enter a name and query to save the preset.")


def _render_preset_card(db, preset: dict, user_id: str, tenant_id: str, is_mine: bool):
    with st.container():
        col_info, col_load, col_del = st.columns([4, 1, 1])
        with col_info:
            shared_badge = " 🔗 shared" if preset["is_shared"] else " 🔒 private"
            count_badge  = f" · {preset['result_count']} results" if preset["result_count"] else ""
            st.markdown(
                f"**{preset['name']}**{shared_badge}{count_badge}"
                + (f" — {preset['description']}" if preset.get("description") else "")
            )
            if preset.get("query_text"):
                st.caption(f"Query: {preset['query_text'][:80]}…"
                           if len(preset.get("query_text","")) > 80
                           else preset["query_text"])
            st.caption(f"By {preset['owner']} · {preset['created_at']}")
        with col_load:
            if st.button("Load", key=f"load_preset_{preset['id']}",
                         use_container_width=True):
                st.session_state["screener_preset_query"] = preset.get("query_text", "")
                st.success(f"✅ '{preset['name']}' loaded — navigate to Screener")
        with col_del:
            if is_mine:
                if st.button("🗑", key=f"del_preset_{preset['id']}",
                             help="Delete preset", use_container_width=True):
                    delete_screener_preset(db, preset["id"], user_id, tenant_id)
                    st.rerun()
    st.markdown("---")


# ─────────────────────────────────────────────────────────────
# Tab 5 — Activity Feed
# ─────────────────────────────────────────────────────────────

def _render_activity_feed(db, tenant_id: str):
    st.subheader("📊 Team Activity Feed")
    st.caption("What your team has been doing in the last 24 hours")

    col_h, col_r = st.columns([3, 1])
    with col_h:
        hours = st.selectbox("Show last", [6, 12, 24, 48, 168],
                             index=2, format_func=lambda x: f"{x}h" if x < 48 else f"{x//24}d",
                             key="feed_hours")
    with col_r:
        st.write("")
        if st.button("↺ Refresh", key="feed_refresh", use_container_width=True):
            if "activity_feed" in st.session_state:
                del st.session_state["activity_feed"]

    cache_key = f"activity_feed_{hours}"
    if cache_key not in st.session_state:
        st.session_state[cache_key] = get_activity_feed(db, tenant_id,
                                                         limit=50, hours=hours)

    events = st.session_state[cache_key]

    if not events:
        st.info("No team activity in the selected time window.")
        return

    for evt in events:
        sym_badge = (f" · <span style='background:#2E75B6;color:white;"
                     f"padding:1px 5px;border-radius:3px;font-size:11px'>"
                     f"${evt['symbol']}</span>"
                     if evt.get("symbol") else "")
        st.markdown(
            f"{evt['icon']} **{evt['user']}** {evt['detail']}{sym_badge} "
            f"<span style='color:#8B949E;font-size:11px'>{evt['time']}</span>",
            unsafe_allow_html=True,
        )


# ─────────────────────────────────────────────────────────────
# Embeddable widgets for other pages
# ─────────────────────────────────────────────────────────────

def render_annotation_widget(db, user: dict, symbol: str):
    """
    Drop-in annotation widget for Stock Dashboard, price charts, etc.
    Shows existing team annotations + quick add form.
    Usage:
        from modules.collab.collab_ui import render_annotation_widget
        render_annotation_widget(db, user, ticker)
    """
    st.markdown("#### 📌 Team Notes")
    _render_annotation_widget(db, user, symbol)


def render_chat_widget(db, user: dict, ticker: str = None):
    """
    Compact chat widget showing messages about a specific ticker.
    For embedding in stock detail pages.
    """
    tenant_id = user.get("tenant_id", "")
    user_id   = user.get("user_id", "")
    email     = user.get("email", "")
    name      = email.split("@")[0]

    msgs = get_messages(db, tenant_id, limit=10, ticker=ticker)

    if msgs:
        st.markdown(f"#### 💬 Team Chat — ${ticker}")
        for msg in msgs[-5:]:  # show last 5
            is_mine = msg["user_email"] == email
            prefix  = "**You:**" if is_mine else f"**{msg['user_name']}:**"
            st.markdown(f"{prefix} {msg['body']} "
                        f"<span style='color:#8B949E;font-size:10px'>{msg['created_at']}</span>",
                        unsafe_allow_html=True)

    # Quick message input
    col_i, col_s = st.columns([4, 1])
    with col_i:
        quick_msg = st.text_input(
            f"Message about ${ticker}",
            placeholder=f"Share thoughts on ${ticker}…",
            key=f"quick_msg_{ticker}",
            label_visibility="collapsed",
        )
    with col_s:
        if st.button("Send", key=f"quick_send_{ticker}"):
            if quick_msg.strip():
                body = f"{quick_msg.strip()} ${ticker}"
                send_message(db, tenant_id, user_id, email, body)
                st.rerun()


# ─────────────────────────────────────────────────────────────
# Helper — user dict for standalone widget calls
# ─────────────────────────────────────────────────────────────

# Allow calling _render_annotation_widget directly with user dict
def _get_user_fields(user):
    return (
        user.get("tenant_id", ""),
        user.get("user_id", ""),
        user.get("email", ""),
    )