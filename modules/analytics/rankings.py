from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Optional

import streamlit as st
import pandas as pd

from modules.analytics.snapshot_cache import get_latest_snapshots_df


@dataclass
class RankedRow:
    symbol: str
    sector: Optional[str]
    rating: Optional[str]

    composite: Optional[float]
    confidence: Optional[float]

    quality: Optional[float]
    growth: Optional[float]
    value: Optional[float]
    momentum: Optional[float]
    risk: Optional[float]

    quality_pct: Optional[float] = None
    growth_pct: Optional[float] = None
    value_pct: Optional[float] = None
    momentum_pct: Optional[float] = None
    risk_pct: Optional[float] = None
    composite_pct: Optional[float] = None
    top_decile: bool = False
    top_quartile: bool = False


def _to_float(x):
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def _percentile_rank(series: pd.Series, ascending: bool = True) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    if s.notna().sum() == 0:
        return pd.Series([None] * len(series), index=series.index, dtype="float64")
    ranked = s.rank(method="average", pct=True, ascending=ascending) * 100.0
    return ranked.round(2)


def _weighted_mean(row, cols_weights: list[tuple[str, float]]) -> float | None:
    vals = []
    weights = []

    for col, w in cols_weights:
        v = row.get(col)
        if pd.notna(v):
            vals.append(float(v) * w)
            weights.append(w)

    if not weights:
        return None

    return round(sum(vals) / sum(weights), 2)


def _apply_percentiles(df: pd.DataFrame, sector_relative: bool = False) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    out = df.copy()

    if sector_relative and "sector" in out.columns:
        grouped = []

        for _, g in out.groupby(out["sector"].fillna("Unknown")):
            g = g.copy()
            g["quality_pct"] = _percentile_rank(g["quality_score"], ascending=True)
            g["growth_pct"] = _percentile_rank(g["growth_score"], ascending=True)
            g["value_pct"] = _percentile_rank(g["value_score"], ascending=True)
            g["momentum_pct"] = _percentile_rank(g["momentum_score"], ascending=True)
            g["risk_pct"] = _percentile_rank(g["risk_score"], ascending=False)
            g["composite_pct_raw"] = _percentile_rank(g["composite_score"], ascending=True)
            grouped.append(g)

        out = pd.concat(grouped, ignore_index=True)

    else:
        out["quality_pct"] = _percentile_rank(out["quality_score"], ascending=True)
        out["growth_pct"] = _percentile_rank(out["growth_score"], ascending=True)
        out["value_pct"] = _percentile_rank(out["value_score"], ascending=True)
        out["momentum_pct"] = _percentile_rank(out["momentum_score"], ascending=True)
        out["risk_pct"] = _percentile_rank(out["risk_score"], ascending=False)
        out["composite_pct_raw"] = _percentile_rank(out["composite_score"], ascending=True)

    weights = [
        ("quality_pct", 0.30),
        ("growth_pct", 0.20),
        ("value_pct", 0.25),
        ("momentum_pct", 0.25),
    ]

    out["percentile_composite"] = out.apply(lambda row: _weighted_mean(row, weights), axis=1)

    out["top_decile"] = out["percentile_composite"].apply(
        lambda x: bool(pd.notna(x) and x >= 90)
    )
    out["top_quartile"] = out["percentile_composite"].apply(
        lambda x: bool(pd.notna(x) and x >= 75)
    )

    return out


