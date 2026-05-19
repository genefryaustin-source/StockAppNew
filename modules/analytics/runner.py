import pandas as pd
import numpy as np
import requests
import streamlit as st
from datetime import datetime
import time

from modules.analytics.models import AnalyticsSnapshot
from modules.utils.config import get_secret
from modules.market_data.service import get_latest_price_map
# ---------------------------------------------------
# CONFIG
# ---------------------------------------------------

EOD_REALTIME = "https://eodhd.com/api/real-time/stock"
EOD_EOD = "https://eodhd.com/api/eod"

_fund_cache = {}

# ---------------------------------------------------
# HELPERS
# ---------------------------------------------------

def _to_float(x):
    try:
        if x in (None, "", "NA", "N/A", "-", "--"):
            return None
        return float(x)
    except:
        return None


def _normalize(sym):
    return str(sym).upper().replace(".US", "").strip()


def _sym(symbol):
    s = _normalize(symbol)
    return f"{s}.US"


def _base_symbol(symbol):
    return _normalize(symbol)


def _normalize_percent(x):
    x = _to_float(x)
    if x is None:
        return None
    return x if x > 1 else x * 100

def _clip_score(x, lo=0.0, hi=100.0):
    if x is None:
        return None
    return float(max(lo, min(hi, x)))


def _score_percent(value, floor=0.0, cap=100.0):
    v = _to_float(value)
    if v is None:
        return None
    return _clip_score(v, floor, cap)


def _score_growth_pct(growth_pct):
    g = _to_float(growth_pct)
    if g is None:
        return 50.0
    if g <= -20:
        return 5.0
    if g <= -10:
        return 15.0
    if g <= 0:
        return 35.0
    if g <= 5:
        return 50.0
    if g <= 10:
        return 65.0
    if g <= 15:
        return 75.0
    if g <= 25:
        return 85.0
    return 95.0


def _score_inverse_metric(v, bands):
    """
    Lower is better.
    bands = [(upper_bound, score), ...]
    """
    x = _to_float(v)
    if x is None:
        return None
    for upper, score in bands:
        if x <= upper:
            return float(score)
    return float(bands[-1][1])


def _score_value(pe_ttm=None, ps_ttm=None, ev_ebitda=None):
    pe_score = _score_inverse_metric(pe_ttm, [
        (10, 95), (15, 85), (20, 75), (25, 65),
        (30, 55), (40, 40), (60, 25), (999999, 10)
    ])
    ps_score = _score_inverse_metric(ps_ttm, [
        (2, 95), (4, 85), (6, 75), (8, 65),
        (10, 55), (15, 40), (25, 25), (999999, 10)
    ])
    ev_score = _score_inverse_metric(ev_ebitda, [
        (8, 95), (12, 85), (16, 75), (20, 65),
        (25, 55), (35, 40), (50, 25), (999999, 10)
    ])

    vals = [x for x in [pe_score, ps_score, ev_score] if x is not None]
    if not vals:
        return 50.0
    return float(sum(vals) / len(vals))


def _score_quality(gross_margin=None, operating_margin=None):
    gm = _score_percent(gross_margin)
    om = _score_percent(operating_margin)

    if gm is None and om is None:
        return 50.0
    if gm is None:
        return om
    if om is None:
        return gm

    return float((gm * 0.6) + (om * 0.4))


def _score_momentum(rsi, trend):
    r = _to_float(rsi)
    if r is None:
        base = 50.0
    elif r < 20:
        base = 20.0
    elif r < 30:
        base = 35.0
    elif r < 40:
        base = 50.0
    elif r < 55:
        base = 65.0
    elif r < 70:
        base = 80.0
    elif r < 80:
        base = 65.0
    else:
        base = 45.0

    if trend == "Uptrend":
        base += 10
    elif trend == "Downtrend":
        base -= 10

    return _clip_score(base)


