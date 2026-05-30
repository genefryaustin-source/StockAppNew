import time
from datetime import datetime, UTC

import numpy as np
import pandas as pd
import requests
import streamlit as st

from modules.analytics.models import AnalyticsSnapshot
from modules.utils.config import get_secret

try:
    from modules.market_data.service import (
        get_latest_price_map,
        get_price_history,
        preload_histories,
        build_shared_price_cache,
    )
except Exception:
    from modules.market_data.service import (
        get_latest_price_map,
        get_price_history,
        build_shared_price_cache,
    )

    def preload_histories(
            db,
            symbols,
            period="1y",
            interval="1d",
    ):
        """
        Fallback preload helper in case service.py has not yet been updated.
        Prefer the service.py implementation when available.
        """
        history_map = {}

        clean_symbols = []
        for s in symbols or []:
            sym = str(s).upper().replace(".US", "").strip()
            if sym:
                clean_symbols.append(sym)

        clean_symbols = list(dict.fromkeys(clean_symbols))

        print(f"🚀 PRELOADING HISTORIES: {len(clean_symbols)} symbols")

        for i, sym in enumerate(clean_symbols):
            if i % 50 == 0:
                print(f"History preload {i}/{len(clean_symbols)}")

            try:
                df = get_price_history(
                    db=db,
                    symbol=sym,
                    period=period,
                    interval=interval,
                )

                if df is None or df.empty:
                    continue

                if len(df) < 50:
                    continue

                history_map[sym] = df

            except Exception as e:
                print("PRELOAD ERROR:", sym, e)

        print(f"✅ PRELOAD COMPLETE: {len(history_map)} loaded")

        return history_map


# ---------------------------------------------------
# CONFIG
# ---------------------------------------------------

EOD_REALTIME = "https://eodhd.com/api/real-time/stock"
EOD_EOD = "https://eodhd.com/api/eod"

_fund_cache = {}
_profile_cache = {}


# ---------------------------------------------------
# HELPERS
# ---------------------------------------------------

def _to_float(x):
    try:
        if x in (None, "", "NA", "N/A", "-", "--"):
            return None
        return float(x)
    except Exception:
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
        (30, 55), (40, 40), (60, 25), (999999, 10),
    ])

    ps_score = _score_inverse_metric(ps_ttm, [
        (2, 95), (4, 85), (6, 75), (8, 65),
        (10, 55), (15, 40), (25, 25), (999999, 10),
    ])

    ev_score = _score_inverse_metric(ev_ebitda, [
        (8, 95), (12, 85), (16, 75), (20, 65),
        (25, 55), (35, 40), (50, 25), (999999, 10),
    ])

    vals = [
        x for x in [
            pe_score,
            ps_score,
            ev_score,
        ]
        if x is not None
    ]

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
        "CONSUMER DEFENSIVE": "Consumer",

        "ENERGY": "Energy",
        "UTILITIES": "Utilities",
        "INDUSTRIALS": "Industrials",
        "MATERIALS": "Materials",
        "REAL ESTATE": "Real Estate",
        "COMMUNICATION": "Communication Services",
        "TELECOM": "Communication Services",
    }

    for k, v in mapping.items():
        if k in s:
            return v

    return s.title()


def _normalize_history_df(df):
    required_cols = [
        "Date",
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    ]

    if df is None or df.empty:
        return pd.DataFrame(columns=required_cols)

    df = df.copy()

    rename_map = {}

    for c in df.columns:
        lc = str(c).lower().strip()

        if lc in ("date", "datetime", "timestamp", "time"):
            rename_map[c] = "Date"
        elif lc == "open":
            rename_map[c] = "Open"
        elif lc == "high":
            rename_map[c] = "High"
        elif lc == "low":
            rename_map[c] = "Low"
        elif lc in ("close", "adj close", "adjusted_close"):
            rename_map[c] = "Close"
        elif lc in ("volume", "vol"):
            rename_map[c] = "Volume"

    df.rename(columns=rename_map, inplace=True)

    for col in required_cols:
        if col not in df.columns:
            if col == "Date":
                df[col] = pd.NaT
            else:
                df[col] = 0.0

    df["Date"] = pd.to_datetime(
        df["Date"],
        errors="coerce",
    )

    try:
        if getattr(df["Date"].dt, "tz", None) is not None:
            df["Date"] = df["Date"].dt.tz_convert(None)
    except Exception:
        try:
            df["Date"] = df["Date"].dt.tz_localize(None)
        except Exception:
            pass

    for col in [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    ]:
        df[col] = pd.to_numeric(
            df[col],
            errors="coerce",
        )

    df = df.dropna(subset=["Date", "Close"])

    df = (
        df
        .sort_values("Date")
        .drop_duplicates(subset=["Date"])
        .reset_index(drop=True)
    )

    return df[required_cols]


