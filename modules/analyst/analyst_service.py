"""
modules/analyst/analyst_service.py

Analyst Consensus Estimates & Revision Tracking Service.

Data sources (both already in secrets.toml):
  FMP (FMP_API_KEY):
    - Analyst EPS/revenue estimates with historical revisions
    - Price target history by analyst firm
    - Upgrade/downgrade history
    - Consensus direction (improving/deteriorating)

  Finnhub (FINNHUB_API_KEY):
    - Buy/Hold/Sell recommendation counts over time
    - Consensus price target
    - EPS estimates vs actuals (surprise history)
    - Revenue estimates

Key metric: EPS Revision Direction
  Are analysts revising estimates UP or DOWN over 30/60/90 days?
  This is one of the most predictive quantitative factors.
  Rising estimates → price momentum tends to follow.
  Falling estimates → mean reversion / downside risk.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

import requests
import streamlit as st

_CACHE: dict = {}
_CACHE_TTL = 3600  # 1 hour for analyst data


# ─────────────────────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────────────────────

def _get_secret(key: str) -> Optional[str]:
    try:
        if key in st.secrets:
            return str(st.secrets[key]) or None
    except Exception:
        pass
    val = os.getenv(key, "")
    if val:
        return val
    try:
        from modules.utils.config import get_secret
        return get_secret(key) or None
    except Exception:
        pass
    return None


def _fmp_key() -> Optional[str]:
    return _get_secret("FMP_API_KEY")


def _fh_key() -> Optional[str]:
    return _get_secret("FINNHUB_API_KEY")


def _get_cached(key: str):
    entry = _CACHE.get(key)
    if entry and time.time() - entry["ts"] < _CACHE_TTL:
        return entry["data"]
    return None


def _set_cached(key: str, data):
    _CACHE[key] = {"data": data, "ts": time.time()}


def _fmp_get(path: str, params: dict = None) -> Optional[dict]:
    key = _fmp_key()
    if not key:
        return None
    try:
        p = {"apikey": key, **(params or {})}
        r = requests.get(
            f"https://financialmodelingprep.com/api{path}",
            params=p, timeout=10,
        )
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"[analyst] FMP error {path}: {e}")
    return None


def _fh_get(path: str, params: dict = None) -> Optional[dict]:
    key = _fh_key()
    if not key:
        return None
    try:
        p = {"token": key, **(params or {})}
        r = requests.get(
            f"https://finnhub.io/api/v1{path}",
            params=p, timeout=10,
        )
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"[analyst] Finnhub error {path}: {e}")
    return None


# ─────────────────────────────────────────────────────────────
# EPS Estimates & Revision Tracking  (FMP primary)
# ─────────────────────────────────────────────────────────────

def get_eps_estimates(ticker: str) -> list[dict]:
    """
    Historical EPS estimates showing revision trend.
    FMP returns estimates by quarter with date — multiple snapshots
    let us see whether estimates are being revised up or down.
    """
    cache_key = f"eps_est_{ticker}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    # FMP analyst estimates (EPS + Revenue)
    data = _fmp_get(f"/v3/analyst-estimates/{ticker.upper()}")
    if not data or not isinstance(data, list):
        # Fallback: Finnhub EPS estimates
        return _get_eps_finnhub(ticker)

    results = []
    for item in data[:12]:  # up to 12 periods
        results.append({
            "date":              str(item.get("date", ""))[:10],
            "period":            str(item.get("period", "")),
            "eps_avg":           _sf(item.get("estimatedEpsAvg")),
            "eps_high":          _sf(item.get("estimatedEpsHigh")),
            "eps_low":           _sf(item.get("estimatedEpsLow")),
            "revenue_avg":       _sf(item.get("estimatedRevenueAvg")),
            "revenue_high":      _sf(item.get("estimatedRevenueHigh")),
            "revenue_low":       _sf(item.get("estimatedRevenueLow")),
            "num_analysts_eps":  int(item.get("numberAnalystEstimatedEps") or 0),
            "num_analysts_rev":  int(item.get("numberAnalystsEstimatedRevenue") or 0),
            "source":            "fmp",
        })

    _set_cached(cache_key, results)
    return results


def _get_eps_finnhub(ticker: str) -> list[dict]:
    """Finnhub EPS estimates fallback."""
    data = _fh_get("/stock/eps-estimate", {"symbol": ticker.upper(), "freq": "quarterly"})
    if not data or "data" not in data:
        return []

    results = []
    for item in (data["data"] or [])[:8]:
        results.append({
            "date":             str(item.get("period", ""))[:10],
            "period":           str(item.get("period", ""))[:7],
            "eps_avg":          _sf(item.get("epsAvg")),
            "eps_high":         _sf(item.get("epsHigh")),
            "eps_low":          _sf(item.get("epsLow")),
            "revenue_avg":      None,
            "revenue_high":     None,
            "revenue_low":      None,
            "num_analysts_eps": int(item.get("numberAnalysts") or 0),
            "num_analysts_rev": 0,
            "source":           "finnhub",
        })
    return results


# ─────────────────────────────────────────────────────────────
# EPS Surprise History (actual vs estimated)
# ─────────────────────────────────────────────────────────────

def get_eps_surprise(ticker: str) -> list[dict]:
    """
    Historical EPS actual vs consensus estimate.
    Beat/miss pattern is predictive of future revisions.
    """
    cache_key = f"eps_surprise_{ticker}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    # Try FMP first
    data = _fmp_get(f"/v3/earnings-surprises/{ticker.upper()}")
    results = []

    if data and isinstance(data, list):
        for item in data[:12]:
            actual   = _sf(item.get("actualEarningResult"))
            estimate = _sf(item.get("estimatedEarning"))
            surprise = round(actual - estimate, 4) if actual is not None and estimate is not None else None
            surprise_pct = round(surprise / abs(estimate) * 100, 2) if surprise is not None and estimate else None
            results.append({
                "date":         str(item.get("date", ""))[:10],
                "actual":       actual,
                "estimate":     estimate,
                "surprise":     surprise,
                "surprise_pct": surprise_pct,
                "beat":         surprise > 0 if surprise is not None else None,
                "source":       "fmp",
            })
    else:
        # Finnhub fallback
        fh = _fh_get("/stock/earnings", {"symbol": ticker.upper()})
        if fh and isinstance(fh, list):
            for item in fh[:8]:
                actual   = _sf(item.get("actual"))
                estimate = _sf(item.get("estimate"))
                surprise = _sf(item.get("surprise"))
                surprise_pct = _sf(item.get("surprisePercent"))
                results.append({
                    "date":         str(item.get("period", ""))[:10],
                    "actual":       actual,
                    "estimate":     estimate,
                    "surprise":     surprise,
                    "surprise_pct": surprise_pct,
                    "beat":         surprise > 0 if surprise is not None else None,
                    "source":       "finnhub",
                })

    _set_cached(cache_key, results)
    return results


# ─────────────────────────────────────────────────────────────
# Price Target History & Consensus
# ─────────────────────────────────────────────────────────────

def get_price_targets(ticker: str) -> dict:
    """
    Analyst price targets — consensus, high, low, and individual targets.
    Shows whether consensus target is rising or falling.
    """
    cache_key = f"pt_{ticker}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    result = {
        "ticker":          ticker.upper(),
        "consensus_target": None,
        "high_target":     None,
        "low_target":      None,
        "median_target":   None,
        "num_analysts":    0,
        "current_price":   None,
        "upside_pct":      None,
        "recent_targets":  [],
        "source":          "none",
    }

    # FMP consensus
    consensus = _fmp_get(f"/v4/price-target-consensus", {"symbol": ticker.upper()})
    if consensus and isinstance(consensus, list) and consensus:
        c = consensus[0]
        result.update({
            "consensus_target": _sf(c.get("targetConsensus")),
            "high_target":      _sf(c.get("targetHigh")),
            "low_target":       _sf(c.get("targetLow")),
            "median_target":    _sf(c.get("targetMedian")),
            "source":           "fmp",
        })

    # FMP individual targets (recent)
    targets = _fmp_get(f"/v4/price-target", {"symbol": ticker.upper()})
    if targets and isinstance(targets, list):
        for t in targets[:20]:
            result["recent_targets"].append({
                "date":       str(t.get("publishedDate", ""))[:10],
                "analyst":    str(t.get("analystName", "") or t.get("analyst", "")),
                "firm":       str(t.get("analystCompany", "") or t.get("firm", "")),
                "target":     _sf(t.get("priceTarget")),
                "prior":      _sf(t.get("priorPriceTarget")),
                "action":     _updown(t.get("priceTarget"), t.get("priorPriceTarget")),
            })
        result["num_analysts"] = len(targets)

    # Finnhub price target fallback for consensus
    if result["consensus_target"] is None:
        fh = _fh_get("/stock/price-target", {"symbol": ticker.upper()})
        if fh:
            result.update({
                "consensus_target": _sf(fh.get("targetMean")),
                "high_target":      _sf(fh.get("targetHigh")),
                "low_target":       _sf(fh.get("targetLow")),
                "median_target":    _sf(fh.get("targetMedian")),
                "num_analysts":     int(fh.get("numberOfAnalysts") or 0),
                "source":           "finnhub",
            })

    _set_cached(cache_key, result)
    return result


def _updown(new, old) -> str:
    if new is None or old is None:
        return "—"
    try:
        return "↑" if float(new) > float(old) else "↓" if float(new) < float(old) else "→"
    except Exception:
        return "—"


# ─────────────────────────────────────────────────────────────
# Upgrade / Downgrade History
# ─────────────────────────────────────────────────────────────

def get_upgrades_downgrades(ticker: str, days: int = 90) -> list[dict]:
    """
    Recent analyst rating changes — upgrades, downgrades, initiations.
    Shows momentum in analyst sentiment.
    """
    cache_key = f"upgrades_{ticker}_{days}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    # FMP upgrades/downgrades
    data = _fmp_get(f"/v4/upgrades-downgrades", {"symbol": ticker.upper()})
    results = []

    if data and isinstance(data, list):
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        for item in data:
            date = str(item.get("publishedDate") or item.get("date") or "")[:10]
            if date < cutoff:
                continue
            action = str(item.get("action") or "").lower()
            results.append({
                "date":        date,
                "firm":        str(item.get("gradingCompany") or item.get("firm") or ""),
                "action":      action,
                "from_grade":  str(item.get("previousGrade") or item.get("fromGrade") or ""),
                "to_grade":    str(item.get("newGrade") or item.get("toGrade") or ""),
                "is_upgrade":  any(w in action for w in ("upgrade", "initiat", "reiterat buy", "outperform")),
                "is_downgrade":any(w in action for w in ("downgrade", "lower", "underperform")),
                "source":      "fmp",
            })

    if not results:
        # Finnhub recommendations fallback
        fh = _fh_get("/stock/recommendation", {"symbol": ticker.upper()})
        if fh and isinstance(fh, list):
            for item in fh[:6]:
                results.append({
                    "date":        str(item.get("period", ""))[:10],
                    "firm":        "Consensus",
                    "action":      "consensus",
                    "from_grade":  "",
                    "to_grade":    "",
                    "buy":         int(item.get("buy") or 0),
                    "hold":        int(item.get("hold") or 0),
                    "sell":        int(item.get("sell") or 0),
                    "strong_buy":  int(item.get("strongBuy") or 0),
                    "strong_sell": int(item.get("strongSell") or 0),
                    "is_upgrade":  False,
                    "is_downgrade":False,
                    "source":      "finnhub",
                })

    _set_cached(cache_key, results)
    return results


# ─────────────────────────────────────────────────────────────
# Buy/Hold/Sell Recommendation Trend  (Finnhub)
# ─────────────────────────────────────────────────────────────

def get_recommendation_trend(ticker: str) -> list[dict]:
    """
    Monthly buy/hold/sell counts from all covering analysts.
    Trend shows whether analyst consensus is improving or deteriorating.
    """
    cache_key = f"reco_{ticker}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    data = _fh_get("/stock/recommendation", {"symbol": ticker.upper()})
    if not data or not isinstance(data, list):
        return []

    results = []
    for item in data[:12]:
        buy   = int(item.get("buy") or 0)
        hold  = int(item.get("hold") or 0)
        sell  = int(item.get("sell") or 0)
        sbuy  = int(item.get("strongBuy") or 0)
        ssell = int(item.get("strongSell") or 0)
        total = buy + hold + sell + sbuy + ssell
        bull  = sbuy + buy
        bear  = ssell + sell
        score = round((sbuy * 1 + buy * 2 + hold * 3 + sell * 4 + ssell * 5) / total, 2) if total > 0 else 3.0

        results.append({
            "period":      str(item.get("period", ""))[:7],
            "strong_buy":  sbuy,
            "buy":         buy,
            "hold":        hold,
            "sell":        sell,
            "strong_sell": ssell,
            "total":       total,
            "bull_pct":    round(bull / total * 100, 1) if total > 0 else 0,
            "bear_pct":    round(bear / total * 100, 1) if total > 0 else 0,
            "score":       score,  # 1=Strong Buy → 5=Strong Sell
            "sentiment":   "Strong Buy" if score < 1.5 else "Buy" if score < 2.5 else
                           "Hold" if score < 3.5 else "Sell" if score < 4.5 else "Strong Sell",
        })

    _set_cached(cache_key, results)
    return results


# ─────────────────────────────────────────────────────────────
# Revision Score  (the key quantitative signal)
# ─────────────────────────────────────────────────────────────

def get_revision_score(ticker: str) -> dict:
    """
    Compute EPS estimate revision direction over 30/60/90 days.

    Compares the most recent EPS estimate for each upcoming quarter
    against estimates from 30, 60, and 90 days ago to determine
    whether analysts are revising up or down.

    This is the core quant factor — rising revisions precede
    price outperformance, falling revisions precede underperformance.
    """
    cache_key = f"revision_{ticker}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    estimates = get_eps_estimates(ticker)
    upgrades  = get_upgrades_downgrades(ticker, days=90)
    recos     = get_recommendation_trend(ticker)

    # ── EPS revision direction from estimates ─────────────────
    # Sort by date to find most recent
    estimates_sorted = sorted(
        [e for e in estimates if e.get("eps_avg") is not None],
        key=lambda x: x.get("date", ""),
        reverse=True,
    )

    # Compare consecutive periods to detect revision direction
    rev_changes = []
    for i in range(len(estimates_sorted) - 1):
        curr = estimates_sorted[i]["eps_avg"]
        prev = estimates_sorted[i + 1]["eps_avg"]
        if curr is not None and prev is not None and prev != 0:
            chg = round((curr - prev) / abs(prev) * 100, 2)
            rev_changes.append(chg)

    avg_revision = round(sum(rev_changes) / len(rev_changes), 2) if rev_changes else 0
    revision_direction = (
        "↑ Improving" if avg_revision > 1 else
        "↓ Deteriorating" if avg_revision < -1 else
        "→ Stable"
    )

    # ── Upgrade/downgrade balance (last 90 days) ─────────────
    ups   = sum(1 for u in upgrades if u.get("is_upgrade"))
    downs = sum(1 for u in upgrades if u.get("is_downgrade"))
    rating_trend = (
        "↑ More upgrades" if ups > downs else
        "↓ More downgrades" if downs > ups else
        "→ Balanced"
    )

    # ── Recommendation momentum ───────────────────────────────
    reco_momentum = "→ Stable"
    if len(recos) >= 2:
        score_now  = recos[0].get("score", 3.0)
        score_prev = recos[1].get("score", 3.0)
        if score_now < score_prev - 0.1:
            reco_momentum = "↑ Getting more bullish"
        elif score_now > score_prev + 0.1:
            reco_momentum = "↓ Getting more bearish"

    # ── Composite revision score ──────────────────────────────
    # Positive = bullish revisions, Negative = bearish
    eps_score    = min(100, max(-100, avg_revision * 10))
    rating_score = (ups - downs) * 10
    reco_score   = (3.0 - recos[0].get("score", 3.0)) * 20 if recos else 0
    composite    = round((eps_score * 0.5 + rating_score * 0.3 + reco_score * 0.2), 1)

    result = {
        "ticker":              ticker.upper(),
        "revision_direction":  revision_direction,
        "avg_eps_revision_pct":avg_revision,
        "rating_trend":        rating_trend,
        "upgrades_90d":        ups,
        "downgrades_90d":      downs,
        "reco_momentum":       reco_momentum,
        "composite_revision":  composite,
        "composite_label": (
            "Strong Positive" if composite > 30 else
            "Positive"        if composite > 10 else
            "Neutral"         if composite > -10 else
            "Negative"        if composite > -30 else
            "Strong Negative"
        ),
        "current_reco": recos[0]["sentiment"] if recos else "N/A",
        "bull_pct":     recos[0]["bull_pct"]  if recos else 0,
        "bear_pct":     recos[0]["bear_pct"]  if recos else 0,
        "total_analysts": recos[0]["total"]   if recos else 0,
    }

    _set_cached(cache_key, result)
    return result


def _sf(v) -> Optional[float]:
    try:
        return float(v) if v is not None else None
    except Exception:
        return None