def _score_risk(vol20, max_dd):
    vol = _to_float(vol20)
    dd = _to_float(max_dd)

    vol_penalty = 0.0
    dd_penalty = 0.0

    if vol is not None:
        # vol is decimal annualized, e.g. 0.20 = 20%
        if vol <= 0.15:
            vol_penalty = 10
        elif vol <= 0.25:
            vol_penalty = 25
        elif vol <= 0.35:
            vol_penalty = 45
        elif vol <= 0.50:
            vol_penalty = 65
        else:
            vol_penalty = 80

    if dd is not None:
        # max drawdown usually negative
        d = abs(dd)
        if d <= 0.10:
            dd_penalty = 10
        elif d <= 0.20:
            dd_penalty = 25
        elif d <= 0.35:
            dd_penalty = 45
        elif d <= 0.50:
            dd_penalty = 65
        else:
            dd_penalty = 85

    penalty = max(vol_penalty, dd_penalty)
    return _clip_score(100 - penalty)


def _score_confidence(fundamentals, sma50, sma200, vol20, max_dd):
    score = 70.0

    if fundamentals.get("gross_margin") is not None:
        score += 5
    if fundamentals.get("operating_margin") is not None:
        score += 5
    if fundamentals.get("revenue_cagr") is not None:
        score += 5
    if fundamentals.get("fcf_margin") is not None:
        score += 5
    if sma50 is not None:
        score += 3
    if sma200 is not None:
        score += 3
    if vol20 is not None:
        score += 2
    if max_dd is not None:
        score += 2

    return _clip_score(score)


def _composite_weighted(quality, growth, value, momentum):
    weights = {
        "quality": 0.30,
        "growth": 0.20,
        "value": 0.25,
        "momentum": 0.25,
    }

    parts = []
    total_w = 0.0

    for name, val in [
        ("quality", quality),
        ("growth", growth),
        ("value", value),
        ("momentum", momentum),
    ]:
        if val is not None:
            parts.append(val * weights[name])
            total_w += weights[name]

    if total_w == 0:
        return None

    return float(sum(parts) / total_w)

def _normalize_sector(s):
    if not s:
        return "Unknown"

    s = str(s).upper().strip()

    mapping = {
        "TECHNOLOGY": "Technology",
        "INFORMATION TECHNOLOGY": "Technology",
        "ELECTRONIC COMPUTERS": "Technology",

        "FINANCIAL SERVICES": "Financials",
        "BANKS": "Financials",

        "HEALTHCARE": "Healthcare",
        "BIOTECH": "Healthcare",

        "CONSUMER CYCLICAL": "Consumer",
        "RETAIL": "Consumer",

        "ENERGY": "Energy",
        "UTILITIES": "Utilities",
        "INDUSTRIALS": "Industrials",
        "MATERIALS": "Materials",
        "REAL ESTATE": "Real Estate",
    }

    for k, v in mapping.items():
        if k in s:
            return v

    return s.title()


# ---------------------------------------------------
# PRICE FETCH (REALTIME)
# ---------------------------------------------------

def _get_prices_many(symbols):

    key = get_secret("EODHD_API_KEY")
    if not key:
        return {}

    out = {}
    BATCH_SIZE = 50

    for i in range(0, len(symbols), BATCH_SIZE):
        batch = symbols[i:i + BATCH_SIZE]

        try:
            r = requests.get(
                EOD_REALTIME,
                params={
                    "api_token": key,
                    "fmt": "json",
                    "s": ",".join(batch)
                },
                timeout=6
            )

            data = r.json()

            if not isinstance(data, list):
                continue

            for row in data:
                sym = row.get("code")
                price = _to_float(row.get("close"))

                if sym and price is not None:
                    base = sym.upper().replace(".US", "")
                    out[base] = price
                    out[f"{base}.US"] = price

        except Exception as e:
            print("PRICE FETCH ERROR:", e)

    return out


# ---------------------------------------------------
# LATEST BAR (FOR VOLUME)
# ---------------------------------------------------