def rank_symbols(
    db,
    tenant_id: str,
    symbols: List[str],
    min_confidence: float = 0.0,
    require_composite: bool = True,
    use_percentiles: bool = True,
    sector_relative: bool = False,
) -> List[RankedRow]:

    if not symbols:
        st.session_state.rank_rows = []
        return []

    syms = [str(s).strip().upper() for s in symbols if s and str(s).strip()]
    if not syms:
        st.session_state.rank_rows = []
        return []

    df = get_latest_snapshots_df(db, tenant_id)

    if df is None or df.empty:
        st.session_state.rank_rows = []
        return []

    if "symbol" not in df.columns:
        st.session_state.rank_rows = []
        return []

    df["symbol"] = df["symbol"].astype(str).str.upper()
    df = df[df["symbol"].isin(syms)].copy()

    if df.empty:
        st.session_state.rank_rows = []
        return []

    numeric_cols = [
        "quality_score",
        "growth_score",
        "value_score",
        "momentum_score",
        "risk_score",
        "composite_score",
        "confidence_score",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if require_composite and "composite_score" in df.columns:
        df = df[df["composite_score"].notna()].copy()

    if "confidence_score" in df.columns:
        df = df[
            df["confidence_score"].isna()
            | (df["confidence_score"] >= float(min_confidence))
        ].copy()

    if df.empty:
        st.session_state.rank_rows = []
        return []

    if use_percentiles:
        df = _apply_percentiles(df, sector_relative=sector_relative)

        df["__sort_comp"] = pd.to_numeric(df["percentile_composite"], errors="coerce")
        df["__sort_conf"] = pd.to_numeric(df["confidence_score"], errors="coerce")

        df = df.sort_values(
            by=["__sort_comp", "__sort_conf", "composite_score"],
            ascending=[False, False, False],
            na_position="last",
        )
    else:
        if "composite_score" in df.columns:
            df["__sort_comp"] = pd.to_numeric(df["composite_score"], errors="coerce")
        else:
            df["__sort_comp"] = None

        if "confidence_score" in df.columns:
            df["__sort_conf"] = pd.to_numeric(df["confidence_score"], errors="coerce")
        else:
            df["__sort_conf"] = None

        df = df.sort_values(
            by=["__sort_comp", "__sort_conf"],
            ascending=[False, False],
            na_position="last",
        )

    ranked: List[RankedRow] = []

    for _, r in df.iterrows():
        ranked.append(
            RankedRow(
                symbol=str(r.get("symbol", "")).upper(),
                sector=(r.get("sector") or "Unknown"),
                rating=r.get("rating"),
                composite=_to_float(r.get("composite_score")),
                confidence=_to_float(r.get("confidence_score")),
                quality=_to_float(r.get("quality_score")),
                growth=_to_float(r.get("growth_score")),
                value=_to_float(r.get("value_score")),
                momentum=_to_float(r.get("momentum_score")),
                risk=_to_float(r.get("risk_score")),
                quality_pct=_to_float(r.get("quality_pct")),
                growth_pct=_to_float(r.get("growth_pct")),
                value_pct=_to_float(r.get("value_pct")),
                momentum_pct=_to_float(r.get("momentum_pct")),
                risk_pct=_to_float(r.get("risk_pct")),
                composite_pct=_to_float(r.get("percentile_composite")),
                top_decile=bool(r.get("top_decile", False)),
                top_quartile=bool(r.get("top_quartile", False)),
            )
        )

    st.session_state.rank_rows = ranked
    return ranked


def sector_leaderboards(
    rows: List[RankedRow], top_n: int = 10
) -> Dict[str, List[RankedRow]]:

    buckets: Dict[str, List[RankedRow]] = {}

    for r in rows:
        sector = (r.sector or "Unknown").strip()
        buckets.setdefault(sector, []).append(r)

    for sector, items in buckets.items():
        items.sort(
            key=lambda x: (
                x.composite_pct if x.composite_pct is not None else (
                    x.composite if x.composite is not None else -1e18
                )
            ),
            reverse=True,
        )
        buckets[sector] = items[:top_n]

    ordered = dict(
        sorted(
            buckets.items(),
            key=lambda kv: (
                kv[1][0].composite_pct if kv[1] and kv[1][0].composite_pct is not None
                else (
                    kv[1][0].composite if kv[1] and kv[1][0].composite is not None else -1e18
                )
            ),
            reverse=True,
        )
    )

    return ordered


def build_percentile_rankings(
    db,
    tenant_id: str,
    symbols: Optional[List[str]] = None,
    min_confidence: float = 0.0,
    sector_relative: bool = False,
) -> pd.DataFrame:
    df = get_latest_snapshots_df(db, tenant_id)

    if df is None or df.empty:
        return pd.DataFrame()

    if "symbol" not in df.columns:
        return pd.DataFrame()

    df["symbol"] = df["symbol"].astype(str).str.upper()

    if symbols:
        syms = [str(s).strip().upper() for s in symbols if s and str(s).strip()]
        if syms:
            df = df[df["symbol"].isin(syms)].copy()

    if df.empty:
        return pd.DataFrame()

    numeric_cols = [
        "quality_score",
        "growth_score",
        "value_score",
        "momentum_score",
        "risk_score",
        "composite_score",
        "confidence_score",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "confidence_score" in df.columns:
        df = df[
            df["confidence_score"].isna()
            | (df["confidence_score"] >= float(min_confidence))
        ].copy()

    if df.empty:
        return pd.DataFrame()

    df = _apply_percentiles(df, sector_relative=sector_relative)

    df = df.sort_values(
        by=["percentile_composite", "confidence_score", "composite_score"],
        ascending=[False, False, False],
        na_position="last",
    ).reset_index(drop=True)

    df["rank"] = range(1, len(df) + 1)

    preferred = [
        "rank",
        "symbol",
        "sector",
        "rating",
        "percentile_composite",
        "top_decile",
        "top_quartile",
        "quality_pct",
        "growth_pct",
        "value_pct",
        "momentum_pct",
        "risk_pct",
        "composite_pct_raw",
        "confidence_score",
        "quality_score",
        "growth_score",
        "value_score",
        "momentum_score",
        "risk_score",
        "composite_score",
    ]

    existing = [c for c in preferred if c in df.columns]
    return df[existing]