def _safe_json_response(response, provider_name, symbol):
    try:
        if response.status_code != 200:
            print(f"{provider_name} HTTP {response.status_code}: {symbol}")
            print(str(response.text or "")[:300])
            return None

        if not response.text or not response.text.strip():
            print(f"{provider_name} EMPTY RESPONSE: {symbol}")
            return None

        return response.json()

    except Exception as e:
        print(f"{provider_name} JSON ERROR: {symbol} {e}")
        return None


# ---------------------------------------------------
# LEGACY PRICE FETCH HELPERS
# ---------------------------------------------------

def _get_prices_many(symbols):
    """
    Legacy EODHD realtime helper retained for compatibility.
    Main analytics should use get_latest_price_map() from market_data.service.
    """
    key = get_secret("EODHD_API_KEY")

    if not key:
        return {}

    out = {}
    batch_size = 50

    clean_symbols = [
        _normalize(s)
        for s in symbols or []
        if s
    ]

    for i in range(0, len(clean_symbols), batch_size):
        batch = clean_symbols[i:i + batch_size]

        try:
            response = requests.get(
                EOD_REALTIME,
                params={
                    "api_token": key,
                    "fmt": "json",
                    "s": ",".join(batch),
                },
                timeout=6,
            )

            data = _safe_json_response(
                response,
                "EODHD REALTIME",
                ",".join(batch),
            )

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


def _get_latest_bar(symbol):
    """
    Legacy latest bar helper. Prefer normalized provider history for volume.
    """
    key = get_secret("EODHD_API_KEY")

    if not key:
        return {}

    try:
        response = requests.get(
            f"{EOD_EOD}/{_sym(symbol)}",
            params={
                "api_token": key,
                "fmt": "json",
                "limit": 1,
            },
            timeout=6,
        )

        data = _safe_json_response(
            response,
            "EODHD LATEST BAR",
            symbol,
        )

        if isinstance(data, list) and data:
            return data[-1]

    except Exception as e:
        print("LATEST BAR ERROR:", symbol, e)

    return {}


def _get_price_series(symbol):
    """
    Compatibility helper.
    Now uses normalized market_data.service history instead of direct EODHD/Finnhub history.
    """
    try:
        df = get_price_history(
            db=None,
            symbol=symbol,
            period="1y",
            interval="1d",
        )

        df = _normalize_history_df(df)

        if df is None or df.empty:
            return pd.DataFrame()

        closes = pd.to_numeric(
            df["Close"],
            errors="coerce",
        ).dropna()

        volumes = pd.to_numeric(
            df["Volume"],
            errors="coerce",
        ).fillna(0)

        return pd.DataFrame({
            "Close": closes,
            "Volume": volumes.iloc[:len(closes)].reset_index(drop=True),
        })

    except Exception as e:
        print("SERIES ERROR:", symbol, e)
        return pd.DataFrame()


# ---------------------------------------------------
# RSI
# ---------------------------------------------------

def _compute_rsi(series, period=14):
    if series is None or len(series) == 0:
        return pd.Series(dtype=float)

    series = pd.to_numeric(
        series,
        errors="coerce",
    ).dropna()

    if len(series) < period + 1:
        return pd.Series(dtype=float)

    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()

    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    return rsi.fillna(50.0)


# ---------------------------------------------------
# FUNDAMENTALS
# ---------------------------------------------------