def _get_latest_bar(symbol):
    key = get_secret("EODHD_API_KEY")

    try:
        r = requests.get(
            f"{EOD_EOD}/{_sym(symbol)}",
            params={"api_token": key, "fmt": "json", "limit": 1},
            timeout=6
        )

        data = r.json()

        if isinstance(data, list) and data:
            return data[-1]

    except Exception as e:
        print("LATEST BAR ERROR:", symbol, e)

    return {}


# ---------------------------------------------------
# PRICE SERIES (TECHNICALS)
# ---------------------------------------------------

def _get_price_series(symbol):

    key = get_secret("EODHD_API_KEY")

    try:
        r = requests.get(
            f"{EOD_EOD}/{_sym(symbol)}",
            params={
                "api_token": key,
                "fmt": "json",
                "limit": 250
            },
            timeout=6
        )

        data = r.json()

        if isinstance(data, list) and len(data) > 0:
            closes = [row["close"] for row in data if row.get("close") is not None]
            volumes = [row.get("volume", 0) for row in data]

            return pd.DataFrame({
                "close": closes,
                "volume": volumes[:len(closes)]
            })

    except Exception as e:
        print("SERIES ERROR:", symbol, e)

    return None


# ---------------------------------------------------
# RSI
# ---------------------------------------------------

def _compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


_profile_cache = {}

def _get_fundamentals(symbol):

    sym = _normalize(symbol)

    if sym in _fund_cache:
        return _fund_cache[sym]

    key = get_secret("FINNHUB_API_KEY")
    if not key:
        return {}

    try:
        # --------------------------------------------------
        # 1. METRICS (PRIMARY)
        # --------------------------------------------------
        r = requests.get(
            "https://finnhub.io/api/v1/stock/metric",
            params={"symbol": sym, "metric": "all", "token": key},
            timeout=6
        )

        data = r.json()
        m = data.get("metric", {})

        if not m:
            return {}

        # --------------------------------------------------
        # 2. SECTOR (PROFILE ENDPOINT - CORRECT SOURCE)
        # --------------------------------------------------
        sector = None

        if sym in _profile_cache:
            sector = _profile_cache[sym]
        else:
            try:
                prof = requests.get(
                    "https://finnhub.io/api/v1/stock/profile2",
                    params={"symbol": sym, "token": key},
                    timeout=5
                ).json()

                sector = prof.get("finnhubIndustry")

                print("✅ FINNHUB PROFILE SECTOR:", sym, sector)

                _profile_cache[sym] = sector

            except Exception as e:
                print("PROFILE ERROR:", sym, e)

        # --------------------------------------------------
        # 3. BASE FUNDAMENTALS
        # --------------------------------------------------
        result = {
            "revenue_cagr": _to_float(m.get("revenueGrowthTTMYoy")),
            "gross_margin": _normalize_percent(m.get("grossMarginTTM")),
            "operating_margin": _normalize_percent(m.get("operatingMarginTTM")),
            "pe_ttm": _to_float(m.get("peTTM")),
            "ps_ttm": _to_float(m.get("psTTM")),
            "ev_ebitda": _to_float(m.get("evEbitdaTTM")),
            "fcf_margin": None,
            "sector": sector,  # 🔥 FIXED
        }

        print("✅ FINNHUB FUNDAMENTALS USED:", sym)

        # --------------------------------------------------
        # 4. FCF CALCULATION (UNCHANGED)
        # --------------------------------------------------
        fcf_ps = _to_float(
            m.get("cashFlowPerShareTTM")
            or m.get("freeCashFlowPerShareTTM")
        )

        rev_ps = _to_float(m.get("revenuePerShareTTM"))

        print("DEBUG FCF INPUT:", sym, fcf_ps, rev_ps)

        if fcf_ps and rev_ps:
            result["fcf_margin"] = (fcf_ps / rev_ps) * 100
            print("✅ FCF CALCULATED:", sym, result["fcf_margin"])
        else:
            print("⚠️ FCF STILL MISSING:", sym)

        # --------------------------------------------------
        # 5. CACHE + RETURN
        # --------------------------------------------------
        _fund_cache[sym] = result
        return result

    except Exception as e:
        print("FINNHUB ERROR:", sym, e)
        return {}

