# ============================================================
# modules/preipo/ipo_intelligence_engine.py
# IPO Intelligence Engine
# ============================================================

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd


IPO_STAGE_WEIGHTS = {
    "424B4": 95.0,
    "424B3": 88.0,
    "424B1": 84.0,
    "S-1/A": 74.0,
    "F-1/A": 74.0,
    "S-1": 62.0,
    "F-1": 62.0,
    "S-4/A": 50.0,
    "S-4": 44.0,
}

STAGE_ORDER = [
    "Initial Registration",
    "Amendment / Roadshow Prep",
    "Pricing / Prospectus Stage",
    "SPAC / Merger Registration",
    "Early Signal",
]

SECTOR_KEYWORDS = {
    "AI / Software": [
        "AI", "ARTIFICIAL INTELLIGENCE", "MACHINE LEARNING", "SOFTWARE",
        "CLOUD", "DATA", "ANALYTICS", "SAAS", "PLATFORM", "DIGITAL",
        "AUTOMATION", "APPLICATION", "TECHNOLOGY", "SYSTEMS",
    ],
    "Cybersecurity": [
        "CYBER", "SECURITY", "IDENTITY", "ZERO TRUST", "THREAT",
        "ENDPOINT", "RANSOMWARE", "NETWORK SECURITY",
    ],
    "Fintech": [
        "FINTECH", "PAYMENT", "PAYMENTS", "BANK", "BANKING", "LENDING",
        "CREDIT", "INSURANCE", "BROKERAGE", "WALLET", "BLOCKCHAIN",
        "CAPITAL", "FINANCIAL", "MORTGAGE", "EXCHANGE",
    ],
    "Healthcare / Biotech": [
        "HEALTH", "BIOTECH", "BIOPHARMA", "PHARMA", "MEDICAL",
        "THERAPEUTICS", "DIAGNOSTICS", "CLINICAL", "HOSPITAL",
        "LIFE SCIENCES", "PHARMACEUTICAL",
    ],
    "Defense / GovTech": [
        "DEFENSE", "GOVERNMENT", "AEROSPACE", "SATELLITE",
        "INTELLIGENCE", "PUBLIC SECTOR", "NATIONAL SECURITY",
    ],
    "Semiconductors": [
        "SEMICONDUCTOR", "CHIP", "ASIC", "GPU", "SILICON",
        "MICROELECTRONICS", "PHOTONICS",
    ],
    "Energy / Climate": [
        "ENERGY", "SOLAR", "BATTERY", "HYDROGEN", "OIL", "GAS",
        "RENEWABLE", "NUCLEAR", "CARBON", "CLIMATE", "POWER",
    ],
    "Consumer / Marketplace": [
        "MARKETPLACE", "CONSUMER", "RETAIL", "COMMERCE", "FOOD",
        "BRAND", "MEDIA", "ENTERTAINMENT", "GAMING", "RESTAURANT",
    ],
    "Industrial / Infrastructure": [
        "INDUSTRIAL", "MANUFACTURING", "LOGISTICS", "SUPPLY CHAIN",
        "TRANSPORTATION", "INFRASTRUCTURE", "CONSTRUCTION", "MATERIALS",
    ],
    "Financial / SPAC": [
        "ACQUISITION", "SPAC", "BLANK CHECK", "HOLDINGS", "CAPITAL",
        "BANCORP", "BANK", "TRUST",
    ],
}

SPAC_KEYWORDS = [
    "ACQUISITION CORP",
    "ACQUISITION CORPORATION",
    "ACQUISITION COMPANY",
    "SPECIAL PURPOSE ACQUISITION",
    "BLANK CHECK",
    "SPAC",
]

TOP_TIER_UNDERWRITERS = [
    "GOLDMAN SACHS",
    "MORGAN STANLEY",
    "J.P. MORGAN",
    "JP MORGAN",
    "JPMORGAN",
    "BOFA",
    "BANK OF AMERICA",
    "CITI",
    "CITIGROUP",
    "BARCLAYS",
    "DEUTSCHE BANK",
    "UBS",
    "JEFFERIES",
    "WELLS FARGO",
    "EVERCORE",
    "PIPER SANDLER",
    "RBC",
    "RAYMOND JAMES",
    "WILLIAM BLAIR",
    "CANTOR",
    "TD COWEN",
]


@dataclass
class IPOIntelligenceResult:
    company: str
    form: str
    filing_date: Any
    ipo_probability: float
    ipo_opportunity_score: float
    ipo_maturity_stage: str
    timeline_estimate: str
    sector: str
    spac_classification: str
    underwriters: str
    underwriter_strength: float
    signal_summary: str


