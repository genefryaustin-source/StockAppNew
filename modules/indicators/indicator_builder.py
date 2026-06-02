"""
modules/indicators/indicator_builder.py

Custom Indicator Builder.

Translates natural language like:
  "RSI crossed above 30 in the last 3 days while price is above 200-day MA"
  "golden cross (50-day SMA crossed above 200-day SMA) in the past week"
  "MACD bullish crossover with volume 1.5x average"
  "Bollinger Band squeeze with price near support"

Into a structured IndicatorFormula, evaluates it against raw OHLCV data
for every symbol in the user's universe, and returns a ranked results table.

Fully composable with the existing screener — results feed into run_screener
for further filtering, or stand alone as a separate scan.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd
import streamlit as st


# ─────────────────────────────────────────────────────────────
# IndicatorFormula — structured output from Claude
# ─────────────────────────────────────────────────────────────

@dataclass
class IndicatorFormula:
    """
    A structured technical indicator condition parsed from natural language.
    Each field maps to a specific evaluator in indicator_engine.py.
    Multiple conditions are ANDed together.
    """

    # RSI conditions
    rsi_cross_above:        Optional[float] = None   # RSI crossed above this level
    rsi_cross_above_period: int             = 14
    rsi_cross_above_days:   int             = 3
    rsi_cross_below:        Optional[float] = None
    rsi_cross_below_period: int             = 14
    rsi_cross_below_days:   int             = 3
    rsi_above:              Optional[float] = None   # RSI currently above level
    rsi_below:              Optional[float] = None   # RSI currently below level

    # Price vs SMA/EMA
    price_above_sma:        Optional[int]   = None   # price above SMA(N)
    price_below_sma:        Optional[int]   = None
    price_above_ema:        Optional[int]   = None
    price_below_ema:        Optional[int]   = None

    # SMA crossovers
    sma_cross_above_fast:   Optional[int]   = None   # fast SMA
    sma_cross_above_slow:   Optional[int]   = None   # slow SMA (golden cross)
    sma_cross_above_days:   int             = 5
    sma_cross_below_fast:   Optional[int]   = None   # death cross
    sma_cross_below_slow:   Optional[int]   = None
    sma_cross_below_days:   int             = 5

    # MACD
    macd_cross_above:       bool            = False  # MACD crossed above signal
    macd_cross_above_days:  int             = 3
    macd_cross_below:       bool            = False
    macd_cross_below_days:  int             = 3
    macd_positive:          bool            = False  # MACD histogram > 0

    # Bollinger Bands
    bb_squeeze:             bool            = False  # band width < threshold
    bb_squeeze_threshold:   float           = 0.05
    price_above_bb_upper:   bool            = False
    price_below_bb_lower:   bool            = False

    # Volume
    volume_spike:           Optional[float] = None   # volume X times avg
    volume_spike_period:    int             = 20

    # 52-week
    high_52w_breakout:      bool            = False
    high_52w_breakout_days: int             = 3
    low_52w_breakdown:      bool            = False
    low_52w_breakdown_days: int             = 3

    # Higher highs / lower lows
    higher_highs:           bool            = False
    higher_highs_count:     int             = 3
    higher_highs_days:      int             = 5
    lower_lows:             bool            = False
    lower_lows_count:       int             = 3
    lower_lows_days:        int             = 5

    # Sector filter
    sector:                 Optional[str]   = None

    # Metadata
    formula_name:           str             = "Custom Indicator"
    plain_summary:          str             = ""
    warnings:               list            = field(default_factory=list)
    price_period:           str             = "1y"   # data fetch period

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()
                if v is not None and v is not False and v != []}

    @classmethod
    def from_dict(cls, d: dict) -> "IndicatorFormula":
        obj = cls()
        for k, v in d.items():
            if hasattr(obj, k):
                setattr(obj, k, v)
        return obj

    def has_conditions(self) -> bool:
        """True if at least one condition is set."""
        skip = {"formula_name", "plain_summary", "warnings", "price_period", "sector"}
        for k, v in self.__dict__.items():
            if k in skip:
                continue
            if v is not None and v is not False and v != []:
                return True
        return False


# ─────────────────────────────────────────────────────────────
# Claude tool schema
# ─────────────────────────────────────────────────────────────

INDICATOR_TOOL = {
    "name": "submit_indicator_formula",
    "description": (
        "Submit a parsed technical indicator formula from a natural language description. "
        "Only set fields explicitly implied by the user. Multiple conditions are ANDed."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            # RSI
            "rsi_cross_above": {"type": ["number","null"],
                "description": "RSI crossed above this level. e.g. 'RSI crossed above 30' → 30"},
            "rsi_cross_above_period": {"type": "integer", "default": 14},
            "rsi_cross_above_days": {"type": "integer", "default": 3,
                "description": "Lookback window in trading days"},
            "rsi_cross_below": {"type": ["number","null"],
                "description": "RSI crossed below this level. e.g. 'RSI crossed below 70' → 70"},
            "rsi_cross_below_period": {"type": "integer", "default": 14},
            "rsi_cross_below_days": {"type": "integer", "default": 3},
            "rsi_above": {"type": ["number","null"],
                "description": "RSI is currently above this level (not a crossover)."},
            "rsi_below": {"type": ["number","null"],
                "description": "RSI is currently below this level."},

            # Price vs MA
            "price_above_sma": {"type": ["integer","null"],
                "description": "Price is above SMA of this period. '200-day MA' → 200"},
            "price_below_sma": {"type": ["integer","null"],
                "description": "Price is below SMA of this period."},
            "price_above_ema": {"type": ["integer","null"],
                "description": "Price is above EMA of this period."},
            "price_below_ema": {"type": ["integer","null"],
                "description": "Price is below EMA of this period."},

            # SMA crossovers
            "sma_cross_above_fast": {"type": ["integer","null"],
                "description": "Fast SMA period for golden cross. '50/200 golden cross' → 50"},
            "sma_cross_above_slow": {"type": ["integer","null"],
                "description": "Slow SMA period for golden cross. '50/200 golden cross' → 200"},
            "sma_cross_above_days": {"type": "integer", "default": 5},
            "sma_cross_below_fast": {"type": ["integer","null"],
                "description": "Fast SMA for death cross."},
            "sma_cross_below_slow": {"type": ["integer","null"],
                "description": "Slow SMA for death cross."},
            "sma_cross_below_days": {"type": "integer", "default": 5},

            # MACD
            "macd_cross_above": {"type": "boolean", "default": False,
                "description": "MACD crossed above signal line. 'MACD bullish crossover' → true"},
            "macd_cross_above_days": {"type": "integer", "default": 3},
            "macd_cross_below": {"type": "boolean", "default": False},
            "macd_cross_below_days": {"type": "integer", "default": 3},
            "macd_positive": {"type": "boolean", "default": False,
                "description": "MACD histogram is currently positive."},

            # Bollinger
            "bb_squeeze": {"type": "boolean", "default": False,
                "description": "Bollinger Band squeeze (narrow bands). 'BB squeeze' → true"},
            "bb_squeeze_threshold": {"type": "number", "default": 0.05},
            "price_above_bb_upper": {"type": "boolean", "default": False,
                "description": "Price above upper Bollinger Band."},
            "price_below_bb_lower": {"type": "boolean", "default": False},

            # Volume
            "volume_spike": {"type": ["number","null"],
                "description": "Volume multiple of N-day average. '2x average volume' → 2.0"},
            "volume_spike_period": {"type": "integer", "default": 20},

            # 52-week
            "high_52w_breakout": {"type": "boolean", "default": False,
                "description": "Price made new 52-week high recently."},
            "high_52w_breakout_days": {"type": "integer", "default": 3},
            "low_52w_breakdown": {"type": "boolean", "default": False},
            "low_52w_breakdown_days": {"type": "integer", "default": 3},

            # Higher highs
            "higher_highs": {"type": "boolean", "default": False,
                "description": "Stock making consecutive higher highs."},
            "higher_highs_count": {"type": "integer", "default": 3},
            "higher_highs_days": {"type": "integer", "default": 5},

            # Sector
            "sector": {"type": ["string","null"],
                "description": "Sector filter. 'tech stocks' → 'Technology'"},

            # Meta
            "formula_name": {"type": "string",
                "description": "Short name for this indicator formula. Max 60 chars."},
            "plain_summary": {"type": "string",
                "description": "1 sentence confirming the parsed conditions."},
            "warnings": {"type": "array", "items": {"type": "string"},
                "description": "Parts of the query that couldn't be mapped."},
            "price_period": {"type": "string", "default": "1y",
                "description": "Price history period needed. '52-week' needs '1y'. Default '1y'."},
        },
        "required": ["formula_name", "plain_summary", "warnings"],
    },
}


# ─────────────────────────────────────────────────────────────
# Translation
# ─────────────────────────────────────────────────────────────

def translate_indicator(query: str) -> IndicatorFormula:
    """Translate plain-English indicator description into IndicatorFormula."""
    try:
        import anthropic
        key = (
            os.getenv("ANTHROPIC_API_KEY")
            or st.secrets.get("ANTHROPIC_API_KEY", "")
        )
        client = anthropic.Anthropic(api_key=key)
    except Exception as e:
        f = IndicatorFormula()
        f.warnings = [f"Anthropic unavailable: {e}"]
        return f

    system = (
        "You are a technical analysis expert translating investor queries into "
        "structured indicator conditions. Be precise with periods and lookback windows. "
        "Multiple conditions are ANDed — only include what the user explicitly stated. "
        "Call submit_indicator_formula with your result."
    )

    user_msg = (
        f"Parse this technical indicator description:\n\n\"{query}\"\n\n"
        f"Key mappings:\n"
        f"- 'RSI crossed above 30 in the last 3 days' → rsi_cross_above=30, rsi_cross_above_days=3\n"
        f"- 'price is above the 200-day MA' → price_above_sma=200\n"
        f"- 'golden cross' → sma_cross_above_fast=50, sma_cross_above_slow=200\n"
        f"- 'death cross' → sma_cross_below_fast=50, sma_cross_below_slow=200\n"
        f"- 'MACD bullish crossover' → macd_cross_above=true\n"
        f"- '2x average volume' → volume_spike=2.0\n"
        f"- 'Bollinger Band squeeze' → bb_squeeze=true\n"
        f"- '52-week high breakout' → high_52w_breakout=true\n"
        f"- 'oversold' → rsi_below=30\n"
        f"- 'overbought' → rsi_above=70\n"
        f"Multiple conditions in the same query are ALL included (ANDed).\n"
    )

    try:
        message = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=512,
            system=system,
            tools=[INDICATOR_TOOL],
            tool_choice={"type": "tool", "name": "submit_indicator_formula"},
            messages=[{"role": "user", "content": user_msg}],
        )
        for block in message.content:
            if block.type == "tool_use" and block.name == "submit_indicator_formula":
                return IndicatorFormula.from_dict(block.input)
    except Exception as e:
        f = IndicatorFormula()
        f.warnings = [f"Translation error: {e}"]
        return f

    return IndicatorFormula()


# ─────────────────────────────────────────────────────────────
# Formula evaluator — one symbol
# ─────────────────────────────────────────────────────────────

def evaluate_formula(
    symbol: str,
    formula: IndicatorFormula,
    df: pd.DataFrame,
    snap=None,
) -> tuple[bool, list[str], list[str]]:
    """
    Evaluate an IndicatorFormula against OHLCV data for one symbol.

    Returns:
        (matched: bool, passed_conditions: list[str], failed_conditions: list[str])
    """
    from modules.indicators.indicator_engine import (
        normalise,
        eval_rsi_cross_above, eval_rsi_cross_below,
        eval_price_above_sma, eval_price_below_sma,
        compute_sma, compute_ema, compute_rsi,
        eval_sma_cross_above, eval_macd_cross_above,
        eval_volume_spike, eval_bb_squeeze,
        eval_price_above_bb_upper, eval_52w_high_breakout,
        eval_higher_highs, crossover_below, crossed_within,
        compute_macd,
    )

    if df is None or df.empty:
        return False, [], ["No price data"]

    df = normalise(df)
    if len(df) < 20:
        return False, [], ["Insufficient data (<20 bars)"]

    passed, failed = [], []

    def _check(condition_set: bool, eval_fn, *args, **kwargs):
        if not condition_set:
            return
        ok, reason = eval_fn(*args, **kwargs)
        (passed if ok else failed).append(reason)

    # ── Sector filter ─────────────────────────────────────────
    if formula.sector and snap:
        sym_sector = getattr(snap, "sector", "") or ""
        if formula.sector.lower() not in sym_sector.lower():
            return False, [], [f"Sector '{sym_sector}' ≠ '{formula.sector}'"]

    # ── RSI crossovers ────────────────────────────────────────
    if formula.rsi_cross_above is not None:
        _check(True, eval_rsi_cross_above, df,
               formula.rsi_cross_above,
               formula.rsi_cross_above_period,
               formula.rsi_cross_above_days)

    if formula.rsi_cross_below is not None:
        _check(True, eval_rsi_cross_below, df,
               formula.rsi_cross_below,
               formula.rsi_cross_below_period,
               formula.rsi_cross_below_days)

    # ── RSI current level ─────────────────────────────────────
    if formula.rsi_above is not None or formula.rsi_below is not None:
        from modules.indicators.indicator_engine import compute_rsi
        rsi = compute_rsi(df["close"], 14)
        last_rsi = rsi.iloc[-1] if not rsi.empty else None
        if formula.rsi_above is not None:
            ok = last_rsi is not None and last_rsi > formula.rsi_above
            msg = f"RSI {last_rsi:.1f} {'>' if ok else '<='} {formula.rsi_above}"
            (passed if ok else failed).append(msg)
        if formula.rsi_below is not None:
            ok = last_rsi is not None and last_rsi < formula.rsi_below
            msg = f"RSI {last_rsi:.1f} {'<' if ok else '>='} {formula.rsi_below}"
            (passed if ok else failed).append(msg)

    # ── Price vs SMA / EMA ────────────────────────────────────
    if formula.price_above_sma is not None:
        _check(True, eval_price_above_sma, df, formula.price_above_sma)

    if formula.price_below_sma is not None:
        _check(True, eval_price_below_sma, df, formula.price_below_sma)

    if formula.price_above_ema is not None:
        ema = compute_ema(df["close"], formula.price_above_ema)
        last = df["close"].iloc[-1]
        ema_v = ema.iloc[-1]
        ok = last > ema_v if pd.notna(ema_v) else False
        msg = f"Price ${last:.2f} {'>' if ok else '<='} EMA{formula.price_above_ema} ${ema_v:.2f}"
        (passed if ok else failed).append(msg)

    if formula.price_below_ema is not None:
        ema = compute_ema(df["close"], formula.price_below_ema)
        last = df["close"].iloc[-1]
        ema_v = ema.iloc[-1]
        ok = last < ema_v if pd.notna(ema_v) else False
        msg = f"Price ${last:.2f} {'<' if ok else '>='} EMA{formula.price_below_ema} ${ema_v:.2f}"
        (passed if ok else failed).append(msg)

    # ── SMA crossovers ────────────────────────────────────────
    if formula.sma_cross_above_fast and formula.sma_cross_above_slow:
        _check(True, eval_sma_cross_above, df,
               formula.sma_cross_above_fast,
               formula.sma_cross_above_slow,
               formula.sma_cross_above_days)

    if formula.sma_cross_below_fast and formula.sma_cross_below_slow:
        fast = compute_sma(df["close"], formula.sma_cross_below_fast)
        slow = compute_sma(df["close"], formula.sma_cross_below_slow)
        cross = crossover_below(fast, slow)
        ok = crossed_within(cross, formula.sma_cross_below_days)
        msg = (
            f"SMA{formula.sma_cross_below_fast} crossed below SMA{formula.sma_cross_below_slow} "
            f"in last {formula.sma_cross_below_days}d"
            if ok else
            f"No death cross SMA{formula.sma_cross_below_fast}/{formula.sma_cross_below_slow}"
        )
        (passed if ok else failed).append(msg)

    # ── MACD ──────────────────────────────────────────────────
    if formula.macd_cross_above:
        _check(True, eval_macd_cross_above, df, formula.macd_cross_above_days)

    if formula.macd_cross_below:
        macd = compute_macd(df["close"])
        cross = crossover_below(macd["macd"], macd["macd_signal"])
        ok = crossed_within(cross, formula.macd_cross_below_days)
        msg = (f"MACD crossed below signal in last {formula.macd_cross_below_days}d"
               if ok else f"No MACD bearish cross in last {formula.macd_cross_below_days}d")
        (passed if ok else failed).append(msg)

    if formula.macd_positive:
        macd = compute_macd(df["close"])
        hist_val = macd["macd_hist"].iloc[-1]
        ok = hist_val > 0 if pd.notna(hist_val) else False
        msg = f"MACD histogram {hist_val:.3f} {'> 0 ✓' if ok else '<= 0 ✗'}"
        (passed if ok else failed).append(msg)

    # ── Bollinger ─────────────────────────────────────────────
    if formula.bb_squeeze:
        _check(True, eval_bb_squeeze, df, formula.bb_squeeze_threshold)

    if formula.price_above_bb_upper:
        _check(True, eval_price_above_bb_upper, df)

    if formula.price_below_bb_lower:
        from modules.indicators.indicator_engine import compute_bollinger
        bb = compute_bollinger(df["close"])
        last = df["close"].iloc[-1]
        lb = bb["bb_lower"].iloc[-1]
        ok = last < lb if pd.notna(lb) else False
        msg = f"Price ${last:.2f} {'below' if ok else 'above'} BB lower ${lb:.2f}"
        (passed if ok else failed).append(msg)

    # ── Volume ────────────────────────────────────────────────
    if formula.volume_spike is not None:
        _check(True, eval_volume_spike, df,
               formula.volume_spike,
               formula.volume_spike_period)

    # ── 52-week ───────────────────────────────────────────────
    if formula.high_52w_breakout:
        _check(True, eval_52w_high_breakout, df, formula.high_52w_breakout_days)

    if formula.low_52w_breakdown:
        closes = df["close"]
        low_252 = closes.rolling(252, min_periods=50).min()
        new_low = closes <= low_252
        ok = bool(new_low.tail(formula.low_52w_breakdown_days).any())
        last = closes.iloc[-1]
        l52 = low_252.iloc[-1]
        msg = (f"New 52w low ${last:.2f} in last {formula.low_52w_breakdown_days}d"
               if ok else f"No 52w breakdown (current ${last:.2f}, 52w low ${l52:.2f})")
        (passed if ok else failed).append(msg)

    # ── Higher highs ──────────────────────────────────────────
    if formula.higher_highs:
        _check(True, eval_higher_highs, df,
               formula.higher_highs_days,
               formula.higher_highs_count)

    # ── Result: ALL conditions must pass ──────────────────────
    matched = len(passed) > 0 and len(failed) == 0
    return matched, passed, failed


# ─────────────────────────────────────────────────────────────
# Universe scan
# ─────────────────────────────────────────────────────────────

def scan_universe(
    formula: IndicatorFormula,
    symbols: list[str],
    db,
    tenant_id: str,
    progress_callback=None,
) -> list[dict]:
    """
    Run IndicatorFormula across all symbols.
    Returns list of matched result dicts sorted by number of passed conditions.
    """
    from modules.market_data.service import get_price_history
    from modules.analytics.models import AnalyticsSnapshot

    # Load snapshots for sector filtering and enrichment
    snaps = {}
    try:
        rows = (
            db.query(AnalyticsSnapshot)
            .filter(AnalyticsSnapshot.tenant_id == tenant_id)
            .order_by(AnalyticsSnapshot.asof.desc())
            .all()
        )
        seen = set()
        for r in rows:
            if r.symbol not in seen:
                seen.add(r.symbol)
                snaps[r.symbol] = r
    except Exception:
        pass

    results = []
    n = len(symbols)

    for i, sym in enumerate(symbols):
        if progress_callback:
            progress_callback(i / n, sym)

        # Sector pre-filter (fast — no price fetch needed)
        snap = snaps.get(sym)
        if formula.sector and snap:
            sym_sector = getattr(snap, "sector", "") or ""
            if formula.sector.lower() not in sym_sector.lower():
                continue

        try:
            db.rollback()
        except Exception:
            pass

        try:
            df = get_price_history(
                db, sym,
                period=formula.price_period,
                interval="1d",
            )
        except Exception:
            df = None

        try:
            matched, passed, failed = evaluate_formula(sym, formula, df, snap)
        except Exception as e:
            continue

        if not matched:
            continue

        # Enrich with snapshot data
        last_px = None
        if df is not None and not df.empty and "Close" in df.columns:
            last_px = round(float(df["Close"].iloc[-1]), 2)

        results.append({
            "symbol":     sym,
            "price":      last_px,
            "sector":     getattr(snap, "sector", "Unknown") if snap else "Unknown",
            "rating":     getattr(snap, "rating", "N/A") if snap else "N/A",
            "composite":  round(float(getattr(snap, "composite_score", 0) or 0), 1) if snap else None,
            "momentum":   round(float(getattr(snap, "momentum_score", 0) or 0), 1) if snap else None,
            "rsi_14":     round(float(getattr(snap, "rsi_14", 0) or 0), 1) if snap else None,
            "conditions_met": len(passed),
            "conditions": " · ".join(passed),
        })

    return sorted(results, key=lambda x: x["conditions_met"], reverse=True)