# ---------------------------------------------------
# FACTORS
# ---------------------------------------------------

def _compute_factors(price, fundamentals, rsi):

    quality = fundamentals.get("gross_margin") or 0
    growth = fundamentals.get("revenue_cagr") or 0
    value = max(0, 100 - (fundamentals.get("pe_ttm") or 50))
    momentum = _to_float(rsi) or 50
    risk = max(0, 100 - momentum)

    return quality, growth, value, momentum, risk


# ---------------------------------------------------
# MAIN ANALYTICS
# ---------------------------------------------------
def check_for_alerts(symbol, signal, composite, sentiment):
    alerts = []

    # -----------------------------
    # SIGNAL ALERTS
    # -----------------------------
    if signal in ["Buy", "Strong Buy"]:
        alerts.append(f"🚀 {symbol} BUY signal")

    elif signal in ["Sell", "Strong Sell"]:
        alerts.append(f"⚠️ {symbol} SELL signal")

    # -----------------------------
    # SENTIMENT ALERTS
    # -----------------------------
    if sentiment is not None:
        if sentiment > 0.1:
            alerts.append(f"📰 {symbol} positive news sentiment")

        elif sentiment < -0.1:
            alerts.append(f"📰 {symbol} negative news sentiment")

    # -----------------------------
    # COMPOSITE ALERTS (FIXED)
    # -----------------------------
    if composite and composite >= 65:
        alerts.append(f"🔥 {symbol} strong composite score ({round(composite, 1)})")

    elif composite and composite <= 30:
        alerts.append(f"❄️ {symbol} weak composite score ({round(composite, 1)})")

    return alerts