def _upper(value: Any) -> str:
    return str(value or "").upper().strip()


def _first(row: Dict[str, Any], keys: Iterable[str], default: Any = None) -> Any:
    for key in keys:
        if key in row and row.get(key) not in (None, ""):
            return row.get(key)
    return default


def _parse_date(value: Any) -> Optional[pd.Timestamp]:
    try:
        if value is None or value == "":
            return None
        dt = pd.to_datetime(value, errors="coerce")
        if pd.isna(dt):
            return None
        if getattr(dt, "tzinfo", None) is None:
            return dt.tz_localize("UTC")
        return dt.tz_convert("UTC")
    except Exception:
        return None


def _age_days(value: Any) -> Optional[int]:
    dt = _parse_date(value)
    if dt is None:
        return None
    return max(0, int((pd.Timestamp.now(tz="UTC") - dt).days))


def infer_sector(company_name: Any, raw_text: Any = None) -> str:
    text = f"{company_name or ''} {raw_text or ''}".upper()
    for sector, keywords in SECTOR_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return sector
    return "Unclassified"


def classify_spac(company_name: Any, form: Any = None, raw_text: Any = None, is_spac: Any = False) -> str:
    text = f"{company_name or ''} {form or ''} {raw_text or ''}".upper()
    form_text = _upper(form)
    if bool(is_spac):
        return "SPAC / Blank Check"
    if any(keyword in text for keyword in SPAC_KEYWORDS):
        return "SPAC Signal"
    if form_text in {"S-4", "S-4/A"}:
        return "Merger / Registration"
    return "Traditional IPO"


def extract_underwriters(text: Any) -> List[str]:
    haystack = _upper(text)
    found = []
    for bank in TOP_TIER_UNDERWRITERS:
        if bank in haystack and bank not in found:
            found.append(bank)
    return found


def compute_underwriter_strength(underwriters: List[str]) -> float:
    if not underwriters:
        return 0.0
    score = 35.0 + min(len(underwriters), 5) * 12.0
    if any(bank in {"GOLDMAN SACHS", "MORGAN STANLEY", "J.P. MORGAN", "JP MORGAN", "JPMORGAN"} for bank in underwriters):
        score += 20.0
    return min(round(score, 1), 100.0)


def compute_maturity_stage(form: Any, is_spac: Any = False) -> str:
    form_text = _upper(form)
    if form_text in {"424B4", "424B3", "424B1"}:
        return "Pricing / Prospectus Stage"
    if form_text in {"S-1/A", "F-1/A"}:
        return "Amendment / Roadshow Prep"
    if form_text in {"S-1", "F-1"}:
        return "Initial Registration"
    if bool(is_spac) or form_text in {"S-4", "S-4/A"}:
        return "SPAC / Merger Registration"
    return "Early Signal"


def compute_ipo_probability(row: Dict[str, Any]) -> float:
    form = _upper(_first(row, ["Form", "filing_type", "SEC Filing"], ""))
    filing_date = _first(row, ["Filing Date", "filing_date", "latest_sec_filing_date"])
    is_spac = bool(_first(row, ["SPAC", "is_spac"], False))
    raw = _first(row, ["raw_payload", "Raw", "Source"], "")
    company = _first(row, ["Company", "company_name"], "")

    score = IPO_STAGE_WEIGHTS.get(form, 25.0)

    age = _age_days(filing_date)
    if age is not None:
        if age <= 14:
            score += 12
        elif age <= 45:
            score += 8
        elif age <= 90:
            score += 4
        elif age > 180:
            score -= 8

    if is_spac or "SPAC" in classify_spac(company, form, raw, is_spac):
        score += 4

    return max(0.0, min(round(score, 1), 100.0))


def compute_timeline_estimate(form: Any, filing_date: Any, probability: float) -> str:
    form_text = _upper(form)
    age = _age_days(filing_date)

    if form_text in {"424B4", "424B3", "424B1"}:
        return "0-30 days / pricing stage"
    if form_text in {"S-1/A", "F-1/A"}:
        return "30-90 days" if age is not None and age <= 45 else "1-2 quarters"
    if form_text in {"S-1", "F-1"}:
        return "1-2 quarters" if probability >= 70 else "2-4 quarters"
    if form_text in {"S-4", "S-4/A"}:
        return "Deal-dependent / merger timeline"
    return "Watchlist only"


