from sqlalchemy.orm import Session
import pandas as pd
import requests
import streamlit as st
from datetime import datetime, UTC
from modules.analytics.models import AnalyticsSnapshot


# ---------------------------------------------------
# SAFE FLOAT
# ---------------------------------------------------

def _to_float(x):
    try:
        if x in (None, "", "NA", "N/A"):
            return None
        return float(x)
    except Exception:
        return None


# ---------------------------------------------------
# PRICE FETCH (EODHD ONLY)
# ---------------------------------------------------

# ---------------------------------------------------
# PRICE FETCH (PROVIDER AGNOSTIC)
# ---------------------------------------------------

def _get_prices_many(
    db: Session,
    symbols: list[str],
):

    from modules.market_data.price_cache import (
        get_price,
    )

    out = {}

    symbols = [
        str(s).upper().strip()
        for s in symbols
        if s
    ]

    total = len(symbols)

    progress = st.progress(0)

    for i, sym in enumerate(symbols):

        try:

            progress.progress((i + 1) / total)

            df = get_price(sym, db)

            if (
                isinstance(df, pd.DataFrame)
                and not df.empty
            ):
                out[sym] = df

        except Exception as e:

            print(
                "SCREENER PRICE ERROR",
                sym,
                e,
            )

    st.write("✅ PRICE COUNT:", len(out))

    return out


# ---------------------------------------------------
# HELPERS
# ---------------------------------------------------

def _safe_float(x):
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def _latest_snapshots(db: Session, tenant_id: str):
    rows = (
        db.query(AnalyticsSnapshot)
        .filter(AnalyticsSnapshot.tenant_id == tenant_id)
        .order_by(AnalyticsSnapshot.symbol.asc(), AnalyticsSnapshot.asof.desc())
        .all()
    )

    latest = {}
    for row in rows:
        if row.symbol not in latest:
            latest[row.symbol] = row

    st.write("✅ SNAPSHOT COUNT:", len(latest))
    return latest


# ---------------------------------------------------
# MAIN SCREENER
# ---------------------------------------------------

def run_screener(
    db: Session,
    tenant_id: str,
    symbols: list[str],
    min_price: float | None = None,
    min_volume: float | None = None,
    min_composite: float | None = None,
    min_confidence: float | None = None,
    min_quality: float | None = None,
    min_growth: float | None = None,
    min_value: float | None = None,
    min_momentum: float | None = None,
    max_risk: float | None = None,
    sector: str | None = None,
    rating_in: list[str] | None = None,
    limit: int = 250,
):

    if not symbols:
        return []

    symbols = [str(s).upper().strip() for s in symbols if s]

    st.warning("🚀 Screener started...")

    # ---------------- PRICE ----------------
    price_data = _get_prices_many(
        db,
        symbols,
    )

    # ---------------- SNAPSHOTS ----------------
    snap_map = _latest_snapshots(db, tenant_id)

    # ---------------- NORMALIZE ----------------
    def normalize(sym):
        return str(sym).upper().replace(".US", "").strip()

    snap_map_norm = {
        normalize(k): v for k, v in snap_map.items()
    }

    price_data_norm = {
        normalize(k): v for k, v in price_data.items()
    }

    # ---------------- DEBUG COUNTERS ----------------
    fail_df = 0
    fail_snap = 0
    fail_price = 0
    pass_all = 0

    results = []

    for symbol in symbols:
        df = price_data_norm.get(normalize(symbol))
        snap = snap_map_norm.get(normalize(symbol))

        if not isinstance(df, pd.DataFrame) or df.empty:
            fail_df += 1
            continue

        if snap is None:
            fail_snap += 1
            continue

        last = df.iloc[-1]

        price = _safe_float(last.get("Close"))
        volume = _safe_float(last.get("Volume"))

        # 🔥 FIX: ONLY require price
        if price is None:
            fail_price += 1
            continue

        if volume is None:
            volume = 0

        composite = _safe_float(snap.composite_score)
        confidence = _safe_float(snap.confidence_score)
        quality = _safe_float(snap.quality_score)
        growth = _safe_float(snap.growth_score)
        value = _safe_float(snap.value_score)
        momentum = _safe_float(snap.momentum_score)
        risk = _safe_float(snap.risk_score)

        # ---------------- FILTERS ----------------

        if min_price is not None and price < min_price:
            continue

        if min_volume is not None and volume < min_volume:
            continue

        if min_composite is not None and (composite is None or composite < min_composite):
            continue

        if min_confidence is not None and (confidence is None or confidence < min_confidence):
            continue

        if min_quality is not None and (quality is None or quality < min_quality):
            continue

        if min_growth is not None and (growth is None or growth < min_growth):
            continue

        if min_value is not None and (value is None or value < min_value):
            continue

        if min_momentum is not None and (momentum is None or momentum < min_momentum):
            continue

        if max_risk is not None and (risk is None or risk > max_risk):
            continue

        if sector is not None and (snap.sector or "").strip() != sector:
            continue

        if rating_in and snap.rating not in rating_in:
            continue

        pass_all += 1

        results.append({
            "symbol": symbol,
            "price": price,
            "volume": volume,
            "sector": snap.sector or "Unknown",
            "rating": snap.rating or "N/A",
            "composite": composite,
            "confidence": confidence,
            "quality": quality,
            "growth": growth,
            "value": value,
            "momentum": momentum,
            "risk": risk,
            "trend": snap.trend,
            "rsi_14": _safe_float(snap.rsi_14),
            "support": _safe_float(snap.support),
            "resistance": _safe_float(snap.resistance),
            "pe_ttm": _safe_float(snap.pe_ttm),
            "ps_ttm": _safe_float(snap.ps_ttm),
            "ev_ebitda": _safe_float(snap.ev_ebitda),
        })

    # ---------------- DEBUG OUTPUT ----------------
    st.write("FAIL DF:", fail_df)
    st.write("FAIL SNAP:", fail_snap)
    st.write("FAIL PRICE:", fail_price)
    st.write("PASS ALL:", pass_all)

    results.sort(
        key=lambda x: (
            x["composite"] if x["composite"] is not None else -9999,
            x["confidence"] if x["confidence"] is not None else -9999,
        ),
        reverse=True,
    )

    st.write("✅ FINAL RESULTS:", len(results))

    return results[:limit]