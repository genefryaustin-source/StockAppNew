from __future__ import annotations
from typing import Any
from datetime import datetime, timezone, timedelta


def build_nav_history(current_nav: float = 1_000_000, days: int = 30) -> list[dict[str, Any]]:
    rows = []
    base = float(current_nav or 1_000_000)
    start = datetime.now(timezone.utc) - timedelta(days=days)
    for i in range(days + 1):
        drift = 1 + ((i - days / 2) * 0.0015) + ((i % 5) - 2) * 0.001
        nav = base * drift
        rows.append({'date': (start + timedelta(days=i)).date().isoformat(), 'nav': round(nav, 2), 'nav_per_share': round(nav / 1_000_000, 4)})
    return rows
