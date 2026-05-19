# ============================================================
# FACTOR MODEL – Institutional Phase 4.1
# Sector-aware normalization + confidence + coverage
# ============================================================

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Tuple


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, float(x)))


def _linear_score(value: Optional[float], lo: float, hi: float, higher_is_better: bool = True) -> Optional[float]:
    if value is None:
        return None
    if lo == hi:
        return 50.0

    v = float(value)

    if higher_is_better:
        if v <= lo:
            return 0.0
        if v >= hi:
            return 100.0
        return 100.0 * (v - lo) / (hi - lo)
    else:
        # lower is better
        if v <= lo:
            return 100.0
        if v >= hi:
            return 0.0
        return 100.0 * (hi - v) / (hi - lo)


def _avg(*vals: Optional[float]) -> Optional[float]:
    xs = [v for v in vals if v is not None]
    if not xs:
        return None
    return float(sum(xs) / len(xs))


# ------------------------------------------------------------
# Sector bands (broad, deterministic, not “guessy”)
# You can expand these later with real peer percentiles.
# ------------------------------------------------------------

DEFAULT_BANDS = {
    "quality": {
        "gross_margin": (0.20, 0.60, True),
        "op_margin": (0.00, 0.30, True),
        "fcf_margin": (0.00, 0.25, True),
    },
    "growth": {
        "revenue_cagr_3y": (-0.05, 0.40, True),
    },
    "value": {
        "pe_ttm": (10.0, 40.0, False),
        "ps_ttm": (2.0, 15.0, False),
        "ev_ebitda": (6.0, 25.0, False),
    },
    "momentum": {
        "rsi": (30.0, 70.0, True),
    }
}

SECTOR_BANDS: Dict[str, Dict[str, Dict[str, Tuple[float, float, bool]]]] = {
    # Tech tends to have higher margins and P/S
    "Technology": {
        "quality": {
            "gross_margin": (0.25, 0.70, True),
            "op_margin": (0.00, 0.35, True),
            "fcf_margin": (0.00, 0.30, True),
        },
        "growth": {
            "revenue_cagr_3y": (-0.05, 0.45, True),
        },
        "value": {
            "pe_ttm": (15.0, 55.0, False),
            "ps_ttm": (3.0, 20.0, False),
            "ev_ebitda": (10.0, 35.0, False),
        },
        "momentum": {"rsi": (30.0, 70.0, True)},
    },
    # Financials: lower margins/P-S, lower PE bands typically
    "Financial Services": {
        "quality": {
            "gross_margin": (0.15, 0.45, True),
            "op_margin": (0.00, 0.25, True),
            "fcf_margin": (0.00, 0.20, True),
        },
        "growth": {"revenue_cagr_3y": (-0.05, 0.25, True)},
        "value": {
            "pe_ttm": (6.0, 20.0, False),
            "ps_ttm": (1.0, 6.0, False),
            "ev_ebitda": (5.0, 18.0, False),
        },
        "momentum": {"rsi": (30.0, 70.0, True)},
    },
    # Energy: cyclicals; lower PE/EV bands; margins can be volatile
    "Energy": {
        "quality": {
            "gross_margin": (0.10, 0.40, True),
            "op_margin": (-0.05, 0.20, True),
            "fcf_margin": (-0.05, 0.20, True),
        },
        "growth": {"revenue_cagr_3y": (-0.10, 0.30, True)},
        "value": {
            "pe_ttm": (5.0, 18.0, False),
            "ps_ttm": (0.8, 4.0, False),
            "ev_ebitda": (3.0, 12.0, False),
        },
        "momentum": {"rsi": (30.0, 70.0, True)},
    },
}


def bands_for_sector(sector: Optional[str]) -> dict:
    if sector and sector in SECTOR_BANDS:
        return SECTOR_BANDS[sector]
    return DEFAULT_BANDS


@dataclass
class FactorInputs:
    sector: Optional[str]

    gross_margin: Optional[float]
    op_margin: Optional[float]
    fcf_margin: Optional[float]

    revenue_cagr_3y: Optional[float]

    pe_ttm: Optional[float]
    ps_ttm: Optional[float]
    ev_ebitda: Optional[float]

    trend: Optional[str]
    rsi_14: Optional[float]
    sma_50: Optional[float]
    sma_200: Optional[float]

    risk_score: Optional[float]


@dataclass
class FactorScores:
    quality_score: Optional[float]
    growth_score: Optional[float]
    value_score: Optional[float]
    momentum_score: Optional[float]
    risk_penalty: Optional[float]
    composite_score: Optional[float]
    data_coverage: float
    confidence_score: float
    composite_notes: str