def _get_fundamentals(symbol):
    sym = _normalize(symbol)

    if sym in _fund_cache:
        return _fund_cache[sym]

    key = get_secret("FINNHUB_API_KEY")

    if not key:
        return {}

    try:
        response = requests.get(
            "https://finnhub.io/api/v1/stock/metric",
            params={
                "symbol": sym,
                "metric": "all",
                "token": key,
            },
            timeout=8,
        )

        data = _safe_json_response(
            response,
            "FINNHUB METRIC",
            sym,
        )

        if not isinstance(data, dict):
            return {}

        metrics = data.get("metric", {})

        if not isinstance(metrics, dict):
            metrics = {}

        sector = None

        if sym in _profile_cache:
            sector = _profile_cache[sym]
        else:
            try:
                profile_response = requests.get(
                    "https://finnhub.io/api/v1/stock/profile2",
                    params={
                        "symbol": sym,
                        "token": key,
                    },
                    timeout=8,
                )

                profile_data = _safe_json_response(
                    profile_response,
                    "FINNHUB PROFILE",
                    sym,
                )

                if isinstance(profile_data, dict):
                    sector = profile_data.get("finnhubIndustry")

                print("✅ FINNHUB PROFILE SECTOR:", sym, sector)

                _profile_cache[sym] = sector

            except Exception as e:
                print("PROFILE ERROR:", sym, e)

        result = {
            "revenue_cagr": _to_float(metrics.get("revenueGrowthTTMYoy")),
            "gross_margin": _normalize_percent(metrics.get("grossMarginTTM")),
            "operating_margin": _normalize_percent(metrics.get("operatingMarginTTM")),
            "pe_ttm": _to_float(metrics.get("peTTM")),
            "ps_ttm": _to_float(metrics.get("psTTM")),
            "ev_ebitda": _to_float(metrics.get("evEbitdaTTM")),
            "fcf_margin": None,
            "sector": sector,
        }

        fcf_ps = _to_float(
            metrics.get("cashFlowPerShareTTM")
            or metrics.get("freeCashFlowPerShareTTM")
        )

        rev_ps = _to_float(metrics.get("revenuePerShareTTM"))

        print("DEBUG FCF INPUT:", sym, fcf_ps, rev_ps)

        if fcf_ps is not None and rev_ps not in (None, 0):
            result["fcf_margin"] = (fcf_ps / rev_ps) * 100
            print("✅ FCF CALCULATED:", sym, result["fcf_margin"])
        else:
            print("⚠️ FCF STILL MISSING:", sym)

        print("✅ FINNHUB FUNDAMENTALS USED:", sym)

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
# ALERTS
# ---------------------------------------------------

def check_for_alerts(symbol, signal, composite, sentiment):
    alerts = []

    if signal in ["Buy", "Strong Buy"]:
        alerts.append(f"🚀 {symbol} BUY signal")
    elif signal in ["Sell", "Strong Sell"]:
        alerts.append(f"⚠️ {symbol} SELL signal")

    if sentiment is not None:
        if sentiment > 0.1:
            alerts.append(f"📰 {symbol} positive news sentiment")
        elif sentiment < -0.1:
            alerts.append(f"📰 {symbol} negative news sentiment")

    if composite and composite >= 65:
        alerts.append(f"🔥 {symbol} strong composite score ({round(composite, 1)})")
    elif composite and composite <= 30:
        alerts.append(f"❄️ {symbol} weak composite score ({round(composite, 1)})")

    return alerts


# ---------------------------------------------------
# MAIN ANALYTICS
# ---------------------------------------------------

