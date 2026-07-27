"""
modules/smc/smc_chart.py

Renders the Smart Money Concepts chart overlay using matplotlib.
Two-panel layout:
  - Top panel  : OHLCV candlestick + OB zones + FVG bands + BOS/CHoCH + swings
  - Bottom panel: Momentum oscillator with signal line + zero band
"""

from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
import numpy as np
import pandas as pd

from modules.smc.smc_engine import SMCResult


# ─────────────────────────────────────────────────────────────
# Colour palette (dark institutional theme)
# ─────────────────────────────────────────────────────────────
C = {
    "bg":          "#0F1117",
    "panel_bg":    "#161B22",
    "grid":        "#21262D",
    "text":        "#C9D1D9",
    "subtext":     "#8B949E",
    "bull_candle": "#1D9E75",
    "bear_candle": "#E24B4A",
    "bull_ob":     "#1D9E75",
    "bear_ob":     "#E24B4A",
    "bull_fvg":    "#378ADD",
    "bear_fvg":    "#BA7517",
    "bos_bull":    "#1D9E75",
    "bos_bear":    "#E24B4A",
    "choch_bull":  "#FFD700",
    "choch_bear":  "#FF8C00",
    "swing_hi":    "#E24B4A",
    "swing_lo":    "#1D9E75",
    "mom_pos":     "#1D9E75",
    "mom_neg":     "#E24B4A",
    "signal":      "#FFD700",
    "divider":     "#30363D",
}


