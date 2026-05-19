# modules/utils/symbol_utils.py

from __future__ import annotations

import re


# ---------------------------------------------------------
# BASIC VALIDATION
# ---------------------------------------------------------

def is_valid_symbol(symbol: str) -> bool:
    """
    Basic ticker validation.
    Filters out obvious bad entries.
    """
    if not symbol:
        return False

    symbol = symbol.strip().upper()

    # Typical tickers 1–6 characters
    if len(symbol) > 8:
        return False

    # Allow letters numbers . -
    if not re.match(r"^[A-Z0-9.\-]+$", symbol):
        return False

    return True


# ---------------------------------------------------------
# NORMALIZATION
# ---------------------------------------------------------

def normalize_symbol(symbol: str) -> str:
    """
    Normalize symbol into canonical format used internally.
    """
    if not symbol:
        return ""

    symbol = symbol.strip().upper()

    # Remove spaces
    symbol = symbol.replace(" ", "")

    return symbol


# ---------------------------------------------------------
# PROVIDER FORMATTING
# ---------------------------------------------------------

def symbol_for_provider(symbol: str, provider: str) -> str:
    """
    Convert symbol into format expected by a provider.
    """

    symbol = normalize_symbol(symbol)

    provider = provider.lower()

    # Yahoo uses dash for share classes
    if provider == "yahoo":
        return symbol.replace(".", "-")

    # Massive (Polygon) uses dot format
    if provider == "massive":
        return symbol

    # TwelveData
    if provider == "twelvedata":
        return symbol.replace(".", "-")

    # FMP
    if provider == "fmp":
        return symbol.replace(".", "-")

    return symbol


# ---------------------------------------------------------
# CLEAN SYMBOL LIST
# ---------------------------------------------------------

def clean_symbol_list(symbols):
    """
    Clean and deduplicate symbol list.
    """

    out = []

    for s in symbols:

        s = normalize_symbol(s)

        if not is_valid_symbol(s):
            continue

        out.append(s)

    return sorted(set(out))