def run_analytics_for_symbol(
        db,
        tenant_id,
        symbol,
        price_df=None,
):
    sym = _normalize(symbol)

    if not sym:
        return None

    # ---------------------------------
    # PRICE HISTORY / SERIES
    # ---------------------------------
    df = price_df

    if df is None or df.empty:
        try:
            df = get_price_history(
                db=db,
                symbol=sym,
                period="1y",
                interval="1d",
            )
        except Exception as e:
            print("PRICE HISTORY ERROR:", sym, e)
            df = pd.DataFrame()

    df = _normalize_history_df(df)

    if df is None or df.empty or len(df) < 50:
        print("INSUFFICIENT PRICE HISTORY:", sym, 0 if df is None else len(df))
        return None

    required_cols = [
        "Close",
        "Volume",
    ]

    for col in required_cols:
        if col not in df.columns:
            print(f"MISSING REQUIRED COLUMN {col}: {sym}")
            return None

    closes = pd.to_numeric(
        df["Close"],
        errors="coerce",
    ).dropna()

    volumes = pd.to_numeric(
        df["Volume"],
        errors="coerce",
    ).fillna(0)

    if len(closes) < 50:
        print("INSUFFICIENT CLOSE SERIES:", sym, len(closes))
        return None

    # ---------------------------------
    # LATEST PRICE
    # ---------------------------------
    price = None

    try:
        latest_prices = get_latest_price_map([sym])

        if isinstance(latest_prices, dict):
            price = (
                latest_prices.get(sym)
                or latest_prices.get(f"{sym}.US")
            )

    except Exception as e:
        print("LATEST PRICE ERROR:", sym, e)

    if price is None or float(price or 0) <= 0:
        try:
            price = float(closes.iloc[-1])
        except Exception:
            price = None

    if price is None or float(price or 0) <= 0:
        print("NO PRICE:", sym, {})
        return None

    price = float(price)

    # ---------------------------------
    # TECHNICALS
    # ---------------------------------
    rsi_series = _compute_rsi(closes)
    rsi = rsi_series.iloc[-1] if rsi_series is not None and not rsi_series.empty else 50.0

    sma50 = closes.rolling(50).mean().iloc[-1] if len(closes) >= 50 else None
    sma200 = closes.rolling(200).mean().iloc[-1] if len(closes) >= 200 else None

    returns = closes.pct_change().dropna()

    vol20 = returns.tail(20).std() * np.sqrt(252) if len(returns) >= 20 else None
    max_dd = ((closes - closes.cummax()) / closes.cummax()).min()

    support = closes.tail(20).min()
    resistance = closes.tail(20).max()

    # ---------------------------------
    # TREND
    # ---------------------------------
    trend = "Range"

    if sma50 is not None and sma200 is not None:
        if price > sma50 > sma200:
            trend = "Uptrend"
        elif price < sma50 < sma200:
            trend = "Downtrend"

    # ---------------------------------
    # VOLUME
    # ---------------------------------
    try:
        latest_volume = float(volumes.iloc[-1]) if len(volumes) else 0.0
    except Exception:
        latest_volume = 0.0

    # ---------------------------------
    # FUNDAMENTALS
    # ---------------------------------
    fundamentals = _get_fundamentals(sym) or {}

    gross_margin = _to_float(fundamentals.get("gross_margin"))
    operating_margin = _to_float(fundamentals.get("operating_margin"))
    revenue_cagr = _to_float(fundamentals.get("revenue_cagr"))
    fcf_margin = _to_float(fundamentals.get("fcf_margin"))

    pe = _to_float(fundamentals.get("pe_ttm"))
    ps = _to_float(fundamentals.get("ps_ttm"))
    ev_ebitda = _to_float(fundamentals.get("ev_ebitda"))

    # ---------------------------------
    # FACTOR SCORES
    # ---------------------------------
    quality = _score_quality(gross_margin, operating_margin)
    growth = _score_growth_pct(revenue_cagr)
    value = _score_value(pe, ps, ev_ebitda)
    momentum = _score_momentum(rsi, trend)
    risk = _score_risk(vol20, max_dd)

    confidence = _score_confidence(
        fundamentals,
        sma50,
        sma200,
        vol20,
        max_dd,
    )

    base_composite = _composite_weighted(
        quality,
        growth,
        value,
        momentum,
    )

    if base_composite is None:
        base_composite = 50.0

    # ---------------------------------
    # SENTIMENT
    # ---------------------------------
    sentiment_score = 0.0

    try:
        from modules.market_data.news_service import (
            get_finnhub_news,
            derive_sentiment_from_news,
        )

        news_items = get_finnhub_news(sym)

        if news_items:
            sentiment_score = derive_sentiment_from_news(news_items)

    except Exception as e:
        print("Sentiment integration failed:", sym, e)
        sentiment_score = 0.0

    sentiment_score = float(sentiment_score or 0.0)

    composite = (
        float(base_composite) * 0.90
        + (sentiment_score * 100.0) * 0.10
    )

    composite = _clip_score(composite)

    # ---------------------------------
    # SIGNAL GENERATION
    # ---------------------------------
    def generate_trade_signal(composite_score, sentiment, confidence_score):
        if composite_score is None:
            return "Hold", "No composite score"

        if composite_score >= 70 and sentiment > 0.1 and confidence_score >= 60:
            return "Strong Buy", "High composite + positive sentiment"

        if composite_score >= 60:
            return "Buy", "Solid fundamentals"

        if composite_score <= 40:
            if sentiment < -0.1:
                return "Strong Sell", "Weak composite + negative sentiment"
            return "Sell", "Weak composite"

        return "Hold", "Neutral conditions"

    signal, rationale = generate_trade_signal(
        composite,
        sentiment_score,
        confidence,
    )

    if not signal:
        signal = "Hold"

    print("FINAL COMPOSITE:", sym, composite)
    print("FINAL SIGNAL:", sym, composite, signal)

    # ---------------------------------
    # ALERTS
    # ---------------------------------
    try:
        alerts = check_for_alerts(
            sym,
            signal,
            composite,
            sentiment_score,
        )

        for alert in alerts:
            print("ALERT:", alert)

    except Exception as e:
        print("ALERT CHECK ERROR:", sym, e)

    # ---------------------------------
    # SNAPSHOT
    # ---------------------------------
    snapshot = AnalyticsSnapshot(
        tenant_id=tenant_id,
        symbol=sym,
        asof=datetime.now(UTC),

        sector=_normalize_sector(fundamentals.get("sector")),

        rating=signal,
        composite_score=float(composite or 0.0),
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

        revenue_cagr=_to_float(revenue_cagr),
        gross_margin=_to_float(gross_margin),
        operating_margin=_to_float(operating_margin),

        pe_ttm=_to_float(pe),
        ps_ttm=_to_float(ps),
        ev_ebitda=_to_float(ev_ebitda),
        fcf_margin=_to_float(fcf_margin),
    )

    # ---------------------------------
    # UPSERT SNAPSHOT
    # ---------------------------------
    existing = (
        db.query(AnalyticsSnapshot)
        .filter(
            AnalyticsSnapshot.tenant_id == tenant_id,
            AnalyticsSnapshot.symbol == sym,
        )
        .order_by(AnalyticsSnapshot.asof.desc())
        .first()
    )

    if existing:
        existing.asof = datetime.now(UTC)
        existing.sector = _normalize_sector(fundamentals.get("sector"))
        existing.rating = signal
        existing.composite_score = float(composite or 0.0)
        existing.confidence_score = float(confidence or 0.0)

        existing.quality_score = _to_float(quality)
        existing.growth_score = _to_float(growth)
        existing.value_score = _to_float(value)
        existing.momentum_score = _to_float(momentum)
        existing.risk_score = _to_float(risk)

        existing.trend = trend
        existing.rsi_14 = _to_float(rsi)
        existing.sma_50 = _to_float(sma50)
        existing.sma_200 = _to_float(sma200)
        existing.signal = signal
        existing.signal_rationale = rationale
        existing.support = _to_float(support)
        existing.resistance = _to_float(resistance)
        existing.sentiment_score = _to_float(sentiment_score)
        existing.vol_20d = _to_float(vol20)
        existing.max_drawdown_1y = _to_float(max_dd)

        existing.latest_volume = _to_float(latest_volume)

        existing.revenue_cagr = _to_float(revenue_cagr)
        existing.gross_margin = _to_float(gross_margin)
        existing.operating_margin = _to_float(operating_margin)

        existing.pe_ttm = _to_float(pe)
        existing.ps_ttm = _to_float(ps)
        existing.ev_ebitda = _to_float(ev_ebitda)
        existing.fcf_margin = _to_float(fcf_margin)

        print("🔥 SNAPSHOT UPDATED:", sym, composite, signal)

        db.commit()
        return existing

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

    clean_symbols = []

    for s in symbols or []:
        sym = _normalize(s)

        if sym:
            clean_symbols.append(sym)

    clean_symbols = list(dict.fromkeys(clean_symbols))

    if not clean_symbols:
        st.warning("No symbols provided for analytics.")
        return []

    # ---------------------------------
    # PRELOAD PRICE HISTORIES
    # ---------------------------------
    history_map = preload_histories(
        db=db,
        symbols=clean_symbols,
        period="1y",
        interval="1d",
    )

    results = []

    for i, sym in enumerate(clean_symbols):
        if i % 25 == 0:
            st.write(f"Processing {i}/{len(clean_symbols)}")

        try:
            snap = run_analytics_for_symbol(
                db=db,
                tenant_id=tenant_id,
                symbol=sym,
                price_df=history_map.get(sym),
            )

            if snap:
                results.append(snap)

        except Exception as e:
            print("ANALYTICS ERROR:", sym, e)

    db.commit()

    st.success(f"Analytics completed: {len(results)} symbols")

    return results


