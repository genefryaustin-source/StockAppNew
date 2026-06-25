
"""
modules/forex/forex_bulk_refresh_engine.py
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Iterable

from modules.forex.forex_refresh_engine import (
    get_forex_refresh_engine,
)

logger = logging.getLogger(__name__)


class ForexBulkRefreshEngine:

    def __init__(self, max_workers: int = 8):
        self.max_workers = max_workers
        self.engine = get_forex_refresh_engine()

    def refresh_pair(self, pair: str) -> dict:
        return self.engine.refresh_pair(pair)

    def refresh_pairs(
        self,
        pairs: Iterable[str],
        parallel: bool = True,
    ) -> dict:

        pairs = list(dict.fromkeys(pairs))
        results = {}

        if not parallel:
            for pair in pairs:
                results[pair] = self.refresh_pair(pair)
            return results

        with ThreadPoolExecutor(
            max_workers=self.max_workers
        ) as executor:

            futures = {
                executor.submit(
                    self.refresh_pair,
                    pair,
                ): pair
                for pair in pairs
            }

            for future in as_completed(futures):
                pair = futures[future]

                try:
                    results[pair] = future.result()
                except Exception as exc:
                    logger.exception(
                        "Bulk refresh failed for %s",
                        pair,
                    )
                    results[pair] = {
                        "pair": pair,
                        "error": str(exc),
                    }

        return results

    def statistics(
        self,
        results: dict,
    ) -> dict:

        success = sum(
            1
            for row in results.values()
            if not row.get("error")
        )

        failed = len(results) - success

        return {
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),
            "pairs": len(results),
            "successful": success,
            "failed": failed,
            "success_rate": round(
                success / max(len(results), 1) * 100,
                2,
            ),
        }


_ENGINE = None


def get_forex_bulk_refresh_engine():

    global _ENGINE

    if _ENGINE is None:
        _ENGINE = ForexBulkRefreshEngine()

    return _ENGINE
