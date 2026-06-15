# modules/smart_money/smart_money_service.py

from __future__ import annotations

from datetime import datetime, UTC, date, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple
import hashlib
import uuid
import json
import pandas as pd
import requests
from sqlalchemy import text
from sqlalchemy.orm import Session

from modules.utils.config import get_secret


SEC_HEADERS = {
    "User-Agent": "StockApp/2.4.1 contact: admin@conduroventures.com",
    "Accept-Encoding": "gzip, deflate",
    "Host": "data.sec.gov",
}

SEC_ARCHIVE_HEADERS = {
    "User-Agent": "StockApp/2.4.1 contact: admin@conduroventures.com",
    "Accept-Encoding": "gzip, deflate",
}

FINNHUB_BASE = "https://finnhub.io/api/v1"
DEFAULT_TIMEOUT = 20


# -----------------------------------------------------------------------------
# Generic DB helpers
# -----------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _normalize_symbol(symbol: str) -> str:
    return str(symbol or "").upper().replace(".US", "").strip()


def _safe_rollback(db: Session) -> None:
    try:
        db.rollback()
    except Exception:
        pass


def _execute(db: Session, sql: str, params: Optional[Dict[str, Any]] = None):
    return db.execute(text(sql), params or {})


def _scalar(db: Session, sql: str, params: Optional[Dict[str, Any]] = None, default: Any = None):
    try:
        value = _execute(db, sql, params).scalar()
        return default if value is None else value
    except Exception:
        _safe_rollback(db)
        return default


def _rows(db: Session, sql: str, params: Optional[Dict[str, Any]] = None) -> list[dict]:
    try:
        return [dict(r) for r in _execute(db, sql, params).mappings().all()]
    except Exception:
        _safe_rollback(db)
        return []


def _table_exists(db: Session, table_name: str) -> bool:
    return bool(
        _scalar(
            db,
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = ANY (current_schemas(false))
                  AND table_name = :table_name
            )
            """,
            {"table_name": table_name},
            False,
        )
    )


def _column_exists(db: Session, table_name: str, column_name: str) -> bool:
    return bool(
        _scalar(
            db,
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = ANY (current_schemas(false))
                  AND table_name = :table_name
                  AND column_name = :column_name
            )
            """,
            {"table_name": table_name, "column_name": column_name},
            False,
        )
    )


def _hash_id(*parts: Any) -> str:
    raw = "|".join(str(p or "") for p in parts)
    return str(uuid.UUID(hashlib.md5(raw.encode("utf-8")).hexdigest()))


def _to_float(value: Any) -> Optional[float]:
    try:
        if value in (None, "", "None", "NA", "N/A", "-", "--"):
            return None
        return float(value)
    except Exception:
        return None


def _to_int(value: Any) -> Optional[int]:
    try:
        if value in (None, "", "None", "NA", "N/A", "-", "--"):
            return None
        return int(float(value))
    except Exception:
        return None


def _safe_date(value: Any) -> Optional[date]:
    if value in (None, "", "None", "NA", "N/A"):
        return None
    if isinstance(value, date):
        return value
    try:
        return pd.to_datetime(value, errors="coerce").date()
    except Exception:
        return None