# ---------------------------------------------------
# WRAPPER
# ---------------------------------------------------

def run_full_analytics(db, tenant_id, symbols):
    results = run_analytics(
        db=db,
        tenant_id=tenant_id,
        symbols=symbols,
    )

    if not results:
        return None

    return results[-1]


# ---------------------------------------------------
# COMPATIBILITY: VECTOR ANALYTICS
# ---------------------------------------------------

def run_vectorized_price_analytics(
        db,
        tenant_id,
        symbols,
        **kwargs,
):
    """
    Vector-compatible analytics runner.

    Uses shared normalized cached price history and passes cached
    dataframes into run_analytics_for_symbol() to avoid repeated
    provider fetches inside the analytics loop.
    """
    print(
        f"🚨 VECTOR STEP 1 — ENTERED "
        f"run_vectorized_price_analytics "
        f"symbols={len(symbols)}"
    )
    if isinstance(symbols, str):
        symbols = [symbols]

    clean_symbols = []

    for s in symbols or []:

        try:
            sym = _normalize(s)

            if sym:
                clean_symbols.append(sym)

        except Exception:
            continue

    clean_symbols = list(dict.fromkeys(clean_symbols))

    print(f"🚀 VECTOR ANALYTICS START: {len(clean_symbols)} symbols")

    if not clean_symbols:
        return []

    # ---------------------------------
    # BUILD SHARED CACHE
    # ---------------------------------
    try:

        price_cache, meta = build_shared_price_cache(
            db=db,
            symbols=clean_symbols,
            min_rows=50,
            period="1y",
            interval="1d",
            max_api_calls=kwargs.get("max_api_calls", None),
        )

    except Exception as e:
        print("🚨 SHARED CACHE BUILD FAILED:", e)
        price_cache = {}
        meta = {}

    if not price_cache:
        print("🚨 VECTOR CACHE EMPTY")
        return []

    print(f"✅ VECTOR CACHE READY: {len(price_cache)} symbols")

    # ---------------------------------
    # ANALYTICS LOOP
    # ---------------------------------
    results = []

    for i, sym in enumerate(clean_symbols):
        if i % 50 == 0:
            print(f"Vector analytics processing {i}/{len(clean_symbols)}")

        try:
            cached_df = price_cache.get(sym)

            if cached_df is None or cached_df.empty:
                continue

            cached_df = _normalize_history_df(cached_df)

            if cached_df is None or cached_df.empty or len(cached_df) < 50:
                continue

            snap = run_analytics_for_symbol(
                db=db,
                tenant_id=tenant_id,
                symbol=sym,
                price_df=cached_df,
            )

            if snap:
                results.append(snap)

        except Exception as e:
            print("VECTOR ANALYTICS ERROR:", sym, e)

    print(f"✅ VECTOR ANALYTICS COMPLETE: {len(results)} snapshots")

    return results