def compute_ipo_opportunity_score(row: Dict[str, Any]) -> float:
    probability = compute_ipo_probability(row)
    company = _first(row, ["Company", "company_name"], "")
    form = _first(row, ["Form", "filing_type", "SEC Filing"], "")
    filing_date = _first(row, ["Filing Date", "filing_date", "latest_sec_filing_date"])
    raw = _first(row, ["raw_payload", "Raw", "Source"], "")
    is_spac = bool(_first(row, ["SPAC", "is_spac"], False))

    sector = infer_sector(company, raw)
    spac = classify_spac(company, form, raw, is_spac)
    underwriters = extract_underwriters(f"{company} {raw}")
    uw_strength = compute_underwriter_strength(underwriters)

    score = probability * 0.68
    score += uw_strength * 0.12
    if sector != "Unclassified":
        score += 8
    if "SPAC" in spac:
        score += 4

    age = _age_days(filing_date)
    if age is not None and age <= 30:
        score += 8
    elif age is not None and age <= 90:
        score += 4

    return max(0.0, min(round(score, 1), 100.0))


def analyze_preipo_row(row: Dict[str, Any]) -> Dict[str, Any]:
    company = _first(row, ["Company", "company_name"], "Unknown")
    form = _first(row, ["Form", "filing_type", "SEC Filing"], "")
    filing_date = _first(row, ["Filing Date", "filing_date", "latest_sec_filing_date"])
    raw = _first(row, ["raw_payload", "Raw", "Source"], "")
    is_spac = bool(_first(row, ["SPAC", "is_spac"], False))

    probability = compute_ipo_probability(row)
    opportunity = compute_ipo_opportunity_score(row)
    sector = infer_sector(company, raw)
    spac = classify_spac(company, form, raw, is_spac)
    underwriters = extract_underwriters(f"{company} {raw}")
    uw_strength = compute_underwriter_strength(underwriters)
    stage = compute_maturity_stage(form, is_spac)
    timeline = compute_timeline_estimate(form, filing_date, probability)

    summary = " | ".join(
        part for part in [
            stage,
            timeline,
            sector if sector != "Unclassified" else "",
            spac,
            "Tier-1 underwriter signal" if underwriters else "",
        ]
        if part
    )

    return asdict(
        IPOIntelligenceResult(
            company=str(company or "Unknown"),
            form=str(form or ""),
            filing_date=filing_date,
            ipo_probability=probability,
            ipo_opportunity_score=opportunity,
            ipo_maturity_stage=stage,
            timeline_estimate=timeline,
            sector=sector,
            spac_classification=spac,
            underwriters=", ".join(underwriters),
            underwriter_strength=uw_strength,
            signal_summary=summary,
        )
    )


def enrich_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df is None:
        return pd.DataFrame()
    if df.empty:
        return df

    out = df.copy()
    rows = [analyze_preipo_row(row.to_dict()) for _, row in out.iterrows()]
    intel = pd.DataFrame(rows)

    mapping = {
        "ipo_probability": "IPO Probability",
        "ipo_opportunity_score": "IPO Opportunity Score",
        "ipo_maturity_stage": "IPO Maturity Stage",
        "timeline_estimate": "Timeline Estimate",
        "sector": "Sector",
        "spac_classification": "SPAC Classification",
        "underwriters": "Underwriters",
        "underwriter_strength": "Underwriter Strength",
        "signal_summary": "Signal Summary",
    }

    for src, dst in mapping.items():
        out[dst] = intel[src] if src in intel.columns else None

    if "IPO Opportunity Score" in out.columns and "IPO Probability" in out.columns:
        out = out.sort_values(["IPO Opportunity Score", "IPO Probability"], ascending=[False, False])

    return out.reset_index(drop=True)


def top_candidates(df: pd.DataFrame, limit: int = 25, min_probability: float = 0.0) -> pd.DataFrame:
    enriched = enrich_dataframe(df)
    if enriched.empty:
        return enriched

    if "IPO Probability" in enriched.columns:
        enriched = enriched[pd.to_numeric(enriched["IPO Probability"], errors="coerce").fillna(0) >= float(min_probability)]

    cols = [
        "Company",
        "Form",
        "Filing Date",
        "IPO Probability",
        "IPO Opportunity Score",
        "IPO Maturity Stage",
        "Timeline Estimate",
        "Sector",
        "SPAC Classification",
        "Underwriters",
        "SEC Link",
    ]
    cols = [col for col in cols if col in enriched.columns]
    return enriched[cols].head(limit).reset_index(drop=True)