def ensure_smart_money_tables(db: Session) -> None:
    """
    Creates/normalizes the Smart Money tables.

    Safe to run repeatedly. PostgreSQL-first.
    """
    stmts = [
        """
        CREATE TABLE IF NOT EXISTS insider_transactions (
            id VARCHAR PRIMARY KEY,
            symbol VARCHAR(32) NOT NULL,
            insider_name VARCHAR(255),
            title VARCHAR(255),
            transaction_type VARCHAR(64),
            transaction_code VARCHAR(32),
            shares NUMERIC,
            price NUMERIC,
            value NUMERIC,
            transaction_date DATE,
            filing_date DATE,
            source VARCHAR(64),
            source_url TEXT,
            raw_payload JSONB,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS institutional_holdings (
            id VARCHAR PRIMARY KEY,
            symbol VARCHAR(32) NOT NULL,
            institution VARCHAR(255),
            fund_name VARCHAR(255),
            cik VARCHAR(32),
            shares NUMERIC,
            previous_shares NUMERIC,
            market_value NUMERIC,
            ownership_pct NUMERIC,
            change_pct NUMERIC,
            filing_date DATE,
            report_period DATE,
            source VARCHAR(64),
            source_url TEXT,
            raw_payload JSONB,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS sec_form4_filings (
            id VARCHAR PRIMARY KEY,
            symbol VARCHAR(32) NOT NULL,
            cik VARCHAR(32),
            accession_number VARCHAR(128),
            filing_date DATE,
            transaction_date DATE,
            filing_type VARCHAR(32),
            filing_url TEXT,
            parsed BOOLEAN DEFAULT FALSE,
            raw_payload JSONB,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS smart_money_signals (
            id VARCHAR PRIMARY KEY,
            symbol VARCHAR(32) NOT NULL,
            smart_money_score NUMERIC,
            accumulation_score NUMERIC,
            distribution_score NUMERIC,
            insider_score NUMERIC,
            institutional_score NUMERIC,
            form4_score NUMERIC,
            options_score NUMERIC,
            ai_score NUMERIC,
            confidence_score NUMERIC,
            signal VARCHAR(64),
            rationale TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_insider_transactions_symbol ON insider_transactions(symbol)",
        "CREATE INDEX IF NOT EXISTS idx_insider_transactions_dates ON insider_transactions(transaction_date, filing_date)",
        "CREATE INDEX IF NOT EXISTS idx_institutional_holdings_symbol ON institutional_holdings(symbol)",
        "CREATE INDEX IF NOT EXISTS idx_institutional_holdings_filing ON institutional_holdings(filing_date)",
        "CREATE INDEX IF NOT EXISTS idx_sec_form4_symbol ON sec_form4_filings(symbol)",
        "CREATE INDEX IF NOT EXISTS idx_sec_form4_filing ON sec_form4_filings(filing_date)",
        "CREATE INDEX IF NOT EXISTS idx_smart_money_signals_symbol ON smart_money_signals(symbol)",
        "CREATE INDEX IF NOT EXISTS idx_smart_money_signals_score ON smart_money_signals(smart_money_score)",
    ]

    for stmt in stmts:
        _execute(db, stmt)

    # ------------------------------------------------------------------
    # Schema migrations for existing deployments
    # ------------------------------------------------------------------

    migrations = [
        # insider_transactions
        ("insider_transactions", "transaction_code",
         "ALTER TABLE insider_transactions ADD COLUMN transaction_code VARCHAR(32)"),

        ("insider_transactions", "source",
         "ALTER TABLE insider_transactions ADD COLUMN source VARCHAR(64)"),

        ("insider_transactions", "source_url",
         "ALTER TABLE insider_transactions ADD COLUMN source_url TEXT"),

        ("insider_transactions", "raw_payload",
         "ALTER TABLE insider_transactions ADD COLUMN raw_payload JSONB"),

        ("insider_transactions", "updated_at",
         "ALTER TABLE insider_transactions ADD COLUMN updated_at TIMESTAMP"),

        # institutional_holdings
        ("institutional_holdings", "fund_name",
         "ALTER TABLE institutional_holdings ADD COLUMN fund_name VARCHAR(255)"),

        ("institutional_holdings", "cik",
         "ALTER TABLE institutional_holdings ADD COLUMN cik VARCHAR(32)"),

        ("institutional_holdings", "previous_shares",
         "ALTER TABLE institutional_holdings ADD COLUMN previous_shares NUMERIC"),

        ("institutional_holdings", "report_period",
         "ALTER TABLE institutional_holdings ADD COLUMN report_period DATE"),

        ("institutional_holdings", "source",
         "ALTER TABLE institutional_holdings ADD COLUMN source VARCHAR(64)"),

        ("institutional_holdings", "source_url",
         "ALTER TABLE institutional_holdings ADD COLUMN source_url TEXT"),

        ("institutional_holdings", "raw_payload",
         "ALTER TABLE institutional_holdings ADD COLUMN raw_payload JSONB"),

        ("institutional_holdings", "updated_at",
         "ALTER TABLE institutional_holdings ADD COLUMN updated_at TIMESTAMP"),

        # sec_form4_filings
        ("sec_form4_filings", "accession_number",
         "ALTER TABLE sec_form4_filings ADD COLUMN accession_number VARCHAR(128)"),

        ("sec_form4_filings", "transaction_date",
         "ALTER TABLE sec_form4_filings ADD COLUMN transaction_date DATE"),

        ("sec_form4_filings", "raw_payload",
         "ALTER TABLE sec_form4_filings ADD COLUMN raw_payload JSONB"),

        ("sec_form4_filings", "created_at",
         "ALTER TABLE sec_form4_filings ADD COLUMN created_at TIMESTAMP DEFAULT NOW()"),

        ("sec_form4_filings", "updated_at",
         "ALTER TABLE sec_form4_filings ADD COLUMN updated_at TIMESTAMP"),

        # smart_money_signals
        ("smart_money_signals", "form4_score",
         "ALTER TABLE smart_money_signals ADD COLUMN form4_score NUMERIC"),

        ("smart_money_signals", "ai_score",
         "ALTER TABLE smart_money_signals ADD COLUMN ai_score NUMERIC"),

        ("smart_money_signals", "confidence_score",
         "ALTER TABLE smart_money_signals ADD COLUMN confidence_score NUMERIC"),

        ("smart_money_signals", "signal",
         "ALTER TABLE smart_money_signals ADD COLUMN signal VARCHAR(64)"),

        ("smart_money_signals", "rationale",
         "ALTER TABLE smart_money_signals ADD COLUMN rationale TEXT"),

        ("smart_money_signals", "updated_at",
         "ALTER TABLE smart_money_signals ADD COLUMN updated_at TIMESTAMP"),
    ]

    for table_name, column_name, sql in migrations:
        try:
            if not _column_exists(
                    db,
                    table_name,
                    column_name,
            ):
                print(
                    f"SMART MONEY MIGRATION: "
                    f"{table_name}.{column_name}"
                )
                _execute(db, sql)
        except Exception as exc:
            print(
                f"SMART MONEY MIGRATION FAILED: "
                f"{table_name}.{column_name}",
                exc,
            )

    db.commit()


# -----------------------------------------------------------------------------
# Universe helpers
# -----------------------------------------------------------------------------


def list_symbols_for_smart_money(
    db: Session,
    tenant_id: Optional[str] = None,
    universe_id: Optional[str] = None,
    limit: int = 100,
) -> list[str]:
    if universe_id and _table_exists(db, "universe_symbols"):
        rows = _rows(
            db,
            """
            SELECT DISTINCT symbol
            FROM universe_symbols
            WHERE universe_id = :universe_id
            ORDER BY symbol
            LIMIT :limit
            """,
            {"universe_id": universe_id, "limit": int(limit or 100)},
        )
        return [_normalize_symbol(r["symbol"]) for r in rows if r.get("symbol")]

    if _table_exists(db, "analytics_snapshots"):
        if tenant_id:
            rows = _rows(
                db,
                """
                SELECT DISTINCT symbol
                FROM analytics_snapshots
                WHERE tenant_id = :tenant_id
                ORDER BY symbol
                LIMIT :limit
                """,
                {"tenant_id": tenant_id, "limit": int(limit or 100)},
            )
        else:
            rows = _rows(
                db,
                """
                SELECT DISTINCT symbol
                FROM analytics_snapshots
                ORDER BY symbol
                LIMIT :limit
                """,
                {"limit": int(limit or 100)},
            )
        return [_normalize_symbol(r["symbol"]) for r in rows if r.get("symbol")]

    return []


# -----------------------------------------------------------------------------
# Finnhub ingestion
# -----------------------------------------------------------------------------


def _finnhub_get(path: str, params: dict) -> Any:
    key = get_secret("FINNHUB_API_KEY")
    if not key:
        return None

    q = dict(params or {})
    q["token"] = key

    response = requests.get(
        f"{FINNHUB_BASE}/{path.lstrip('/')}",
        params=q,
        timeout=DEFAULT_TIMEOUT,
    )

    if response.status_code == 429:
        raise RuntimeError("Finnhub rate limited")

    if response.status_code != 200:
        print("Finnhub HTTP error:", response.status_code, response.text[:300])
        return None

    if not response.text:
        return None

    try:
        return response.json()
    except Exception:
        return None


def fetch_finnhub_insider_transactions(symbol: str) -> list[dict]:
    sym = _normalize_symbol(symbol)
    if not sym:
        return []

    data = _finnhub_get("stock/insider-transactions", {"symbol": sym})
    if not data:
        return []

    if isinstance(data, dict):
        rows = data.get("data") or data.get("transactions") or []
    elif isinstance(data, list):
        rows = data
    else:
        rows = []

    out = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue

        tx_type = (
            row.get("transactionCode")
            or row.get("transaction_type")
            or row.get("transactionType")
            or row.get("type")
        )

        shares = _to_float(
            row.get("share")
            or row.get("shares")
            or row.get("transactionShares")
            or row.get("securitiesTransacted")
        )

        price = _to_float(
            row.get("transactionPrice")
            or row.get("price")
            or row.get("transaction_price")
        )

        value = _to_float(row.get("value"))
        if value is None and shares is not None and price is not None:
            value = shares * price

        out.append(
            {
                "id": _hash_id("FINNHUB_INSIDER", sym, row.get("name"), row.get("filingDate"), row.get("transactionDate"), tx_type, shares, price),
                "symbol": sym,
                "insider_name": row.get("name") or row.get("insiderName") or row.get("ownerName"),
                "title": row.get("shareholder") or row.get("title") or row.get("relationship"),
                "transaction_type": _normalize_transaction_type(tx_type),
                "transaction_code": tx_type,
                "shares": shares,
                "price": price,
                "value": value,
                "transaction_date": _safe_date(row.get("transactionDate") or row.get("transaction_date")),
                "filing_date": _safe_date(row.get("filingDate") or row.get("filing_date")),
                "source": "FINNHUB",
                "source_url": None,
                "raw_payload": row,
            }
        )

    return out


def fetch_finnhub_institutional_ownership(symbol: str) -> list[dict]:
    sym = _normalize_symbol(symbol)
    if not sym:
        return []

    # Finnhub endpoint availability differs by plan. This function is defensive.
    data = _finnhub_get("stock/ownership", {"symbol": sym})
    if not data:
        return []

    if isinstance(data, dict):
        rows = data.get("ownership") or data.get("data") or []
    elif isinstance(data, list):
        rows = data
    else:
        rows = []

    out = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue

        institution = row.get("name") or row.get("institution") or row.get("fundName") or row.get("holder")
        shares = _to_float(row.get("share") or row.get("shares"))
        previous_shares = _to_float(row.get("previousShares") or row.get("prevShares"))
        change_pct = _to_float(row.get("changePct") or row.get("change_pct"))

        if change_pct is None and shares is not None and previous_shares not in (None, 0):
            change_pct = ((shares - previous_shares) / previous_shares) * 100

        filing_date = _safe_date(row.get("filingDate") or row.get("reportDate") or row.get("date"))

        out.append(
            {
                "id": _hash_id("FINNHUB_INST", sym, institution, filing_date, shares),
                "symbol": sym,
                "institution": institution,
                "fund_name": institution,
                "cik": row.get("cik"),
                "shares": shares,
                "previous_shares": previous_shares,
                "market_value": _to_float(row.get("value") or row.get("marketValue")),
                "ownership_pct": _to_float(row.get("ownershipPct") or row.get("ownership_pct")),
                "change_pct": change_pct,
                "filing_date": filing_date,
                "report_period": _safe_date(row.get("reportDate") or row.get("period")),
                "source": "FINNHUB",
                "source_url": None,
                "raw_payload": row,
            }
        )

    return out


# -----------------------------------------------------------------------------
# SEC company facts/submissions helpers
# -----------------------------------------------------------------------------


def fetch_sec_company_tickers() -> dict[str, dict]:
    """
    Returns symbol -> metadata mapping from SEC company_tickers.json.
    """
    url = "https://www.sec.gov/files/company_tickers.json"
    try:
        response = requests.get(url, headers=SEC_ARCHIVE_HEADERS, timeout=DEFAULT_TIMEOUT)
        if response.status_code != 200:
            print("SEC tickers HTTP error:", response.status_code, response.text[:200])
            return {}

        data = response.json()
        out = {}
        for _, row in (data or {}).items():
            ticker = _normalize_symbol(row.get("ticker"))
            if ticker:
                out[ticker] = {
                    "cik": str(row.get("cik_str")).zfill(10),
                    "title": row.get("title"),
                    "ticker": ticker,
                }
        return out
    except Exception as exc:
        print("SEC ticker fetch failed:", exc)
        return {}


def fetch_sec_form4_filings(symbol: str, ticker_map: Optional[dict[str, dict]] = None, limit: int = 20) -> list[dict]:
    sym = _normalize_symbol(symbol)
    ticker_map = ticker_map or fetch_sec_company_tickers()
    meta = ticker_map.get(sym)
    if not meta:
        return []

    cik = meta["cik"]
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"

    try:
        response = requests.get(url, headers=SEC_HEADERS, timeout=DEFAULT_TIMEOUT)
        if response.status_code != 200:
            print("SEC submissions HTTP error:", sym, response.status_code, response.text[:200])
            return []

        data = response.json()
        recent = (data or {}).get("filings", {}).get("recent", {})
        forms = recent.get("form", []) or []
        filing_dates = recent.get("filingDate", []) or []
        accession_numbers = recent.get("accessionNumber", []) or []
        primary_docs = recent.get("primaryDocument", []) or []

        out = []
        for idx, form in enumerate(forms):
            if str(form).upper() not in {"4", "4/A"}:
                continue

            accession = accession_numbers[idx] if idx < len(accession_numbers) else None
            filing_date = _safe_date(filing_dates[idx] if idx < len(filing_dates) else None)
            primary_doc = primary_docs[idx] if idx < len(primary_docs) else ""

            accession_path = str(accession or "").replace("-", "")
            filing_url = (
                f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_path}/{primary_doc}"
                if accession and primary_doc
                else None
            )

            out.append(
                {
                    "id": _hash_id("SEC_FORM4", sym, cik, accession),
                    "symbol": sym,
                    "cik": cik,
                    "accession_number": accession,
                    "filing_date": filing_date,
                    "transaction_date": None,
                    "filing_type": form,
                    "filing_url": filing_url,
                    "parsed": False,
                    "raw_payload": {
                        "form": form,
                        "filingDate": str(filing_date) if filing_date else None,
                        "accessionNumber": accession,
                        "primaryDocument": primary_doc,
                    },
                }
            )

            if len(out) >= limit:
                break

        return out
    except Exception as exc:
        print("SEC Form 4 fetch failed:", sym, exc)
        return []


# -----------------------------------------------------------------------------
# Upserts
# -----------------------------------------------------------------------------


def _normalize_transaction_type(code: Any) -> str:
    c = str(code or "").upper().strip()
    if c in {"P", "BUY", "PURCHASE", "ACQUIRE", "ACQUIRED"}:
        return "BUY"
    if c in {"S", "SELL", "SALE", "DISPOSE", "DISPOSED"}:
        return "SELL"
    if c in {"A"}:
        return "AWARD"
    if c in {"M"}:
        return "OPTION_EXERCISE"
    return c or "UNKNOWN"


def upsert_insider_transactions(db: Session, rows: Iterable[dict]) -> int:
    ensure_smart_money_tables(db)
    count = 0

    for row in rows or []:
        params = dict(row)
        params["raw_payload"] = json.dumps(
    params.get("raw_payload"),
    default=str
) if params.get("raw_payload") is not None else None
        _execute(
            db,
            """
            INSERT INTO insider_transactions (
                id, symbol, insider_name, title, transaction_type,
                transaction_code, shares, price, value, transaction_date,
                filing_date, source, source_url, raw_payload, created_at, updated_at
            )
            VALUES (
                :id, :symbol, :insider_name, :title, :transaction_type,
                :transaction_code, :shares, :price, :value, :transaction_date,
                :filing_date, :source, :source_url, CAST(:raw_payload AS JSONB),
                NOW(), NOW()
            )
            ON CONFLICT (id) DO UPDATE SET
                insider_name = EXCLUDED.insider_name,
                title = EXCLUDED.title,
                transaction_type = EXCLUDED.transaction_type,
                transaction_code = EXCLUDED.transaction_code,
                shares = EXCLUDED.shares,
                price = EXCLUDED.price,
                value = EXCLUDED.value,
                transaction_date = EXCLUDED.transaction_date,
                filing_date = EXCLUDED.filing_date,
                source = EXCLUDED.source,
                source_url = EXCLUDED.source_url,
                raw_payload = EXCLUDED.raw_payload,
                updated_at = NOW()
            """,
            params,
        )
        count += 1

    db.commit()
    return count


def upsert_institutional_holdings(db: Session, rows: Iterable[dict]) -> int:
    ensure_smart_money_tables(db)
    count = 0

    for row in rows or []:
        params = dict(row)
        params["raw_payload"] = json.dumps(
    params.get("raw_payload"),
    default=str
) if params.get("raw_payload") is not None else None
        _execute(
            db,
            """
            INSERT INTO institutional_holdings (
                id, symbol, institution, fund_name, cik, shares,
                previous_shares, market_value, ownership_pct, change_pct,
                filing_date, report_period, source, source_url,
                raw_payload, created_at, updated_at
            )
            VALUES (
                :id, :symbol, :institution, :fund_name, :cik, :shares,
                :previous_shares, :market_value, :ownership_pct, :change_pct,
                :filing_date, :report_period, :source, :source_url,
                CAST(:raw_payload AS JSONB), NOW(), NOW()
            )
            ON CONFLICT (id) DO UPDATE SET
                institution = EXCLUDED.institution,
                fund_name = EXCLUDED.fund_name,
                cik = EXCLUDED.cik,
                shares = EXCLUDED.shares,
                previous_shares = EXCLUDED.previous_shares,
                market_value = EXCLUDED.market_value,
                ownership_pct = EXCLUDED.ownership_pct,
                change_pct = EXCLUDED.change_pct,
                filing_date = EXCLUDED.filing_date,
                report_period = EXCLUDED.report_period,
                source = EXCLUDED.source,
                source_url = EXCLUDED.source_url,
                raw_payload = EXCLUDED.raw_payload,
                updated_at = NOW()
            """,
            params,
        )
        count += 1

    db.commit()
    return count


def upsert_sec_form4_filings(db: Session, rows: Iterable[dict]) -> int:
    ensure_smart_money_tables(db)

    count = 0

    for row in rows or []:
        params = dict(row)

        _execute(
            db,
            """
            INSERT INTO sec_form4_filings (
                id,
                symbol,
                cik,
                filing_date,
                filing_url,
                filing_type,
                parsed
            )
            VALUES (
                :id,
                :symbol,
                :cik,
                :filing_date,
                :filing_url,
                :filing_type,
                :parsed
            )
            ON CONFLICT (id)
            DO UPDATE SET
                filing_date = EXCLUDED.filing_date,
                filing_url = EXCLUDED.filing_url,
                filing_type = EXCLUDED.filing_type,
                parsed = EXCLUDED.parsed
            """,
            params,
        )

        count += 1

    db.commit()
    return count


# -----------------------------------------------------------------------------
# Scoring
# -----------------------------------------------------------------------------


def _score_insiders(db: Session, symbol: str) -> tuple[float, str]:
    sym = _normalize_symbol(symbol)
    if not _table_exists(db, "insider_transactions"):
        return 0.0, "No insider table"

    buys = int(
        _scalar(
            db,
            """
            SELECT COUNT(*)
            FROM insider_transactions
            WHERE symbol = :symbol
              AND transaction_type = 'BUY'
              AND COALESCE(transaction_date, filing_date, created_at::date) >= CURRENT_DATE - INTERVAL '180 days'
            """,
            {"symbol": sym},
            0,
        )
        or 0
    )
    sells = int(
        _scalar(
            db,
            """
            SELECT COUNT(*)
            FROM insider_transactions
            WHERE symbol = :symbol
              AND transaction_type = 'SELL'
              AND COALESCE(transaction_date, filing_date, created_at::date) >= CURRENT_DATE - INTERVAL '180 days'
            """,
            {"symbol": sym},
            0,
        )
        or 0
    )
    buy_value = float(
        _scalar(
            db,
            """
            SELECT COALESCE(SUM(value), 0)
            FROM insider_transactions
            WHERE symbol = :symbol
              AND transaction_type = 'BUY'
              AND COALESCE(transaction_date, filing_date, created_at::date) >= CURRENT_DATE - INTERVAL '180 days'
            """,
            {"symbol": sym},
            0,
        )
        or 0
    )
    sell_value = float(
        _scalar(
            db,
            """
            SELECT COALESCE(SUM(value), 0)
            FROM insider_transactions
            WHERE symbol = :symbol
              AND transaction_type = 'SELL'
              AND COALESCE(transaction_date, filing_date, created_at::date) >= CURRENT_DATE - INTERVAL '180 days'
            """,
            {"symbol": sym},
            0,
        )
        or 0
    )

    net_count = buys - sells
    net_value = buy_value - sell_value

    score = 50.0
    score += min(25.0, max(-25.0, net_count * 5.0))
    if net_value > 0:
        score += min(25.0, 5.0 + (net_value / 1_000_000.0) * 3.0)
    elif net_value < 0:
        score -= min(25.0, 5.0 + (abs(net_value) / 1_000_000.0) * 3.0)

    score = max(0.0, min(100.0, score))
    return score, f"Insider buys={buys}, sells={sells}, net value={net_value:,.0f}"


def _score_institutional(db: Session, symbol: str) -> tuple[float, str]:
    sym = _normalize_symbol(symbol)
    if not _table_exists(db, "institutional_holdings"):
        return 0.0, "No institutional table"

    avg_change = float(
        _scalar(
            db,
            """
            SELECT COALESCE(AVG(change_pct), 0)
            FROM institutional_holdings
            WHERE symbol = :symbol
            """,
            {"symbol": sym},
            0,
        )
        or 0
    )
    inst_count = int(
        _scalar(
            db,
            """
            SELECT COUNT(DISTINCT COALESCE(institution, fund_name, cik))
            FROM institutional_holdings
            WHERE symbol = :symbol
            """,
            {"symbol": sym},
            0,
        )
        or 0
    )

    score = 50.0 + max(-35.0, min(35.0, avg_change * 1.5)) + min(15.0, inst_count * 1.5)
    score = max(0.0, min(100.0, score))
    return score, f"Institutional avg change={avg_change:.1f}%, holders={inst_count}"


def _score_form4(db: Session, symbol: str) -> tuple[float, str]:
    sym = _normalize_symbol(symbol)
    if not _table_exists(db, "sec_form4_filings"):
        return 0.0, "No Form 4 table"

    recent = int(
        _scalar(
            db,
            """
            SELECT COUNT(*)
            FROM sec_form4_filings
            WHERE symbol = :symbol
              AND filing_date >= CURRENT_DATE - INTERVAL '180 days'
            """,
            {"symbol": sym},
            0,
        )
        or 0
    )
    score = max(0.0, min(100.0, recent * 10.0))
    return score, f"Recent Form 4 filings={recent}"


def _score_ai(db: Session, symbol: str) -> tuple[float, float, str]:
    sym = _normalize_symbol(symbol)
    if not _table_exists(db, "analytics_snapshots"):
        return 0.0, 0.0, "No analytics table"

    row = _rows(
        db,
        """
        SELECT composite_score, confidence_score, signal, rating
        FROM analytics_snapshots
        WHERE symbol = :symbol
        ORDER BY asof DESC
        LIMIT 1
        """,
        {"symbol": sym},
    )
    if not row:
        return 0.0, 0.0, "No analytics snapshot"

    r = row[0]
    ai = float(r.get("composite_score") or 0)
    conf = float(r.get("confidence_score") or 0)
    return ai, conf, f"AI={ai:.1f}, confidence={conf:.1f}, signal={r.get('signal') or r.get('rating')}"


def calculate_smart_money_signal(db: Session, symbol: str) -> dict:
    sym = _normalize_symbol(symbol)
    insider_score, insider_reason = _score_insiders(db, sym)
    institutional_score, institutional_reason = _score_institutional(db, sym)
    form4_score, form4_reason = _score_form4(db, sym)
    ai_score, confidence_score, ai_reason = _score_ai(db, sym)

    accumulation_score = max(
        0.0,
        min(
            100.0,
            institutional_score * 0.45
            + insider_score * 0.30
            + form4_score * 0.10
            + ai_score * 0.15,
        ),
    )

    distribution_score = max(
        0.0,
        min(
            100.0,
            (100.0 - institutional_score) * 0.45
            + (100.0 - insider_score) * 0.30
            + max(0.0, 50.0 - ai_score) * 0.25,
        ),
    )

    smart_money_score = max(
        0.0,
        min(
            100.0,
            insider_score * 0.30
            + institutional_score * 0.30
            + form4_score * 0.10
            + ai_score * 0.20
            + confidence_score * 0.10,
        ),
    )

    if smart_money_score >= 75 and accumulation_score >= distribution_score:
        signal = "Aggressive Accumulation"
    elif smart_money_score >= 60 and accumulation_score >= distribution_score:
        signal = "Accumulation"
    elif distribution_score >= 65:
        signal = "Distribution"
    else:
        signal = "Neutral"

    rationale = "; ".join([insider_reason, institutional_reason, form4_reason, ai_reason])

    return {
        "id": _hash_id("SMART_MONEY_SIGNAL", sym),
        "symbol": sym,
        "smart_money_score": round(smart_money_score, 2),
        "accumulation_score": round(accumulation_score, 2),
        "distribution_score": round(distribution_score, 2),
        "insider_score": round(insider_score, 2),
        "institutional_score": round(institutional_score, 2),
        "form4_score": round(form4_score, 2),
        "options_score": 0.0,
        "ai_score": round(ai_score, 2),
        "confidence_score": round(confidence_score, 2),
        "signal": signal,
        "rationale": rationale,
    }


def upsert_smart_money_signal(db: Session, signal: dict) -> None:
    ensure_smart_money_tables(db)
    _execute(
        db,
        """
        INSERT INTO smart_money_signals (
            id, symbol, smart_money_score, accumulation_score,
            distribution_score, insider_score, institutional_score,
            form4_score, options_score, ai_score, confidence_score,
            signal, rationale, created_at, updated_at
        )
        VALUES (
            :id, :symbol, :smart_money_score, :accumulation_score,
            :distribution_score, :insider_score, :institutional_score,
            :form4_score, :options_score, :ai_score, :confidence_score,
            :signal, :rationale, NOW(), NOW()
        )
        ON CONFLICT (id) DO UPDATE SET
            smart_money_score = EXCLUDED.smart_money_score,
            accumulation_score = EXCLUDED.accumulation_score,
            distribution_score = EXCLUDED.distribution_score,
            insider_score = EXCLUDED.insider_score,
            institutional_score = EXCLUDED.institutional_score,
            form4_score = EXCLUDED.form4_score,
            options_score = EXCLUDED.options_score,
            ai_score = EXCLUDED.ai_score,
            confidence_score = EXCLUDED.confidence_score,
            signal = EXCLUDED.signal,
            rationale = EXCLUDED.rationale,
            updated_at = NOW()
        """,
        signal,
    )
    db.commit()


# -----------------------------------------------------------------------------
# Orchestration
# -----------------------------------------------------------------------------


def refresh_symbol_smart_money(
    db: Session,
    symbol: str,
    ticker_map: Optional[dict[str, dict]] = None,
    fetch_sec: bool = True,
    fetch_finnhub: bool = True,
) -> dict:
    sym = _normalize_symbol(symbol)
    ensure_smart_money_tables(db)

    inserted = {
        "symbol": sym,
        "insider_transactions": 0,
        "institutional_holdings": 0,
        "sec_form4_filings": 0,
        "smart_money_signals": 0,
    }

    if fetch_finnhub:
        try:
            insiders = fetch_finnhub_insider_transactions(sym)
            inserted["insider_transactions"] = upsert_insider_transactions(db, insiders)
        except Exception as exc:
            _safe_rollback(db)
            print("Smart money insider refresh failed:", sym, exc)

        try:
            institutional = fetch_finnhub_institutional_ownership(sym)
            inserted["institutional_holdings"] = upsert_institutional_holdings(db, institutional)
        except Exception as exc:
            _safe_rollback(db)
            print("Smart money institutional refresh failed:", sym, exc)

    if fetch_sec:
        try:
            filings = fetch_sec_form4_filings(sym, ticker_map=ticker_map)
            inserted["sec_form4_filings"] = upsert_sec_form4_filings(db, filings)
        except Exception as exc:
            _safe_rollback(db)
            print("Smart money SEC Form 4 refresh failed:", sym, exc)

    try:
        signal = calculate_smart_money_signal(db, sym)
        upsert_smart_money_signal(db, signal)
        inserted["smart_money_signals"] = 1
    except Exception as exc:
        _safe_rollback(db)
        print("Smart money signal scoring failed:", sym, exc)

    return inserted


def refresh_smart_money_universe(
    db: Session,
    tenant_id: Optional[str] = None,
    universe_id: Optional[str] = None,
    symbols: Optional[list[str]] = None,
    limit: int = 50,
    fetch_sec: bool = True,
    fetch_finnhub: bool = True,
    progress=None,
) -> dict:
    ensure_smart_money_tables(db)

    if symbols is None:
        symbols = list_symbols_for_smart_money(
            db,
            tenant_id=tenant_id,
            universe_id=universe_id,
            limit=limit,
        )

    clean_symbols = []
    for s in symbols or []:
        sym = _normalize_symbol(s)
        if sym and sym not in clean_symbols:
            clean_symbols.append(sym)

    if limit and limit > 0:
        clean_symbols = clean_symbols[: int(limit)]

    ticker_map = fetch_sec_company_tickers() if fetch_sec else {}

    totals = {
        "symbols": len(clean_symbols),
        "insider_transactions": 0,
        "institutional_holdings": 0,
        "sec_form4_filings": 0,
        "smart_money_signals": 0,
        "errors": 0,
    }

    for idx, sym in enumerate(clean_symbols, start=1):
        try:
            result = refresh_symbol_smart_money(
                db,
                sym,
                ticker_map=ticker_map,
                fetch_sec=fetch_sec,
                fetch_finnhub=fetch_finnhub,
            )
            for key in [
                "insider_transactions",
                "institutional_holdings",
                "sec_form4_filings",
                "smart_money_signals",
            ]:
                totals[key] += int(result.get(key) or 0)
        except Exception as exc:
            totals["errors"] += 1
            _safe_rollback(db)
            print("Smart money universe refresh failed:", sym, exc)

        if progress:
            try:
                progress(idx, len(clean_symbols), sym)
            except Exception:
                pass

    return totals


def get_symbol_smart_money_snapshot(
    db: Session,
    symbol: str,
) -> dict:

    sym = _normalize_symbol(symbol)

    ensure_smart_money_tables(db)

    signal = _rows(
        db,
        """
        SELECT *
        FROM smart_money_signals
        WHERE symbol = :symbol
        ORDER BY created_at DESC NULLS LAST
        LIMIT 1
        """,
        {"symbol": sym},
    )

    if signal:
        return signal[0]

    return calculate_smart_money_signal(
        db,
        sym,
    )


