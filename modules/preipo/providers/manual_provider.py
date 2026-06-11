# ============================================================
# modules/preipo/providers/manual_provider.py
# User-entered / CSV-ready public pre-IPO data normalizer
# ============================================================

from __future__ import annotations

import json
from datetime import datetime, UTC
from typing import Any, Dict


def normalize_manual_company(row: Dict[str, Any]) -> Dict[str, Any]:
    company = str(row.get("company_name") or row.get("company") or "Unknown").strip()

    def f(key):
        try:
            value = row.get(key)
            if value in (None, "", "N/A", "null"):
                return None
            if isinstance(value, str):
                value = value.replace("$", "").replace(",", "").strip()
            return float(value)
        except Exception:
            return None

    def d(key):
        value = row.get(key)
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value)).replace(tzinfo=UTC)
        except Exception:
            return None

    return {
        "company_name": company,
        "normalized_name": company.upper(),
        "ticker_hint": row.get("ticker_hint") or row.get("ticker"),
        "sector": row.get("sector"),
        "industry": row.get("industry"),
        "country": row.get("country"),
        "website": row.get("website"),
        "last_known_valuation": f("last_known_valuation"),
        "last_funding_amount": f("last_funding_amount"),
        "last_funding_date": d("last_funding_date"),
        "last_funding_round": row.get("last_funding_round"),
        "lead_investors": row.get("lead_investors"),
        "source": row.get("source") or "MANUAL",
        "raw_payload": json.dumps(row, default=str),
    }
