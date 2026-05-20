from __future__ import annotations

import re
from typing import Tuple


BAD_EXACT_SYMBOLS = {
    "TEST",
    "NTEST",
    "DUMMY",
    "FAKE",
}


BAD_SUFFIXES = [
    "WS",
    "RT",
    "P",
    "Z",
]


def normalize_symbol(symbol: str) -> str:

    if symbol is None:
        return ""

    return str(symbol).upper().strip()


def validate_symbol(symbol: str) -> Tuple[bool, str]:

    sym = normalize_symbol(symbol)

    if not sym:
        return False, "empty"

    if sym in BAD_EXACT_SYMBOLS:
        return False, "blacklisted_test_symbol"

    if len(sym) > 5:
        return False, "length_gt_5"

    if not re.match(r"^[A-Z]+$", sym):
        return False, "non_alpha_characters"

    for suffix in BAD_SUFFIXES:
        if sym.endswith(suffix):
            return False, f"bad_suffix_{suffix}"

    return True, "valid"


def is_valid_equity_symbol(symbol: str) -> bool:

    valid, _ = validate_symbol(symbol)

    return valid