def score_quality(inp: FactorInputs, bands: dict) -> Optional[float]:
    qm = bands.get("quality", {})
    gm = _linear_score(inp.gross_margin, *qm.get("gross_margin", DEFAULT_BANDS["quality"]["gross_margin"]))
    om = _linear_score(inp.op_margin, *qm.get("op_margin", DEFAULT_BANDS["quality"]["op_margin"]))
    fm = _linear_score(inp.fcf_margin, *qm.get("fcf_margin", DEFAULT_BANDS["quality"]["fcf_margin"]))
    return _avg(gm, om, fm)


def score_growth(inp: FactorInputs, bands: dict) -> Optional[float]:
    gb = bands.get("growth", {})
    return _linear_score(inp.revenue_cagr_3y, *gb.get("revenue_cagr_3y", DEFAULT_BANDS["growth"]["revenue_cagr_3y"]))


def score_value(inp: FactorInputs, bands: dict) -> Optional[float]:
    vb = bands.get("value", {})
    pe = _linear_score(inp.pe_ttm, *vb.get("pe_ttm", DEFAULT_BANDS["value"]["pe_ttm"]))
    ps = _linear_score(inp.ps_ttm, *vb.get("ps_ttm", DEFAULT_BANDS["value"]["ps_ttm"]))
    ev = _linear_score(inp.ev_ebitda, *vb.get("ev_ebitda", DEFAULT_BANDS["value"]["ev_ebitda"]))
    return _avg(pe, ps, ev)


def score_momentum(inp: FactorInputs, bands: dict) -> Optional[float]:
    # trend bucket score
    trend_score = None
    if inp.trend == "Uptrend":
        trend_score = 85.0
    elif inp.trend == "Range":
        trend_score = 55.0
    elif inp.trend == "Downtrend":
        trend_score = 25.0

    mb = bands.get("momentum", {})
    rsi_score = _linear_score(inp.rsi_14, *mb.get("rsi", DEFAULT_BANDS["momentum"]["rsi"]))

    ma_score = None
    if inp.sma_50 is not None and inp.sma_200 is not None:
        if inp.sma_50 > inp.sma_200:
            ma_score = 70.0
        elif inp.sma_50 < inp.sma_200:
            ma_score = 30.0
        else:
            ma_score = 50.0

    return _avg(trend_score, rsi_score, ma_score)


def score_risk_penalty(inp: FactorInputs) -> Optional[float]:
    if inp.risk_score is None:
        return None
    return _clamp(inp.risk_score, 0.0, 100.0)


def _coverage(*vals: Optional[float]) -> float:
    total = len(vals)
    present = sum(1 for v in vals if v is not None)
    return present / total if total else 0.0


def composite(quality, growth, value, momentum, risk_penalty) -> tuple[Optional[float], str]:
    weights = {"quality": 0.25, "growth": 0.20, "value": 0.20, "momentum": 0.20}
    parts = {"quality": quality, "growth": growth, "value": value, "momentum": momentum}
    avail = {k: v for k, v in parts.items() if v is not None}
    if not avail:
        return None, "Insufficient factor inputs"

    denom = sum(weights[k] for k in avail.keys())
    score = 0.0
    for k, v in avail.items():
        score += (weights[k] / denom) * float(v)

    note = f"Reweighted across available factors: {', '.join(sorted(avail.keys()))}"

    if risk_penalty is not None:
        score = score - 0.15 * float(risk_penalty)
        note += "; risk penalty applied (15%)"

    return _clamp(score, 0.0, 100.0), note


def confidence_score(data_coverage: float, risk_penalty: Optional[float]) -> float:
    """
    Confidence = primarily data coverage, adjusted down if risk is high.
    Deterministic:
      base = coverage * 100
      adjustment: -0..15 based on risk_penalty
    """
    base = _clamp(data_coverage * 100.0, 0.0, 100.0)
    if risk_penalty is None:
        return base
    adj = (float(risk_penalty) / 100.0) * 15.0
    return _clamp(base - adj, 0.0, 100.0)


def run_factor_model(inp: FactorInputs) -> FactorScores:
    b = bands_for_sector(inp.sector)

    q = score_quality(inp, b)
    g = score_growth(inp, b)
    v = score_value(inp, b)
    m = score_momentum(inp, b)
    rp = score_risk_penalty(inp)

    comp, note = composite(q, g, v, m, rp)

    # Coverage uses key inputs that drive factors (not raw price series)
    coverage = _coverage(
        inp.gross_margin, inp.op_margin, inp.fcf_margin,
        inp.revenue_cagr_3y,
        inp.pe_ttm, inp.ps_ttm, inp.ev_ebitda,
        inp.rsi_14,
        inp.risk_score,
    )

    conf = confidence_score(coverage, rp)

    if inp.sector:
        note = f"Sector bands: {inp.sector}; {note}"
    else:
        note = f"Sector bands: Default; {note}"

    return FactorScores(
        quality_score=q,
        growth_score=g,
        value_score=v,
        momentum_score=m,
        risk_penalty=rp,
        composite_score=comp,
        data_coverage=float(coverage),
        confidence_score=float(conf),
        composite_notes=note,
    )