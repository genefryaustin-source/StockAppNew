"""
modules/alerts/scanner_engine.py

AI Market Scanner Engine.

Translates plain-English monitoring rules like:
  "alert me when a S&P 500 stock breaks above its 52-week high on 2x average volume"
  "notify me when any tech stock has RSI below 30 and composite score above 70"
  "alert when NVDA drops more than 3% in a single day"

Into structured ScannerRule objects, evaluates them against live market data
and analytics snapshots, and fires AlertEvents via the existing AlertService.

Persistent rules are stored in alert_scanner_rules table (auto-created).
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import streamlit as st
from sqlalchemy import Column, String, Text, Boolean, DateTime, Float, text
from sqlalchemy.orm import Session

from modules.db.core import Base
from modules.db.models import gen_uuid


# ─────────────────────────────────────────────────────────────
# DB Model — persisted scanner rules
# ─────────────────────────────────────────────────────────────

class ScannerRule(Base):
    __tablename__ = "alert_scanner_rules"

    id          = Column(String, primary_key=True, default=gen_uuid)
    tenant_id   = Column(String, nullable=False, index=True)
    user_id     = Column(String, nullable=True)
    name        = Column(String, nullable=False)
    description = Column(Text, nullable=False)   # original plain-English rule
    condition   = Column(Text, nullable=False)   # JSON-serialised ScanCondition
    scope       = Column(String, default="watchlist")  # watchlist / universe / custom
    symbols     = Column(Text, nullable=True)    # JSON list if scope=custom
    active      = Column(Boolean, default=True)
    last_run    = Column(DateTime, nullable=True)
    last_fired  = Column(DateTime, nullable=True)
    fire_count  = Column(String, default="0")
    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ─────────────────────────────────────────────────────────────
# Condition data class
# ─────────────────────────────────────────────────────────────

@dataclass
class ScanCondition:
    """
    Structured condition parsed from natural language.
    All threshold fields are None if not specified.
    """
    # Price conditions
    price_above_52w_high:   bool  = False
    price_below_52w_low:    bool  = False
    price_above_sma:        Optional[int]   = None   # e.g. 50 or 200
    price_below_sma:        Optional[int]   = None
    day_change_pct_above:   Optional[float] = None   # e.g. +5%
    day_change_pct_below:   Optional[float] = None   # e.g. -3%
    price_above:            Optional[float] = None   # fixed price level
    price_below:            Optional[float] = None

    # Volume conditions
    volume_vs_avg_multiplier: Optional[float] = None  # e.g. 2.0 = 2x avg volume
    min_volume:               Optional[float] = None

    # Technical conditions
    rsi_above:              Optional[float] = None
    rsi_below:              Optional[float] = None
    near_support_pct:       Optional[float] = None   # within X% of support
    near_resistance_pct:    Optional[float] = None

    # Analytics conditions
    composite_above:        Optional[float] = None
    composite_below:        Optional[float] = None
    momentum_above:         Optional[float] = None
    momentum_below:         Optional[float] = None
    risk_above:             Optional[float] = None
    risk_below:             Optional[float] = None
    quality_above:          Optional[float] = None
    rating_in:              Optional[list]  = None   # ["Buy", "Strong Buy"]

    # Sector filter
    sector:                 Optional[str]   = None

    # Alert metadata
    alert_type:             str  = "SCANNER"
    alert_title:            str  = "Scanner Alert"
    plain_summary:          str  = ""
    warnings:               list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()
                if v is not None and v is not False and v != []}

    @classmethod
    def from_dict(cls, d: dict) -> "ScanCondition":
        obj = cls()
        for k, v in d.items():
            if hasattr(obj, k):
                setattr(obj, k, v)
        return obj


# ─────────────────────────────────────────────────────────────
# Claude tool schema
# ─────────────────────────────────────────────────────────────

SCANNER_TOOL = {
    "name": "submit_scanner_condition",
    "description": (
        "Submit a parsed scanner condition from a natural language alert rule. "
        "Only set fields that are clearly implied by the user's rule."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "price_above_52w_high":     {"type": "boolean",
                "description": "True if rule fires when price breaks above 52-week high."},
            "price_below_52w_low":      {"type": "boolean",
                "description": "True if rule fires when price breaks below 52-week low."},
            "price_above_sma":          {"type": ["integer","null"],
                "description": "SMA period to check price above (50 or 200)."},
            "price_below_sma":          {"type": ["integer","null"],
                "description": "SMA period to check price below (50 or 200)."},
            "day_change_pct_above":     {"type": ["number","null"],
                "description": "Fire if day % change exceeds this. e.g. 'up 5%' → 5.0"},
            "day_change_pct_below":     {"type": ["number","null"],
                "description": "Fire if day % change is below this (negative). e.g. 'drops 3%' → -3.0"},
            "price_above":              {"type": ["number","null"],
                "description": "Fixed price level threshold."},
            "price_below":              {"type": ["number","null"],
                "description": "Fixed price level threshold."},
            "volume_vs_avg_multiplier": {"type": ["number","null"],
                "description": "Volume multiple of 20-day average. '2x volume' → 2.0"},
            "min_volume":               {"type": ["number","null"],
                "description": "Absolute minimum volume."},
            "rsi_above":                {"type": ["number","null"],
                "description": "RSI threshold above which alert fires. 'overbought' → 70"},
            "rsi_below":                {"type": ["number","null"],
                "description": "RSI threshold below which alert fires. 'oversold' → 30"},
            "near_support_pct":         {"type": ["number","null"],
                "description": "Alert if price within X% of support level."},
            "near_resistance_pct":      {"type": ["number","null"],
                "description": "Alert if price within X% of resistance level."},
            "composite_above":          {"type": ["number","null"],
                "description": "Minimum composite score 0-100."},
            "composite_below":          {"type": ["number","null"],
                "description": "Maximum composite score 0-100."},
            "momentum_above":           {"type": ["number","null"],
                "description": "Minimum momentum score 0-100. 'strong momentum' → 65"},
            "momentum_below":           {"type": ["number","null"],
                "description": "Maximum momentum score 0-100."},
            "risk_above":               {"type": ["number","null"],
                "description": "Risk score threshold (100=highest risk)."},
            "risk_below":               {"type": ["number","null"],
                "description": "Risk score threshold. 'low risk' → 40"},
            "quality_above":            {"type": ["number","null"],
                "description": "Minimum quality score. 'high quality' → 65"},
            "rating_in":                {
                "type": ["array","null"],
                "items": {"type": "string", "enum": ["Buy","Strong Buy","Hold","Sell","N/A"]},
                "description": "'buy rated' → ['Buy','Strong Buy']"},
            "sector":                   {"type": ["string","null"],
                "description": "Sector filter. Map 'tech' → 'Technology'."},
            "alert_type":               {"type": "string", "default": "SCANNER"},
            "alert_title":              {"type": "string",
                "description": "Short title for the alert notification. Max 80 chars."},
            "plain_summary":            {"type": "string",
                "description": "1 sentence confirming what condition was parsed."},
            "warnings":                 {
                "type": "array", "items": {"type": "string"},
                "description": "Parts of the rule that couldn't be mapped."},
        },
        "required": ["alert_title", "plain_summary", "warnings"],
    },
}


# ─────────────────────────────────────────────────────────────
# NL → Condition translation
# ─────────────────────────────────────────────────────────────

def translate_rule(rule_text: str) -> ScanCondition:
    """Translate plain-English rule into a ScanCondition via Claude."""
    try:
        import anthropic
        key = (
            os.getenv("ANTHROPIC_API_KEY")
            or st.secrets.get("ANTHROPIC_API_KEY", "")
        )
        client = anthropic.Anthropic(api_key=key)
    except Exception as e:
        c = ScanCondition()
        c.warnings = [f"Anthropic unavailable: {e}"]
        return c

    system = (
        "You are a financial data expert translating investor alert rules into "
        "structured scanner conditions. Only set fields that are explicitly or "
        "clearly implied by the rule. Do not add conditions the user didn't mention. "
        "Call submit_scanner_condition with your parsed result."
    )

    user_msg = (
        f"Parse this stock alert rule into scanner conditions:\n\n"
        f"\"{rule_text}\"\n\n"
        f"Notes:\n"
        f"- '52-week high breakout' → price_above_52w_high=true\n"
        f"- '2x average volume' → volume_vs_avg_multiplier=2.0\n"
        f"- 'drops 3%' → day_change_pct_below=-3.0\n"
        f"- 'RSI under 30' → rsi_below=30\n"
        f"- 'tech stocks' → sector='Technology'\n"
        f"- 'buy rated' → rating_in=['Buy','Strong Buy']\n"
        f"- 'oversold' → rsi_below=30; 'overbought' → rsi_above=70\n"
        f"- Composite/momentum/risk scores are 0-100\n"
    )

    try:
        message = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=512,
            system=system,
            tools=[SCANNER_TOOL],
            tool_choice={"type": "tool", "name": "submit_scanner_condition"},
            messages=[{"role": "user", "content": user_msg}],
        )
        for block in message.content:
            if block.type == "tool_use" and block.name == "submit_scanner_condition":
                return ScanCondition.from_dict(block.input)
    except Exception as e:
        c = ScanCondition()
        c.warnings = [f"Translation error: {e}"]
        return c

    return ScanCondition()


# ─────────────────────────────────────────────────────────────
# Condition evaluator
# ─────────────────────────────────────────────────────────────

def evaluate_condition(
    symbol: str,
    condition: ScanCondition,
    db,
    snapshot=None,
) -> tuple[bool, str]:
    """
    Evaluate a ScanCondition against live data for one symbol.
    Returns (fired: bool, reason: str).
    """
    from modules.market_data.service import get_price_history
    from modules.analytics.models import AnalyticsSnapshot

    reasons = []

    # ── Load price history ────────────────────────────────────
    px = None
    try:
        px = get_price_history(db, symbol, period="1y", interval="1d")
    except Exception:
        pass

    closes   = []
    volumes  = []
    last_px  = None
    prev_px  = None
    high_52w = None
    low_52w  = None
    sma_50   = None
    sma_200  = None
    vol_20d_avg = None
    day_chg_pct = None

    if px is not None and not px.empty and "Close" in px.columns:
        closes = px["Close"].dropna().tolist()
        if "Volume" in px.columns:
            volumes = px["Volume"].dropna().tolist()

        if closes:
            last_px  = closes[-1]
            prev_px  = closes[-2] if len(closes) > 1 else last_px
            high_52w = max(closes[-252:]) if len(closes) >= 252 else max(closes)
            low_52w  = min(closes[-252:]) if len(closes) >= 252 else min(closes)
            sma_50   = sum(closes[-50:]) / 50 if len(closes) >= 50 else None
            sma_200  = sum(closes[-200:]) / 200 if len(closes) >= 200 else None
            day_chg_pct = ((last_px - prev_px) / prev_px * 100) if prev_px else 0

        if volumes:
            vol_20d_avg = sum(volumes[-20:]) / min(20, len(volumes))

    # ── Load analytics snapshot ───────────────────────────────
    snap = snapshot
    if snap is None and db is not None:
        try:
            snap = (
                db.query(AnalyticsSnapshot)
                .filter(AnalyticsSnapshot.symbol == symbol)
                .order_by(AnalyticsSnapshot.asof.desc())
                .first()
            )
        except Exception:
            pass

    rsi       = float(getattr(snap, "rsi_14", 0) or 0) if snap else None
    composite = float(getattr(snap, "composite_score", 0) or 0) if snap else None
    momentum  = float(getattr(snap, "momentum_score", 0) or 0) if snap else None
    risk      = float(getattr(snap, "risk_score", 0) or 0) if snap else None
    quality   = float(getattr(snap, "quality_score", 0) or 0) if snap else None
    rating    = getattr(snap, "rating", None) if snap else None
    sector    = getattr(snap, "sector", None) if snap else None
    support   = float(getattr(snap, "support", 0) or 0) if snap else None
    resistance= float(getattr(snap, "resistance", 0) or 0) if snap else None

    # ── Evaluate each condition ───────────────────────────────

    def _fail(reason):
        return False, reason

    # Sector filter — must match
    if condition.sector and sector:
        if condition.sector.lower() not in sector.lower():
            return False, f"Sector {sector} ≠ {condition.sector}"

    # Price conditions
    if condition.price_above_52w_high:
        if last_px is None or high_52w is None:
            return False, "No price data"
        if last_px <= high_52w:
            return False, f"${last_px:.2f} ≤ 52w high ${high_52w:.2f}"
        reasons.append(f"52w breakout: ${last_px:.2f} > ${high_52w:.2f}")

    if condition.price_below_52w_low:
        if last_px is None or low_52w is None:
            return False, "No price data"
        if last_px >= low_52w:
            return False, f"${last_px:.2f} ≥ 52w low ${low_52w:.2f}"
        reasons.append(f"52w breakdown: ${last_px:.2f} < ${low_52w:.2f}")

    if condition.price_above_sma is not None:
        sma = sma_50 if condition.price_above_sma == 50 else sma_200
        if last_px is None or sma is None:
            return False, f"SMA{condition.price_above_sma} unavailable"
        if last_px <= sma:
            return False, f"${last_px:.2f} ≤ SMA{condition.price_above_sma} ${sma:.2f}"
        reasons.append(f"Above SMA{condition.price_above_sma}: ${last_px:.2f} > ${sma:.2f}")

    if condition.price_below_sma is not None:
        sma = sma_50 if condition.price_below_sma == 50 else sma_200
        if last_px is None or sma is None:
            return False, f"SMA{condition.price_below_sma} unavailable"
        if last_px >= sma:
            return False, f"${last_px:.2f} ≥ SMA{condition.price_below_sma} ${sma:.2f}"
        reasons.append(f"Below SMA{condition.price_below_sma}: ${last_px:.2f} < ${sma:.2f}")

    if condition.day_change_pct_above is not None:
        if day_chg_pct is None:
            return False, "No price change data"
        if day_chg_pct <= condition.day_change_pct_above:
            return False, f"Day chg {day_chg_pct:.2f}% ≤ {condition.day_change_pct_above:.2f}%"
        reasons.append(f"Day gain {day_chg_pct:+.2f}% > {condition.day_change_pct_above:+.2f}%")

    if condition.day_change_pct_below is not None:
        if day_chg_pct is None:
            return False, "No price change data"
        if day_chg_pct >= condition.day_change_pct_below:
            return False, f"Day chg {day_chg_pct:.2f}% ≥ {condition.day_change_pct_below:.2f}%"
        reasons.append(f"Day drop {day_chg_pct:+.2f}% < {condition.day_change_pct_below:+.2f}%")

    if condition.price_above is not None:
        if last_px is None or last_px <= condition.price_above:
            return False, f"${last_px:.2f} ≤ ${condition.price_above:.2f}"
        reasons.append(f"Price ${last_px:.2f} > ${condition.price_above:.2f}")

    if condition.price_below is not None:
        if last_px is None or last_px >= condition.price_below:
            return False, f"${last_px:.2f} ≥ ${condition.price_below:.2f}"
        reasons.append(f"Price ${last_px:.2f} < ${condition.price_below:.2f}")

    # Volume conditions
    if condition.volume_vs_avg_multiplier is not None:
        if not volumes or vol_20d_avg is None or vol_20d_avg == 0:
            return False, "No volume data"
        last_vol = volumes[-1]
        ratio = last_vol / vol_20d_avg
        if ratio < condition.volume_vs_avg_multiplier:
            return False, f"Volume {ratio:.1f}x avg < {condition.volume_vs_avg_multiplier:.1f}x"
        reasons.append(f"Volume {ratio:.1f}x 20d avg ({last_vol:,.0f} vs {vol_20d_avg:,.0f})")

    if condition.min_volume is not None:
        if not volumes or volumes[-1] < condition.min_volume:
            return False, f"Volume {volumes[-1] if volumes else 0:,.0f} < {condition.min_volume:,.0f}"
        reasons.append(f"Volume {volumes[-1]:,.0f} ≥ {condition.min_volume:,.0f}")

    # Technical conditions
    if condition.rsi_above is not None:
        if rsi is None:
            return False, "No RSI data"
        if rsi <= condition.rsi_above:
            return False, f"RSI {rsi:.1f} ≤ {condition.rsi_above:.1f}"
        reasons.append(f"RSI {rsi:.1f} > {condition.rsi_above:.1f}")

    if condition.rsi_below is not None:
        if rsi is None:
            return False, "No RSI data"
        if rsi >= condition.rsi_below:
            return False, f"RSI {rsi:.1f} ≥ {condition.rsi_below:.1f}"
        reasons.append(f"RSI {rsi:.1f} < {condition.rsi_below:.1f}")

    if condition.near_support_pct is not None and support and last_px:
        pct_from = abs(last_px - support) / support * 100
        if pct_from > condition.near_support_pct:
            return False, f"{pct_from:.2f}% from support > {condition.near_support_pct:.2f}%"
        reasons.append(f"Within {pct_from:.2f}% of support ${support:.2f}")

    if condition.near_resistance_pct is not None and resistance and last_px:
        pct_from = abs(last_px - resistance) / resistance * 100
        if pct_from > condition.near_resistance_pct:
            return False, f"{pct_from:.2f}% from resistance > {condition.near_resistance_pct:.2f}%"
        reasons.append(f"Within {pct_from:.2f}% of resistance ${resistance:.2f}")

    # Analytics conditions
    if condition.composite_above is not None:
        if composite is None or composite <= condition.composite_above:
            return False, f"Composite {composite} ≤ {condition.composite_above}"
        reasons.append(f"Composite {composite:.0f} > {condition.composite_above:.0f}")

    if condition.composite_below is not None:
        if composite is None or composite >= condition.composite_below:
            return False, f"Composite {composite} ≥ {condition.composite_below}"
        reasons.append(f"Composite {composite:.0f} < {condition.composite_below:.0f}")

    if condition.momentum_above is not None:
        if momentum is None or momentum <= condition.momentum_above:
            return False, f"Momentum {momentum} ≤ {condition.momentum_above}"
        reasons.append(f"Momentum {momentum:.0f} > {condition.momentum_above:.0f}")

    if condition.risk_below is not None:
        if risk is None or risk >= condition.risk_below:
            return False, f"Risk {risk} ≥ {condition.risk_below}"
        reasons.append(f"Risk {risk:.0f} < {condition.risk_below:.0f}")

    if condition.quality_above is not None:
        if quality is None or quality <= condition.quality_above:
            return False, f"Quality {quality} ≤ {condition.quality_above}"
        reasons.append(f"Quality {quality:.0f} > {condition.quality_above:.0f}")

    if condition.rating_in:
        if rating not in condition.rating_in:
            return False, f"Rating {rating} not in {condition.rating_in}"
        reasons.append(f"Rating: {rating}")

    if not reasons:
        return False, "No conditions matched"

    return True, " · ".join(reasons)


# ─────────────────────────────────────────────────────────────
# Scanner runner — evaluates a rule across all symbols
# ─────────────────────────────────────────────────────────────

def run_scanner_rule(
    db,
    rule: ScannerRule,
    tenant_id: str,
    symbols: list[str],
) -> list[dict]:
    """
    Run a single ScannerRule across all symbols.
    Fires AlertEvents for matches. Returns list of fired alerts.
    """
    from modules.alerts.models import AlertEvent

    condition = ScanCondition.from_dict(json.loads(rule.condition))
    fired = []

    for sym in symbols:
        try:
            db.rollback()  # Ensure clean session state
        except Exception:
            pass

        try:
            matched, reason = evaluate_condition(sym, condition, db)
            if not matched:
                continue

            # Dedup — don't fire same rule+symbol twice in 24h
            existing = (
                db.query(AlertEvent)
                .filter(
                    AlertEvent.tenant_id == tenant_id,
                    AlertEvent.symbol == sym,
                    AlertEvent.alert_type == "SCANNER",
                    AlertEvent.title == condition.alert_title,
                )
                .order_by(AlertEvent.created_at.desc())
                .first()
            )
            if existing:
                age_hrs = (
                    datetime.now(timezone.utc) - existing.created_at.replace(tzinfo=timezone.utc)
                ).total_seconds() / 3600
                if age_hrs < 24:
                    continue

            event = AlertEvent(
                tenant_id=tenant_id,
                symbol=sym,
                alert_type="SCANNER",
                title=condition.alert_title,
                message=(
                    f"Scanner rule '{rule.name}' fired for {sym}. "
                    f"Conditions met: {reason}. "
                    f"Rule: {rule.description}"
                ),
            )
            db.add(event)
            db.commit()

            fired.append({
                "symbol": sym,
                "title":  condition.alert_title,
                "reason": reason,
            })

        except Exception as e:
            try:
                db.rollback()
            except Exception:
                pass
            print(f"[scanner] error on {sym}: {e}")

    # Update last_run
    try:
        rule.last_run = datetime.now(timezone.utc)
        if fired:
            rule.last_fired = datetime.now(timezone.utc)
            rule.fire_count = str(int(rule.fire_count or 0) + len(fired))
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass

    return fired