def render_smc_chart(
    df: pd.DataFrame,
    result: SMCResult,
    symbol: str = "",
    figsize: tuple = (14, 8),
) -> plt.Figure:
    """
    Render the full SMC chart.
    Returns a matplotlib Figure ready for st.pyplot().
    """
    df = _prep_df(df)
    n  = len(df)
    xs = np.arange(n)

    fig = plt.figure(figsize=figsize, facecolor=C["bg"])
    gs  = fig.add_gridspec(4, 1, hspace=0.04, height_ratios=[3, 0, 1, 0])
    ax_price = fig.add_subplot(gs[0])
    ax_mom   = fig.add_subplot(gs[2], sharex=ax_price)

    for ax in (ax_price, ax_mom):
        ax.set_facecolor(C["panel_bg"])
        ax.tick_params(colors=C["subtext"], labelsize=8)
        ax.spines[:].set_color(C["divider"])
        ax.grid(True, color=C["grid"], linewidth=0.4, alpha=0.6)
        ax.yaxis.tick_right()
        ax.yaxis.set_label_position("right")

    # ── Candlesticks ──────────────────────────────────────────
    _draw_candles(ax_price, df, xs)

    # ── Order Blocks ──────────────────────────────────────────
    _draw_order_blocks(ax_price, result.order_blocks, n)

    # ── Fair Value Gaps ───────────────────────────────────────
    _draw_fvgs(ax_price, result.fvgs, n)

    # ── Swing points ──────────────────────────────────────────
    _draw_swings(ax_price, result.swing_highs, result.swing_lows)

    # ── Structure (BOS / CHoCH) ───────────────────────────────
    _draw_structure(ax_price, result.structure)

    # ── Momentum panel ────────────────────────────────────────
    _draw_momentum(ax_mom, result.momentum, result.momentum_signal, xs)

    # ── Labels ────────────────────────────────────────────────
    trend_color = C["bull_candle"] if result.trend == "Bullish" else \
                  C["bear_candle"] if result.trend == "Bearish" else C["subtext"]

    ax_price.set_title(
        f"{symbol}  ·  Smart Money Concepts  ·  Trend: {result.trend}",
        color=C["text"], fontsize=12, pad=8, loc="left"
    )
    ax_price.set_ylabel("Price", color=C["subtext"], fontsize=9)
    ax_mom.set_ylabel("Momentum", color=C["subtext"], fontsize=9)

    # X-axis labels on bottom panel only
    if "date" in df.columns:
        tick_step = max(1, n // 10)
        tick_xs   = xs[::tick_step]
        tick_lbls = [str(df["date"].iloc[i])[:10] for i in tick_xs]
        ax_mom.set_xticks(tick_xs)
        ax_mom.set_xticklabels(tick_lbls, rotation=30, ha="right", fontsize=7)
    plt.setp(ax_price.get_xticklabels(), visible=False)

    # Legend
    legend_patches = [
        mpatches.Patch(color=C["bull_ob"],   alpha=0.4, label="Bullish OB"),
        mpatches.Patch(color=C["bear_ob"],   alpha=0.4, label="Bearish OB"),
        mpatches.Patch(color=C["bull_fvg"],  alpha=0.3, label="Bullish FVG"),
        mpatches.Patch(color=C["bear_fvg"],  alpha=0.3, label="Bearish FVG"),
        mpatches.Patch(color=C["bos_bull"],  label="BOS ↑"),
        mpatches.Patch(color=C["bos_bear"],  label="BOS ↓"),
        mpatches.Patch(color=C["choch_bull"], label="CHoCH"),
    ]
    ax_price.legend(
        handles=legend_patches, loc="upper left",
        fontsize=7, framealpha=0.3,
        facecolor=C["panel_bg"], edgecolor=C["divider"],
        labelcolor=C["text"]
    )

    plt.tight_layout()
    return fig


# ─────────────────────────────────────────────────────────────
# Drawing helpers
# ─────────────────────────────────────────────────────────────

def _draw_candles(ax, df, xs):
    for i, (_, row) in enumerate(df.iterrows()):
        o, h, l, c = row["open"], row["high"], row["low"], row["close"]
        color = C["bull_candle"] if c >= o else C["bear_candle"]
        # Wick
        ax.plot([xs[i], xs[i]], [l, h], color=color, linewidth=0.8, alpha=0.7)
        # Body
        body_lo = min(o, c)
        body_hi = max(o, c)
        height  = max(body_hi - body_lo, (h - l) * 0.01)
        rect = mpatches.FancyBboxPatch(
            (xs[i] - 0.3, body_lo), 0.6, height,
            boxstyle="square,pad=0", linewidth=0,
            facecolor=color, alpha=0.85
        )
        ax.add_patch(rect)


def _draw_order_blocks(ax, obs, n_bars):
    for ob in obs:
        color = C["bull_ob"] if ob.kind == "bullish" else C["bear_ob"]
        alpha = 0.18 + ob.strength * 0.12
        # Draw from ob.index to current bar
        x_start = ob.index
        width   = n_bars - x_start
        rect = mpatches.Rectangle(
            (x_start, ob.bottom), width, ob.top - ob.bottom,
            linewidth=0.8, edgecolor=color, facecolor=color, alpha=alpha
        )
        ax.add_patch(rect)
        # Label
        ax.text(
            x_start + 0.5, ob.top, f"{'Bull' if ob.kind == 'bullish' else 'Bear'} OB",
            color=color, fontsize=6.5, va="bottom", alpha=0.9
        )


def _draw_fvgs(ax, fvgs, n_bars):
    for fvg in fvgs:
        color = C["bull_fvg"] if fvg.kind == "bullish" else C["bear_fvg"]
        x_start = fvg.index
        width   = n_bars - x_start
        rect = mpatches.Rectangle(
            (x_start, fvg.bottom), width, fvg.top - fvg.bottom,
            linewidth=0.6, edgecolor=color, facecolor=color, alpha=0.15,
            linestyle="--"
        )
        ax.add_patch(rect)
        ax.text(
            x_start + 0.5, (fvg.top + fvg.bottom) / 2,
            "FVG", color=color, fontsize=6, va="center", alpha=0.8
        )


def _draw_swings(ax, swing_highs, swing_lows):
    for idx, price in swing_highs[-12:]:
        ax.plot(idx, price, "v", color=C["swing_hi"], markersize=5, alpha=0.8)
        ax.text(idx, price * 1.002, f"{price:.1f}",
                color=C["swing_hi"], fontsize=6, ha="center", va="bottom", alpha=0.7)

    for idx, price in swing_lows[-12:]:
        ax.plot(idx, price, "^", color=C["swing_lo"], markersize=5, alpha=0.8)
        ax.text(idx, price * 0.998, f"{price:.1f}",
                color=C["swing_lo"], fontsize=6, ha="center", va="top", alpha=0.7)


def _draw_structure(ax, structure):
    kind_cfg = {
        "BOS_bull":  (C["bos_bull"],  "BOS ↑",   False),
        "BOS_bear":  (C["bos_bear"],  "BOS ↓",   False),
        "CHoCH_bull":(C["choch_bull"],"CHoCH ↑", True),
        "CHoCH_bear":(C["choch_bear"],"CHoCH ↓", True),
    }
    for pt in structure[-8:]:
        color, label, is_choch = kind_cfg.get(pt.kind, (C["subtext"], pt.kind, False))
        ls = "--" if is_choch else "-"
        ax.axhline(pt.price, color=color, linewidth=0.8, linestyle=ls, alpha=0.5,
                   xmin=pt.index / max(1, pt.index + 10))
        ax.axvline(pt.index, color=color, linewidth=0.5, linestyle=":", alpha=0.3)
        ax.text(
            pt.index, pt.price, f" {label}",
            color=color, fontsize=6.5, va="center",
            path_effects=[pe.withStroke(linewidth=1.5, foreground=C["panel_bg"])]
        )


def _draw_momentum(ax, momentum, signal, xs):
    if not momentum:
        return
    mom = np.array(momentum)
    sig = np.array(signal)
    n   = min(len(mom), len(xs))
    mom, sig, xs_n = mom[-n:], sig[-n:], xs[-n:]

    # Positive / negative fills
    ax.fill_between(xs_n, mom, 0, where=(mom >= 0),
                    color=C["mom_pos"], alpha=0.4, interpolate=True)
    ax.fill_between(xs_n, mom, 0, where=(mom < 0),
                    color=C["mom_neg"], alpha=0.4, interpolate=True)
    ax.plot(xs_n, sig, color=C["signal"], linewidth=1.2, label="Signal")
    ax.axhline(0, color=C["divider"], linewidth=0.8)
    ax.axhline( 0.6, color=C["mom_neg"], linewidth=0.4, linestyle="--", alpha=0.4)
    ax.axhline(-0.6, color=C["mom_pos"], linewidth=0.4, linestyle="--", alpha=0.4)
    ax.set_ylim(-1.1, 1.1)


# ─────────────────────────────────────────────────────────────
# DataFrame prep
# ─────────────────────────────────────────────────────────────

def _prep_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    rename = {}
    for col in df.columns:
        lc = col.lower()
        if lc in ("open","high","low","close","volume","date"):
            rename[col] = lc
    df = df.rename(columns=rename)
    for col in ("open","high","low","close"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    # Ensure open column exists
    if "open" not in df.columns and "close" in df.columns:
        df["open"] = df["close"].shift(1).fillna(df["close"])
    if "high" not in df.columns:
        df["high"] = df["close"]
    if "low" not in df.columns:
        df["low"] = df["close"]
    return df.dropna(subset=["close"]).reset_index(drop=True)
