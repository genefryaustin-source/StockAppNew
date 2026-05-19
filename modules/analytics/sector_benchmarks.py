# ============================================================
# modules/analytics/sector_benchmarks.py
# Sector valuation benchmarks (median estimates)
# ============================================================

SECTOR_VALUATION = {

    "Technology": {
        "pe": 37,
        "ps": 9,
        "ev_ebitda": 24
    },

    "Healthcare": {
        "pe": 28,
        "ps": 6,
        "ev_ebitda": 18
    },

    "Financials": {
        "pe": 15,
        "ps": 3,
        "ev_ebitda": 12
    },

    "Consumer Discretionary": {
        "pe": 25,
        "ps": 4,
        "ev_ebitda": 16
    },

    "Consumer Staples": {
        "pe": 22,
        "ps": 3,
        "ev_ebitda": 14
    },

    "Energy": {
        "pe": 12,
        "ps": 2,
        "ev_ebitda": 7
    },

    "Industrials": {
        "pe": 20,
        "ps": 3,
        "ev_ebitda": 14
    },

    "Materials": {
        "pe": 18,
        "ps": 2,
        "ev_ebitda": 10
    },

    "Utilities": {
        "pe": 19,
        "ps": 3,
        "ev_ebitda": 12
    },

    "Real Estate": {
        "pe": 35,
        "ps": 8,
        "ev_ebitda": 20
    },

    "Communication Services": {
        "pe": 24,
        "ps": 5,
        "ev_ebitda": 16
    },

    "Default": {
        "pe": 25,
        "ps": 4,
        "ev_ebitda": 15
    }
}


def get_sector_benchmarks(sector: str):
    if not sector:
        return SECTOR_VALUATION["Default"]

    return SECTOR_VALUATION.get(sector, SECTOR_VALUATION["Default"])