def run_analytics_for_symbol(db, tenant_id, symbol):

    sym = _normalize(symbol)

    # -------- PRICE --------
    price_map = _get_prices_many([sym, f"{sym}.US"])

    price = (
        price_map.get(sym) or
        price_map.get(f"{sym}.US")
    )

    if price is None:
        print("NO PRICE:", sym, price_map)
        return None

    # -------- SERIES --------
    df = _get_price_series(sym)

    if df is None or len(df) < 50:
        return None

    closes = df["close"]
    volumes = df["volume"]

    # -------- TECH --------
    rsi = _compute_rsi(closes).iloc[-1]

    sma50 = closes.rolling(50).mean().iloc[-1] if len(closes) >= 50 else None
    sma200 = closes.rolling(200).mean().iloc[-1] if len(closes) >= 200 else None

    returns = closes.pct_change().dropna()

    vol20 = returns.tail(20).std() * np.sqrt(252) if len(returns) >= 20 else None
    max_dd = ((closes - closes.cummax()) / closes.cummax()).min()

    support = closes.tail(20).min()
    resistance = closes.tail(20).max()

    # -------- TREND --------
    trend = "Range"
    if sma50 and sma200:
        if price > sma50 > sma200:
            trend = "Uptrend"
        elif price < sma50 < sma200:
            trend = "Downtrend"

    # -------- VOLUME --------
    latest_bar = _get_latest_bar(sym)
    latest_volume = _to_float(latest_bar.get("volume"))

    # -------- FUNDAMENTALS --------
    fundamentals = _get_fundamentals(sym)

    gross_margin = _to_float(fundamentals.get("gross_margin"))
    operating_margin = _to_float(fundamentals.get("operating_margin"))
    revenue_cagr = _to_float(fundamentals.get("revenue_cagr"))
    fcf_margin = _to_float(fundamentals.get("fcf_margin"))

    pe = _to_float(fundamentals.get("pe_ttm"))
    ps = _to_float(fundamentals.get("ps_ttm"))
    ev_ebitda = _to_float(fundamentals.get("ev_ebitda"))

    # -------- FACTOR SCORES --------
    quality = _score_quality(gross_margin, operating_margin)
    growth = _score_growth_pct(revenue_cagr)
    value = _score_value(pe, ps, ev_ebitda)
    momentum = _score_momentum(rsi, trend)
    risk = _score_risk(vol20, max_dd)

    # ✅ FIX: use computed confidence
    confidence = _score_confidence(fundamentals, sma50, sma200, vol20, max_dd)

    # -------- BASE COMPOSITE --------
    # ---------------------------------------
    # SENTIMENT-ADJUSTED COMPOSITE
    # ---------------------------------------

    sentiment_score = 0.0

    try:
        from modules.market_data.news_service import get_finnhub_news
        from modules.market_data.news_service import (
            get_finnhub_news,
            derive_sentiment_from_news
        )
        news_items = get_finnhub_news(symbol)

        if news_items:
            sentiment_score = derive_sentiment_from_news(news_items)

    except Exception as e:
        sentiment_score = 0.0

    base_composite = _composite_weighted(quality, growth, value, momentum)

    # Weight sentiment lightly (10–15% influence)
    composite = (
            base_composite * 0.9
            + (sentiment_score * 100) * 0.1
    )

    def generate_trade_signal(composite, sentiment, confidence):
        if composite is None:
            return "Hold", "No composite score"

        # Strong Buy
        if composite >= 70 and sentiment > 0.1 and confidence >= 60:
            return "Strong Buy", "High composite + positive sentiment"

        # Buy
        if composite >= 60:
            return "Buy", "Solid fundamentals"

        # Sell
        if composite <= 40:
            if sentiment < -0.1:
                return "Strong Sell", "Weak + negative sentiment"
            return "Sell", "Weak composite"

        return "Hold", "Neutral conditions"
    # --------------------------------------------------
    # 🧠 SENTIMENT INTEGRATION (SAFE)
    # --------------------------------------------------
    try:
        from modules.market_data.news_service import get_finnhub_news

        def derive_sentiment_from_news(news_items):
            if not news_items:
                return 0.0

            bullish_words = [
                "beat", "growth", "strong", "upgrade", "outperform",
                "record", "surge", "expansion", "positive"
            ]

            bearish_words = [
                "miss", "weak", "downgrade", "decline", "drop",
                "cut", "risk", "concern", "negative"
            ]

            bullish = 0
            bearish = 0

            for n in news_items:
                text = f"{n.get('headline', '')} {n.get('summary', '')}".lower()

                if any(w in text for w in bullish_words):
                    bullish += 1

                if any(w in text for w in bearish_words):
                    bearish += 1

            total = bullish + bearish
            if total == 0:
                return 0.0

            return (bullish - bearish) / total

        news_items = get_finnhub_news(sym)
        sentiment_score = derive_sentiment_from_news(news_items)

        sentiment_scaled = sentiment_score * 100
        SENTIMENT_WEIGHT = 0.10

        composite += sentiment_scaled * SENTIMENT_WEIGHT

    except Exception as e:
        print("Sentiment integration failed:", e)

    print("FINAL COMPOSITE:", composite)
    signal, rationale = generate_trade_signal(
        composite,
        sentiment_score,
        confidence
    )
    # ---------------------------------------
    # 🚨 ALERT ENGINE (PLACE IT HERE)
    # ---------------------------------------
    alerts = check_for_alerts(
        symbol,
        signal,
        composite,
        sentiment_score
    )

    for alert in alerts:
        print("ALERT:", alert)

    if not signal:
        signal = "Hold"

    if sentiment_score is None:
        sentiment_score = sentiment_score if sentiment_score is not None else 0.0

        # -----------------------------
        # SIGNAL GENERATION (REQUIRED)
        # -----------------------------
        if composite is None:
            signal = None
        elif composite >= 65:
            signal = "Strong Buy"
        elif composite >= 55:
            signal = "Buy"
        elif composite <= 30:
            signal = "Strong Sell"
        elif composite <= 45:
            signal = "Sell"
        else:
            signal = "Hold"

        print("FINAL SIGNAL:", sym, composite, signal)
    # -------- SNAPSHOT --------
    snapshot = AnalyticsSnapshot(
        tenant_id=tenant_id,
        symbol=sym,
        asof=datetime.utcnow(),

        sector=_normalize_sector(fundamentals.get("sector")),

        rating = signal,

        # ✅ FIX: safe float conversion
        composite_score=float(composite or 0.0),

        # ✅ FIX: use real confidence
        confidence_score=float(confidence or 0.0),

        quality_score=_to_float(quality),
        growth_score=_to_float(growth),
        value_score=_to_float(value),
        momentum_score=_to_float(momentum),
        risk_score=_to_float(risk),

        trend=trend,
        rsi_14=_to_float(rsi),

        sma_50=_to_float(sma50),
        sma_200=_to_float(sma200),
        signal=signal,
        signal_rationale=rationale,
        support=_to_float(support),
        resistance=_to_float(resistance),
        sentiment_score=_to_float(sentiment_score),
        vol_20d=_to_float(vol20),
        max_drawdown_1y=_to_float(max_dd),

        latest_volume=_to_float(latest_volume),

        revenue_cagr=_to_float(fundamentals.get("revenue_cagr")),
        gross_margin=_to_float(fundamentals.get("gross_margin")),
        operating_margin=_to_float(fundamentals.get("operating_margin")),

        pe_ttm=_to_float(fundamentals.get("pe_ttm")),
        ps_ttm=_to_float(fundamentals.get("ps_ttm")),
        ev_ebitda=_to_float(fundamentals.get("ev_ebitda")),
        fcf_margin=_to_float(fundamentals.get("fcf_margin")),
    )

    # -----------------------------
    # UPSERT SNAPSHOT
    # -----------------------------
    existing = (
        db.query(AnalyticsSnapshot)
        .filter(
            AnalyticsSnapshot.tenant_id == tenant_id,
            AnalyticsSnapshot.symbol == symbol,
        )
        .order_by(AnalyticsSnapshot.asof.desc())
        .first()
    )

    if existing:
        existing.composite_score = float(composite or 0.0)
        existing.signal = signal
        existing.rating = signal
        existing.sentiment_score = float(sentiment_score or 0.0)
        existing.confidence_score = float(confidence or 0.0)
        existing.asof = datetime.utcnow()

        print("🔥 SNAPSHOT UPDATED:", sym, composite, signal)

        db.commit()
        return existing

    else:
        db.add(snapshot)

        print("🔥 SNAPSHOT INSERTED:", sym, composite, signal)

        db.commit()
        return snapshot



