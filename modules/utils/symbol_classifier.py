"""
modules/utils/symbol_classifier.py
"""

from __future__ import annotations


# ---------------------------------------------------
# COMMON BAD / NON-EQUITY SUFFIXES
# ---------------------------------------------------

BAD_SUFFIXES = (

    # warrants
    "W",
    "WS",

    # rights
    "R",

    # units
    "U",

    # preferred variants
    "P",

    # odd OTC endings
    "Z",
)


# ---------------------------------------------------
# KNOWN INVALID SYMBOLS
# ---------------------------------------------------

KNOWN_BAD = {

    "",
    "N/A",
    "NONE",
    "NULL",
    "TEST",
    "UNKNOWN",
}


# ---------------------------------------------------
# BASIC SYMBOL SANITIZATION
# ---------------------------------------------------

def normalize_symbol(symbol: str) -> str:

    if symbol is None:
        return ""

    symbol = str(symbol).strip().upper()

    return symbol


# ---------------------------------------------------
# COMMON EQUITY VALIDATION
# ---------------------------------------------------

def is_supported_common_equity(
    symbol: str,
) -> bool:

    symbol = normalize_symbol(symbol)

    if not symbol:
        return False

    # -----------------------------------
    # Known invalid
    # -----------------------------------

    if symbol in KNOWN_BAD:
        return False

    # -----------------------------------
    # Length sanity
    # -----------------------------------

    if len(symbol) > 6:
        return False

    # -----------------------------------
    # OTC / warrants / rights / units
    # -----------------------------------

    # -----------------------------------
    # Warrants / rights / units
    # ONLY for long OTC-style symbols
    # -----------------------------------

    #bad_patterns = (

        #"WS",
        #"WT",
        #"WARRANT",
    #)

    #for pat in bad_patterns:

        #if symbol.endswith(pat):
            #return False

    # -----------------------------------
    # OTC-style long suffix filtering
    # -----------------------------------

    if len(symbol) >= 5:

        otc_suffixes = (
            "W",
            "R",
            "U",
            "P",
            "Z",
        )

        if symbol.endswith(otc_suffixes):

            # avoid filtering legit:
            # PLTR
            # SPYR
            # etc.

            if "." not in symbol:
                return False

    # -----------------------------------
    # Numeric symbols
    # -----------------------------------

    if symbol.isdigit():
        return False

    # -----------------------------------
    # Invalid chars
    # -----------------------------------

    allowed = set(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ.-"
    )

    if any(c not in allowed for c in symbol):
        return False

    return True


# ---------------------------------------------------
# BULK FILTER
# ---------------------------------------------------

def filter_supported_equities(
    symbols,
):

    out = []

    for s in symbols:

        s = normalize_symbol(s)

        if is_supported_common_equity(s):

            out.append(s)

    return sorted(set(out))