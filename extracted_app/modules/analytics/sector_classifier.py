"""
Automated sector classification.

Converts SEC SIC industry strings into normalized sectors.
Handles funds, REITs, ETFs, and operating companies.
"""

import re


TECH_KEYWORDS = [
    "SOFTWARE",
    "COMPUTER",
    "SEMICONDUCTOR",
    "DATA PROCESSING",
    "PROGRAMMING",
    "COMMUNICATIONS EQUIPMENT",
]

HEALTH_KEYWORDS = [
    "PHARMACEUTICAL",
    "BIOLOGICAL",
    "MEDICAL",
    "SURGICAL",
    "DIAGNOSTIC",
    "LABORATORIES",
]

FINANCIAL_KEYWORDS = [
    "BANK",
    "FINANCE",
    "INSURANCE",
    "BROKER",
    "INVESTMENT",
    "CREDIT",
]

ENERGY_KEYWORDS = [
    "PETROLEUM",
    "OIL",
    "NATURAL GAS",
    "DRILLING",
]

MATERIALS_KEYWORDS = [
    "MINING",
    "ORES",
    "CHEMICAL",
    "METAL",
    "STEEL",
]

INDUSTRIAL_KEYWORDS = [
    "MACHINERY",
    "AIRCRAFT",
    "CONSTRUCTION",
    "EQUIPMENT",
    "TRANSPORTATION",
]

REAL_ESTATE_KEYWORDS = [
    "REAL ESTATE",
    "REIT",
]

UTILITIES_KEYWORDS = [
    "ELECTRIC",
    "GAS",
    "WATER",
]

CONSUMER_KEYWORDS = [
    "RETAIL",
    "FOOD",
    "APPAREL",
    "HOTELS",
    "RESTAURANTS",
]

COMM_KEYWORDS = [
    "TELEPHONE",
    "BROADCASTING",
    "COMMUNICATION",
]


def _contains_any(text: str, keywords):

    for k in keywords:
        if k in text:
            return True

    return False


def classify_sector(raw_sector: str, symbol: str = None) -> str:
    """
    Normalize SIC sector strings to modern market sectors.
    """

    if not raw_sector:
        return "Other"

    s = raw_sector.upper()

    if _contains_any(s, TECH_KEYWORDS):
        return "Technology"

    if _contains_any(s, HEALTH_KEYWORDS):
        return "Healthcare"

    if _contains_any(s, FINANCIAL_KEYWORDS):
        return "Financials"

    if _contains_any(s, ENERGY_KEYWORDS):
        return "Energy"

    if _contains_any(s, MATERIALS_KEYWORDS):
        return "Materials"

    if _contains_any(s, INDUSTRIAL_KEYWORDS):
        return "Industrials"

    if _contains_any(s, REAL_ESTATE_KEYWORDS):
        return "Real Estate"

    if _contains_any(s, UTILITIES_KEYWORDS):
        return "Utilities"

    if _contains_any(s, CONSUMER_KEYWORDS):
        return "Consumer"

    if _contains_any(s, COMM_KEYWORDS):
        return "Communication Services"

    # fallback
    return "Other"