# ---------------------------------------------------
# BULK
# ---------------------------------------------------

def run_analytics(db, tenant_id, symbols):

    if isinstance(symbols, str):
        symbols = [symbols]

    results = []

    for i, s in enumerate(symbols):
        if i % 25 == 0:
            st.write(f"Processing {i}/{len(symbols)}")

        snap = run_analytics_for_symbol(db, tenant_id, s)

        if snap:
            results.append(snap)

    db.commit()

    st.success(f"Analytics completed: {len(results)} symbols")

    return results


# ---------------------------------------------------
# WRAPPER
# ---------------------------------------------------

def run_full_analytics(db, tenant_id, symbols):

    results = run_analytics(db, tenant_id, symbols)

    if not results:
        return None

    return results[-1]
# ---------------------------------------------------
# COMPATIBILITY: VECTOR ANALYTICS (UNIVERSE SUPPORT)
# ---------------------------------------------------

def run_vectorized_price_analytics(db, tenant_id, symbols, **kwargs):
    """
    Compatibility wrapper for legacy universe module.

    Previously vectorized — now routes to per-symbol analytics safely.
    """

    print("⚠️ Using fallback: run_vectorized_price_analytics → run_analytics")

    if isinstance(symbols, str):
        symbols = [symbols]

    results = []

    for i, sym in enumerate(symbols):

        if i % 50 == 0:
            print(f"Vector fallback processing {i}/{len(symbols)}")

        try:
            snap = run_analytics_for_symbol(db, tenant_id, sym)

            if snap:
                results.append(snap)

        except Exception as e:
            print("VECTOR FALLBACK ERROR:", sym, e)

    return results