"""
modules/market/market_status.py

Market Status

NYSE session status (open/pre-market/after-hours/closed) and current
local times for major global market centers (New York, London, Tokyo,
Hong Kong).

Honesty note on holidays: this accounts for weekends and the fixed or
simply-computed US market holidays (New Year's Day, MLK Day,
Presidents Day, Juneteenth, Independence Day, Labor Day, Thanksgiving,
Christmas, Memorial Day). It does NOT compute Good Friday (which
requires an Easter-date algorithm) -- on that one day per year, this
will incorrectly report a session as open/pre-market/after-hours when
NYSE is actually closed. Flagged here rather than silently claiming
full holiday accuracy.
"""

from __future__ import annotations

from datetime import datetime, time, date
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo("America/New_York")

# Regular session bounds, Eastern time.
PREMARKET_START = time(4, 0)
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)
AFTERHOURS_END = time(20, 0)

GLOBAL_MARKET_CENTERS = {
    "New York": "America/New_York",
    "London": "Europe/London",
    "Tokyo": "Asia/Tokyo",
    "Hong Kong": "Asia/Hong_Kong",
}


def _nth_weekday_of_month(year: int, month: int, weekday: int, n: int) -> date:
    """weekday: Monday=0 ... Sunday=6. n=1 for 1st, n=-1 for last."""
    if n > 0:
        d = date(year, month, 1)
        count = 0
        while True:
            if d.weekday() == weekday:
                count += 1
                if count == n:
                    return d
            d = _add_day(d)
    else:
        # Last occurrence: start from the end of the month and walk back.
        if month == 12:
            d = date(year + 1, 1, 1)
        else:
            d = date(year, month + 1, 1)
        d = _add_day(d, -1)
        while d.weekday() != weekday:
            d = _add_day(d, -1)
        return d


def _add_day(d: date, delta: int = 1) -> date:
    from datetime import timedelta
    return d + timedelta(days=delta)


def _us_market_holidays(year: int) -> set[date]:
    """
    Fixed-date and rule-based US market holidays for a given year
    (excludes Good Friday -- see module docstring). Observed-date
    shifting (e.g. a fixed holiday landing on a weekend) is handled
    for the common cases.
    """
    def _observed(d: date) -> date:
        if d.weekday() == 5:  # Saturday -> observed Friday
            return _add_day(d, -1)
        if d.weekday() == 6:  # Sunday -> observed Monday
            return _add_day(d, 1)
        return d

    holidays = {
        _observed(date(year, 1, 1)),                          # New Year's Day
        _nth_weekday_of_month(year, 1, 0, 3),                  # MLK Day (3rd Monday Jan)
        _nth_weekday_of_month(year, 2, 0, 3),                  # Presidents Day (3rd Monday Feb)
        _nth_weekday_of_month(year, 5, 0, -1),                 # Memorial Day (last Monday May)
        _observed(date(year, 6, 19)),                          # Juneteenth
        _observed(date(year, 7, 4)),                           # Independence Day
        _nth_weekday_of_month(year, 9, 0, 1),                  # Labor Day (1st Monday Sept)
        _nth_weekday_of_month(year, 11, 3, 4),                 # Thanksgiving (4th Thursday Nov)
        _observed(date(year, 12, 25)),                         # Christmas
    }
    return holidays


def get_market_status() -> dict:
    """
    Current NYSE session status and local times for major global
    market centers. See module docstring for the Good Friday
    limitation.
    """
    now_ny = datetime.now(NY_TZ)
    today = now_ny.date()
    current_time = now_ny.time()

    is_weekday = now_ny.weekday() < 5
    is_holiday = today in _us_market_holidays(today.year)

    if not is_weekday or is_holiday:
        status = "Closed"
    elif PREMARKET_START <= current_time < MARKET_OPEN:
        status = "Pre-market"
    elif MARKET_OPEN <= current_time < MARKET_CLOSE:
        status = "Open"
    elif MARKET_CLOSE <= current_time < AFTERHOURS_END:
        status = "After-hours"
    else:
        status = "Closed"

    global_times = {}
    for name, tz_name in GLOBAL_MARKET_CENTERS.items():
        local = datetime.now(ZoneInfo(tz_name))
        global_times[name] = {
            "local_time": local.strftime("%H:%M"),
            "date": local.strftime("%Y-%m-%d"),
            "utc_offset": local.strftime("%z"),
        }

    return {
        "status": status,
        "is_holiday_today": is_holiday,
        "nyse_local_time": now_ny.strftime("%H:%M:%S"),
        "nyse_date": now_ny.strftime("%Y-%m-%d"),
        "global_times": global_times,
        "coverage_note": (
            "Weekends and most US market holidays are accounted for; "
            "Good Friday is not (requires an Easter-date calculation) "
            "and will not be reported as a holiday closure."
        ),
    }