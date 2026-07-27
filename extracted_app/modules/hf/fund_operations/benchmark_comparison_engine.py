from __future__ import annotations
from typing import Any


def compare_to_benchmark(performance: dict[str, Any], benchmark_return: float = 0.08) -> dict[str, Any]:
    ytd = float(performance.get('ytd_return') or 0)
    alpha = ytd - float(benchmark_return or 0)
    return {'fund_ytd': round(ytd, 4), 'benchmark_ytd': round(benchmark_return, 4), 'alpha': round(alpha, 4), 'status': 'Outperforming' if alpha > 0 else 'Underperforming'}