def intelligence_metrics(df: pd.DataFrame) -> Dict[str, Any]:
    enriched = enrich_dataframe(df)
    if enriched.empty:
        return {
            "total_candidates": 0,
            "avg_probability": 0.0,
            "highest_probability": 0.0,
            "near_term": 0,
            "pricing_stage": 0,
            "spac": 0,
            "tier1_underwriters": 0,
            "top_sector": "N/A",
        }

    probability = pd.to_numeric(enriched.get("IPO Probability"), errors="coerce").fillna(0)
    stage = enriched.get("IPO Maturity Stage", pd.Series(dtype=str)).fillna("").astype(str)
    spac = enriched.get("SPAC Classification", pd.Series(dtype=str)).fillna("").astype(str)
    underwriters = enriched.get("Underwriters", pd.Series(dtype=str)).fillna("").astype(str)
    sector = enriched.get("Sector", pd.Series(dtype=str)).fillna("Unclassified").astype(str)

    sector_counts = sector[sector != "Unclassified"].value_counts()
    top_sector = sector_counts.index[0] if not sector_counts.empty else "N/A"

    return {
        "total_candidates": int(len(enriched)),
        "avg_probability": round(float(probability.mean()), 1),
        "highest_probability": round(float(probability.max()), 1),
        "near_term": int((probability >= 70).sum()),
        "pricing_stage": int(stage.str.contains("Pricing", case=False, na=False).sum()),
        "spac": int(spac.str.contains("SPAC", case=False, na=False).sum()),
        "tier1_underwriters": int((underwriters.str.len() > 0).sum()),
        "top_sector": top_sector,
    }


def sector_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    enriched = enrich_dataframe(df)
    if enriched.empty or "Sector" not in enriched.columns:
        return pd.DataFrame(columns=["Sector", "Count"])
    out = enriched["Sector"].fillna("Unclassified").astype(str).value_counts().reset_index()
    out.columns = ["Sector", "Count"]
    return out


def maturity_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    enriched = enrich_dataframe(df)
    if enriched.empty or "IPO Maturity Stage" not in enriched.columns:
        return pd.DataFrame(columns=["Stage", "Count"])
    out = enriched["IPO Maturity Stage"].fillna("Unknown").astype(str).value_counts().reset_index()
    out.columns = ["Stage", "Count"]
    return out


def probability_distribution(df: pd.DataFrame) -> pd.DataFrame:
    enriched = enrich_dataframe(df)
    if enriched.empty or "IPO Probability" not in enriched.columns:
        return pd.DataFrame(columns=["Range", "Count"])

    probs = pd.to_numeric(enriched["IPO Probability"], errors="coerce").fillna(0)
    bins = [0, 50, 60, 70, 80, 90, 101]
    labels = ["0-49", "50-59", "60-69", "70-79", "80-89", "90-100"]
    bucket = pd.cut(probs, bins=bins, labels=labels, include_lowest=True, right=False)
    out = bucket.value_counts().reindex(labels, fill_value=0).reset_index()
    out.columns = ["Range", "Count"]
    return out


def pipeline_funnel(df: pd.DataFrame) -> pd.DataFrame:
    enriched = enrich_dataframe(df)
    if enriched.empty:
        return pd.DataFrame(columns=["Stage", "Count"])

    form = enriched.get("Form", pd.Series(dtype=str)).fillna("").astype(str).str.upper()

    rows = [
        {"Stage": "S-1 / F-1 Filed", "Count": int(form.isin(["S-1", "F-1"]).sum())},
        {"Stage": "Amended S-1 / F-1", "Count": int(form.isin(["S-1/A", "F-1/A"]).sum())},
        {"Stage": "424B Prospectus", "Count": int(form.isin(["424B1", "424B3", "424B4"]).sum())},
        {"Stage": "Pricing Stage", "Count": int(form.isin(["424B4"]).sum())},
    ]
    return pd.DataFrame(rows)


def underwriter_leaderboard(df: pd.DataFrame) -> pd.DataFrame:
    enriched = enrich_dataframe(df)
    if enriched.empty or "Underwriters" not in enriched.columns:
        return pd.DataFrame(columns=["Underwriter", "Count"])

    counts: Dict[str, int] = {}
    for value in enriched["Underwriters"].fillna("").astype(str):
        for bank in [part.strip() for part in value.split(",") if part.strip()]:
            counts[bank] = counts.get(bank, 0) + 1

    if not counts:
        return pd.DataFrame(columns=["Underwriter", "Count"])

    return pd.DataFrame(
        [{"Underwriter": key, "Count": value} for key, value in counts.items()]
    ).sort_values("Count", ascending=False).reset_index(drop=True)
