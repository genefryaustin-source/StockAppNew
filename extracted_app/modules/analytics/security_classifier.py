from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class SecurityProfile:
    asset_type: str
    normalized_sector: str
    use_fundamentals: bool
    skip_symbol: bool
    reason: Optional[str] = None


BAD_SUFFIXES = (
    ".W", ".WS", ".WT",
    ".U", ".R", ".P",
)


ETF_KEYWORDS = [
    "ETF",
    "EXCHANGE TRADED FUND",
    "INDEX FUND",
]

FUND_KEYWORDS = [
    "CLOSED-END",
    "CLOSED END",
    "FUND",
    "INCOME TRUST",
    "ASSET-BACKED SECURITIES",
]

REIT_KEYWORDS = [
    "REIT",
    "REAL ESTATE INVESTMENT TRUST",
]

ADR_KEYWORDS = [
    "ADR",
    "AMERICAN DEPOSITARY RECEIPT",
]

MINER_EXPLORER_KEYWORDS = [
    "GOLD AND SILVER ORES",
    "METAL MINING",
    "MISCELLANEOUS METAL ORES",
    "MINING",
    "ORES",
]


def _contains_any(text: str, keywords: list[str]) -> bool:
    text = (text or "").upper()
    return any(k in text for k in keywords)


def classify_security(
    symbol: str,
    raw_sector: Optional[str],
    normalized_sector: str,
) -> SecurityProfile:

    symbol = (symbol or "").strip().upper()
    raw = (raw_sector or "").strip().upper()
    norm = (normalized_sector or "Other").strip()

    # hard skip structured / problematic instruments
    for suf in BAD_SUFFIXES:
        if symbol.endswith(suf):
            return SecurityProfile(
                asset_type="Structured",
                normalized_sector="Other",
                use_fundamentals=False,
                skip_symbol=True,
                reason=f"suffix {suf}",
            )

    if "/" in symbol:
        return SecurityProfile(
            asset_type="Structured",
            normalized_sector="Other",
            use_fundamentals=False,
            skip_symbol=True,
            reason="slash ticker",
        )

    # REITs
    if _contains_any(raw, REIT_KEYWORDS) or norm == "Real Estate":
        return SecurityProfile(
            asset_type="REIT",
            normalized_sector="Real Estate",
            use_fundamentals=True,
            skip_symbol=False,
        )

    # ETFs
    if _contains_any(raw, ETF_KEYWORDS):
        return SecurityProfile(
            asset_type="ETF",
            normalized_sector="Funds",
            use_fundamentals=False,
            skip_symbol=False,
        )

    # closed-end funds / funds
    if _contains_any(raw, FUND_KEYWORDS):
        return SecurityProfile(
            asset_type="Fund",
            normalized_sector="Funds",
            use_fundamentals=False,
            skip_symbol=False,
        )

    # ADRs
    if _contains_any(raw, ADR_KEYWORDS):
        return SecurityProfile(
            asset_type="ADR",
            normalized_sector=norm,
            use_fundamentals=True,
            skip_symbol=False,
        )

    # miners / explorers often have sparse fundamentals
    if _contains_any(raw, MINER_EXPLORER_KEYWORDS):
        return SecurityProfile(
            asset_type="Miner",
            normalized_sector="Materials",
            use_fundamentals=False,
            skip_symbol=False,
        )

    # fallback: regular operating company
    return SecurityProfile(
        asset_type="Equity",
        normalized_sector=norm,
        use_fundamentals=True,
        skip_symbol=False,
    )