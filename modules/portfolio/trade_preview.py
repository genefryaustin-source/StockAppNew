"""
modules/portfolio/trade_preview.py

Agentic Trade Preview Engine.

Intercepts any trade before it reaches OrderService.submit_order().
Generates a Claude-powered rationale card with:
  - Entry/exit reason (why this trade makes sense now)
  - Risk factors (what could go wrong)
  - Position sizing logic (is the qty appropriate?)
  - Suggested stop-loss (calculated from ATR or support)
  - Expected P&L range
  - Confidence score

The user sees the card and explicitly clicks Approve or Reject.
Only on Approve does the order go to submit_order().

Usage in trading_ui.py — replace the submit block:

    from modules.portfolio.trade_preview import (
        render_trade_preview,
        generate_trade_preview,
        TradePreviewResult,
    )

    if submitted:
        # Generate preview and store — don't submit yet
        preview = generate_trade_preview(
            symbol=symbol, side=side, qty=qty,
            order_type=order_type, limit_price=limit_price,
            stop_price=stop_price, portfolio_id=portfolio_id,
            db=db_session,
        )
        st.session_state["pending_trade_preview"] = preview
        st.session_state["pending_trade_params"] = dict(
            portfolio_id=portfolio_id, user_id=user_id,
            symbol=symbol, side=side, qty=qty,
            order_type=order_type, tif=tif,
            limit_price=limit_price, stop_price=stop_price,
        )

    # Render preview (handles approve/reject)
    render_trade_preview(db_session, order_service)
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import streamlit as st


# ─────────────────────────────────────────────────────────────
# Claude client
# ─────────────────────────────────────────────────────────────

def _get_client():
    import anthropic
    from modules.admin.tenant_api_keys import get_provider_key
    key = get_provider_key("ANTHROPIC_API_KEY")
    if not key:
        raise EnvironmentError("ANTHROPIC_API_KEY not set.")
    return anthropic.Anthropic(api_key=key)


def _anthropic_available() -> bool:
    try:
        from modules.admin.tenant_api_keys import get_provider_key
        return bool(get_provider_key("ANTHROPIC_API_KEY"))
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────
# Tool schema
# ─────────────────────────────────────────────────────────────

PREVIEW_TOOL = {
    "name": "submit_trade_preview",
    "description": (
        "Submit a structured trade preview card evaluating whether "
        "this trade should be executed."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "entry_rationale": {
                "type": "string",
                "description": (
                    "2-3 sentences explaining why this trade makes sense right now. "
                    "Reference specific data — price vs MA, RSI, momentum, news, "
                    "sector strength. Be direct."
                ),
            },
            "risk_factors": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "2-4 specific risks for this trade. Not generic disclaimers — "
                    "actual risks based on the stock's data. "
                    "e.g. 'RSI at 74 — overbought, pullback risk.'"
                ),
            },
            "position_sizing": {
                "type": "string",
                "description": (
                    "1-2 sentences on whether the requested qty is appropriate "
                    "given the portfolio value and position concentration. "
                    "Flag if the trade would create >10% concentration."
                ),
            },
            "suggested_stop_loss": {
                "type": ["number", "null"],
                "description": (
                    "Suggested stop-loss price. "
                    "For buys: below key support or ATR-based. "
                    "For sells: above key resistance. "
                    "Null if can't be determined."
                ),
            },
            "stop_loss_rationale": {
                "type": "string",
                "description": "1 sentence explaining the stop-loss level.",
            },
            "suggested_take_profit": {
                "type": ["number", "null"],
                "description": (
                    "Suggested take-profit price based on resistance or risk/reward ratio."
                ),
            },
            "expected_pnl_bear": {
                "type": ["number", "null"],
                "description": "Expected P&L in bear case (stop-loss hit) in dollars.",
            },
            "expected_pnl_base": {
                "type": ["number", "null"],
                "description": "Expected P&L in base case in dollars.",
            },
            "expected_pnl_bull": {
                "type": ["number", "null"],
                "description": "Expected P&L in bull case (take-profit hit) in dollars.",
            },
            "risk_reward_ratio": {
                "type": ["number", "null"],
                "description": "Risk/reward ratio. e.g. 2.5 means 2.5x reward vs risk.",
            },
            "confidence_score": {
                "type": "integer",
                "description": "AI confidence in this trade being sound, 0-100.",
            },
            "recommendation": {
                "type": "string",
                "enum": ["Proceed", "Proceed with caution", "Reconsider", "Do not proceed"],
                "description": "AI recommendation based on all factors.",
            },
            "recommendation_reason": {
                "type": "string",
                "description": "1 sentence summary of the recommendation.",
            },
        },
        "required": [
            "entry_rationale", "risk_factors", "position_sizing",
            "confidence_score", "recommendation", "recommendation_reason",
        ],
    },
}


# ─────────────────────────────────────────────────────────────
# Data class
# ─────────────────────────────────────────────────────────────

@dataclass
class TradePreviewResult:
    symbol:               str
    side:                 str
    qty:                  float
    order_type:           str
    limit_price:          Optional[float]
    stop_price:           Optional[float]
    current_price:        Optional[float]
    notional:             Optional[float]

    entry_rationale:      str              = ""
    risk_factors:         list             = field(default_factory=list)
    position_sizing:      str              = ""
    suggested_stop_loss:  Optional[float]  = None
    stop_loss_rationale:  str              = ""
    suggested_take_profit:Optional[float]  = None
    expected_pnl_bear:    Optional[float]  = None
    expected_pnl_base:    Optional[float]  = None
    expected_pnl_bull:    Optional[float]  = None
    risk_reward_ratio:    Optional[float]  = None
    confidence_score:     int              = 60
    recommendation:       str              = "Proceed with caution"
    recommendation_reason:str              = ""

    generated_at:         str              = ""
    error:                Optional[str]    = None


# ─────────────────────────────────────────────────────────────
# Data loader
# ─────────────────────────────────────────────────────────────

def _build_trade_context(
    symbol: str,
    side: str,
    qty: float,
    order_type: str,
    limit_price: Optional[float],
    stop_price: Optional[float],
    portfolio_id: str,
    db,
) -> dict:
    """Assemble all relevant data for the Claude prompt."""
    from modules.market_data.service import get_price_history

    ctx: dict = {
        "symbol":     symbol.upper(),
        "side":       side,
        "qty":        qty,
        "order_type": order_type,
        "limit_price": limit_price,
        "stop_price":  stop_price,
    }

    # ── Current price + recent history ───────────────────────
    current_price = None
    try:
        df = get_price_history(db, symbol, period="3mo", interval="1d")
        if df is not None and not df.empty and "Close" in df.columns:
            closes = df["Close"].dropna().tolist()
            if closes:
                current_price = closes[-1]
                prev          = closes[-2] if len(closes) > 1 else closes[-1]
                high_52w      = max(closes[-252:]) if len(closes) >= 252 else max(closes)
                low_52w       = min(closes[-252:]) if len(closes) >= 252 else min(closes)
                sma_50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else None
                sma_200= sum(closes[-200:]) / 200 if len(closes) >= 200 else None
                day_chg= ((current_price - prev) / prev * 100) if prev else 0

                # ATR (20-day)
                atr = None
                if "High" in df.columns and "Low" in df.columns:
                    h = df["High"].dropna().tolist()
                    l = df["Low"].dropna().tolist()
                    c = closes
                    trs = [max(h[i]-l[i], abs(h[i]-c[i-1]), abs(l[i]-c[i-1]))
                           for i in range(1, min(21, len(h)))]
                    atr = sum(trs) / len(trs) if trs else None

                ctx["price"] = {
                    "current":      round(current_price, 2),
                    "day_chg_pct":  round(day_chg, 2),
                    "52w_high":     round(high_52w, 2),
                    "52w_low":      round(low_52w, 2),
                    "sma_50":       round(sma_50, 2) if sma_50 else None,
                    "sma_200":      round(sma_200, 2) if sma_200 else None,
                    "pct_from_52w_high": round((current_price - high_52w) / high_52w * 100, 1),
                    "atr_20d":      round(atr, 2) if atr else None,
                }
                ctx["notional"] = round(current_price * qty, 2)
    except Exception as e:
        print(f"[trade_preview] price error: {e}")

    # ── Analytics snapshot ────────────────────────────────────
    try:
        from modules.analytics.models import AnalyticsSnapshot
        snap = (
            db.query(AnalyticsSnapshot)
            .filter(AnalyticsSnapshot.symbol == symbol.upper())
            .order_by(AnalyticsSnapshot.asof.desc())
            .first()
        )
        if snap:
            ctx["analytics"] = {
                "rating":    getattr(snap, "rating", None),
                "sector":    getattr(snap, "sector", None),
                "composite": getattr(snap, "composite_score", None),
                "momentum":  getattr(snap, "momentum_score", None),
                "quality":   getattr(snap, "quality_score", None),
                "risk":      getattr(snap, "risk_score", None),
                "rsi_14":    getattr(snap, "rsi_14", None),
                "sma_50":    getattr(snap, "sma_50", None),
                "sma_200":   getattr(snap, "sma_200", None),
                "support":   getattr(snap, "support", None),
                "resistance":getattr(snap, "resistance", None),
                "trend":     getattr(snap, "trend", None),
                "vol_20d":   getattr(snap, "vol_20d", None),
                "pe_ttm":    getattr(snap, "pe_ttm", None),
                "signal":    getattr(snap, "signal", None),
                "signal_rationale": getattr(snap, "signal_rationale", None),
            }
            ctx["analytics"] = {k: v for k, v in ctx["analytics"].items()
                                 if v is not None}
    except Exception as e:
        print(f"[trade_preview] analytics error: {e}")

    # ── Portfolio context ─────────────────────────────────────
    try:
        from sqlalchemy import text
        rows = db.execute(text("""
            SELECT symbol, qty, avg_cost, market_value
            FROM portfolio_positions
            WHERE portfolio_id = :pid
        """), {"pid": portfolio_id}).mappings().fetchall()

        positions = [dict(r) for r in rows]
        total_mv = sum(float(p.get("market_value") or 0) for p in positions)

        # Current position in this symbol
        existing = next((p for p in positions
                         if str(p.get("symbol", "")).upper() == symbol.upper()), None)

        ctx["portfolio"] = {
            "total_market_value": round(total_mv, 2),
            "n_positions": len(positions),
            "existing_position_qty": float(existing.get("qty", 0)) if existing else 0,
            "existing_avg_cost":     float(existing.get("avg_cost") or 0) if existing else None,
            "trade_notional":        ctx.get("notional"),
            "trade_pct_of_portfolio": round(
                ctx.get("notional", 0) / total_mv * 100, 1
            ) if total_mv else None,
        }
    except Exception as e:
        print(f"[trade_preview] portfolio context error: {e}")

    # ── News ──────────────────────────────────────────────────
    try:
        from modules.market_data.news_service import get_finnhub_news
        news = get_finnhub_news(symbol) or []
        ctx["recent_news"] = [
            {"headline": n.get("headline", ""), "source": n.get("source", "")}
            for n in news[:4]
        ]
    except Exception:
        pass

    return ctx, current_price


# ─────────────────────────────────────────────────────────────
# Core generation function
# ─────────────────────────────────────────────────────────────

def generate_trade_preview(
    symbol: str,
    side: str,
    qty: float,
    order_type: str = "market",
    limit_price: Optional[float] = None,
    stop_price:  Optional[float] = None,
    portfolio_id: str = "",
    db=None,
) -> TradePreviewResult:
    """Generate a trade preview card via Claude."""

    ctx, current_price = _build_trade_context(
        symbol, side, qty, order_type,
        limit_price, stop_price, portfolio_id, db,
    )

    notional = ctx.get("notional")
    result_base = TradePreviewResult(
        symbol=symbol.upper(),
        side=side,
        qty=qty,
        order_type=order_type,
        limit_price=limit_price,
        stop_price=stop_price,
        current_price=current_price,
        notional=notional,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )

    if not _anthropic_available():
        result_base.error = "ANTHROPIC_API_KEY not set."
        result_base.entry_rationale = "AI preview unavailable — API key not configured."
        result_base.recommendation = "Proceed with caution"
        result_base.recommendation_reason = "Manual review required — AI preview not available."
        return result_base

    try:
        client = _get_client()
    except Exception as e:
        result_base.error = str(e)
        return result_base

    system = (
        "You are a senior portfolio manager reviewing a trade before execution. "
        "Your job is to give an honest, specific assessment of this trade — "
        "not generic disclaimers. Reference the actual numbers in the data. "
        "Be direct. Flag real risks. Suggest practical stop-loss and take-profit levels. "
        "Call submit_trade_preview with your assessment."
    )

    side_verb = "buying" if side == "buy" else "selling"
    user_msg = (
        f"Review this pending trade before execution:\n\n"
        f"{side_verb.upper()} {qty} shares of {symbol.upper()}\n"
        f"Order type: {order_type}\n"
        f"{'Limit: $' + str(limit_price) if limit_price else ''}"
        f"{'Stop: $' + str(stop_price) if stop_price else ''}\n\n"
        f"Full context:\n{json.dumps(ctx, indent=2, default=str)}\n\n"
        f"Assess: entry rationale, risk factors, position sizing, "
        f"suggested stop-loss (use ATR-based or support/resistance), "
        f"take-profit, expected P&L scenarios, and overall recommendation."
    )

    try:
        message = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1024,
            system=system,
            tools=[PREVIEW_TOOL],
            tool_choice={"type": "tool", "name": "submit_trade_preview"},
            messages=[{"role": "user", "content": user_msg}],
        )

        for block in message.content:
            if block.type == "tool_use" and block.name == "submit_trade_preview":
                data = block.input
                result_base.entry_rationale       = data.get("entry_rationale", "")
                result_base.risk_factors          = data.get("risk_factors", [])
                result_base.position_sizing       = data.get("position_sizing", "")
                result_base.suggested_stop_loss   = data.get("suggested_stop_loss")
                result_base.stop_loss_rationale   = data.get("stop_loss_rationale", "")
                result_base.suggested_take_profit = data.get("suggested_take_profit")
                result_base.expected_pnl_bear     = data.get("expected_pnl_bear")
                result_base.expected_pnl_base     = data.get("expected_pnl_base")
                result_base.expected_pnl_bull     = data.get("expected_pnl_bull")
                result_base.risk_reward_ratio     = data.get("risk_reward_ratio")
                result_base.confidence_score      = int(data.get("confidence_score", 60))
                result_base.recommendation        = data.get("recommendation", "Proceed with caution")
                result_base.recommendation_reason = data.get("recommendation_reason", "")
                return result_base

        result_base.error = "No preview returned from API."
        return result_base

    except Exception as e:
        result_base.error = str(e)
        result_base.recommendation = "Proceed with caution"
        result_base.recommendation_reason = f"AI preview failed: {e}"
        return result_base


# ─────────────────────────────────────────────────────────────
# Streamlit renderer + approve/reject gate
# ─────────────────────────────────────────────────────────────

def render_trade_preview(db_session, order_service):
    """
    Call this AFTER the trade form in trading_ui.py.
    Renders the preview card if a pending trade exists.
    Handles approve → submit_order and reject → clear.
    """
    preview: Optional[TradePreviewResult] = st.session_state.get("pending_trade_preview")
    params: Optional[dict]               = st.session_state.get("pending_trade_params")

    if not preview or not params:
        return

    st.markdown("---")
    st.markdown("### 🤖 AI Trade Preview")
    st.caption(
        "Review this AI assessment before your order is submitted. "
        "**No order has been placed yet.**"
    )

    _render_preview_card(preview)

    # ── Approve / Reject buttons ──────────────────────────────
    st.markdown("---")
    col_approve, col_reject, col_edit = st.columns([1, 1, 2])

    with col_approve:
        approve_label = {
            "Proceed":               "✅ Approve & Submit",
            "Proceed with caution":  "⚠️ Approve Anyway",
            "Reconsider":            "⚠️ Submit Despite Warning",
            "Do not proceed":        "🚫 Submit Anyway",
        }.get(preview.recommendation, "✅ Approve & Submit")

        approve_btn = st.button(
            approve_label,
            key="trade_preview_approve",
            type="primary",
            use_container_width=True,
        )

    with col_reject:
        reject_btn = st.button(
            "❌ Reject Trade",
            key="trade_preview_reject",
            use_container_width=True,
        )

    with col_edit:
        # Optional: apply suggested stop-loss
        if preview.suggested_stop_loss:
            if st.button(
                f"Apply stop-loss ${preview.suggested_stop_loss:.2f} & submit",
                key="trade_preview_apply_stop",
                use_container_width=True,
            ):
                params = dict(params)
                params["stop_price"] = preview.suggested_stop_loss
                _execute_order(db_session, order_service, params)

    if approve_btn:
        _execute_order(db_session, order_service, params)

    if reject_btn:
        st.session_state.pop("pending_trade_preview", None)
        st.session_state.pop("pending_trade_params", None)
        st.warning("❌ Trade rejected. Order was not submitted.")
        st.rerun()


def _execute_order(db_session, order_service, params: dict):
    """Execute the order and clear the pending state."""
    try:
        order = order_service.submit_order(**params)
        st.session_state.pop("pending_trade_preview", None)
        st.session_state.pop("pending_trade_params", None)
        st.success(
            f"✅ Order submitted: {order.symbol} {order.side} {order.qty} "
            f"| Status: {order.status} | ID: {order.broker_order_id}"
        )
        st.rerun()
    except Exception as e:
        st.error(f"Order submission failed: {e}")


def _render_preview_card(preview: TradePreviewResult):
    """Render the full preview card UI."""

    rec = preview.recommendation
    rec_config = {
        "Proceed":               ("🟢", "#1D9E75"),
        "Proceed with caution":  ("🟡", "#BA7517"),
        "Reconsider":            ("🟠", "#FF8C00"),
        "Do not proceed":        ("🔴", "#E24B4A"),
    }
    rec_emoji, rec_color = rec_config.get(rec, ("⚪", "#8B949E"))

    # ── Trade summary bar ─────────────────────────────────────
    side_arrow = "📈 BUY" if preview.side == "buy" else "📉 SELL"
    price_str  = f"${preview.current_price:,.2f}" if preview.current_price else "—"
    notional_str = f"${preview.notional:,.2f}" if preview.notional else "—"

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Trade",        f"{side_arrow} {preview.symbol}")
    c2.metric("Qty",          f"{preview.qty:,.0f} shares")
    c3.metric("Price",        price_str)
    c4.metric("Notional",     notional_str)
    c5.metric(
        "Recommendation",
        f"{rec_emoji} {rec}",
    )

    # Confidence bar
    conf = preview.confidence_score
    conf_color = "#1D9E75" if conf >= 70 else "#BA7517" if conf >= 50 else "#E24B4A"
    st.markdown(
        f"**AI Confidence:** {conf}%  "
        f"<div style='background:#21262D;border-radius:4px;height:8px;width:100%'>"
        f"<div style='background:{conf_color};height:8px;border-radius:4px;width:{conf}%'>"
        f"</div></div>",
        unsafe_allow_html=True,
    )
    if preview.recommendation_reason:
        st.markdown(
            f"<span style='color:{rec_color};font-weight:500'>{preview.recommendation_reason}</span>",
            unsafe_allow_html=True,
        )
    st.markdown("")

    # ── Main sections ─────────────────────────────────────────
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("**📋 Entry Rationale**")
        st.markdown(preview.entry_rationale or "—")
        st.markdown("")

        st.markdown("**📐 Position Sizing**")
        st.markdown(preview.position_sizing or "—")
        st.markdown("")

    with col_right:
        st.markdown("**⚠️ Risk Factors**")
        for risk in preview.risk_factors:
            st.warning(f"⚠️ {risk}")
        if not preview.risk_factors:
            st.caption("No specific risk factors identified.")
        st.markdown("")

    # ── Stop-loss / take-profit ───────────────────────────────
    c1, c2, c3 = st.columns(3)
    if preview.suggested_stop_loss:
        c1.metric(
            "Suggested Stop-Loss",
            f"${preview.suggested_stop_loss:,.2f}",
            help=preview.stop_loss_rationale,
        )
        if preview.current_price and preview.suggested_stop_loss:
            stop_pct = (preview.suggested_stop_loss - preview.current_price) / preview.current_price * 100
            c1.caption(f"{stop_pct:+.1f}% from current · {preview.stop_loss_rationale}")

    if preview.suggested_take_profit:
        c2.metric(
            "Suggested Take-Profit",
            f"${preview.suggested_take_profit:,.2f}",
        )

    if preview.risk_reward_ratio:
        c3.metric("Risk/Reward", f"{preview.risk_reward_ratio:.1f}x")

    # ── P&L scenarios ─────────────────────────────────────────
    if any([preview.expected_pnl_bear, preview.expected_pnl_base, preview.expected_pnl_bull]):
        st.markdown("**📊 Expected P&L Scenarios**")
        pc1, pc2, pc3 = st.columns(3)
        if preview.expected_pnl_bear is not None:
            pc1.metric(
                "Bear Case",
                f"${preview.expected_pnl_bear:+,.2f}",
                delta_color="inverse" if preview.expected_pnl_bear < 0 else "normal",
            )
        if preview.expected_pnl_base is not None:
            pc2.metric(
                "Base Case",
                f"${preview.expected_pnl_base:+,.2f}",
                delta_color="normal" if preview.expected_pnl_base >= 0 else "inverse",
            )
        if preview.expected_pnl_bull is not None:
            pc3.metric(
                "Bull Case",
                f"${preview.expected_pnl_bull:+,.2f}",
                delta_color="normal",
            )

    if preview.error:
        st.caption(f"⚠️ Preview note: {preview.error}")

    st.caption(
        f"Generated {preview.generated_at[:16]} UTC · "
        "AI assessment for informational purposes. Not financial advice."
    )