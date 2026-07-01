"""
modules/forex/forex_history_repository.py

Sprint 25 Phase 4.5 - Historical Market Data Platform

Postgres-backed repository for institutional Forex historical OHLCV data.
All writes are tenant-aware and use deterministic upserts on:
    (tenant_id, symbol, asof, interval)

This repository intentionally contains no Streamlit code and no direct provider calls.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Iterable, Optional
from uuid import uuid4

import pandas as pd
from sqlalchemy import text


PRICE_HISTORY_TABLE = "forex_price_history"
REFRESH_LOG_TABLE = "forex_history_refresh_log"


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def normalize_pair(pair: Any) -> str:
    value = str(pair or "").upper().strip()
    value = value.replace("-", "").replace("_", "").replace("/", "").replace(" ", "")
    if len(value) >= 6:
        return f"{value[:3]}/{value[3:6]}"
    return value


def pair_to_symbol(pair: Any) -> str:
    return normalize_pair(pair).replace("/", "")


def _to_naive_datetime(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    parsed = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(parsed):
        return None
    return parsed.to_pydatetime().replace(tzinfo=None)


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        out = float(value)
        if pd.isna(out):
            return None
        return out
    except Exception:
        return None


class ForexHistoryRepository:
    def __init__(
        self,
        db: Any = None,
        *,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
    ):
        self.db = db
        self.tenant_id = tenant_id or "default"
        self.user_id = user_id
        self.portfolio_id = portfolio_id

    def ensure_tables(self):


        if self.db is None:
            return

        self.db.execute(text(f"""
        CREATE TABLE IF NOT EXISTS {PRICE_HISTORY_TABLE} (
            id UUID PRIMARY KEY,
            tenant_id VARCHAR(100) NOT NULL,
            portfolio_id VARCHAR(100),
            user_id VARCHAR(100),
            symbol VARCHAR(20) NOT NULL,
            pair VARCHAR(20) NOT NULL,
            base_currency VARCHAR(10),
            quote_currency VARCHAR(10),
            asof TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            interval VARCHAR(20) NOT NULL DEFAULT '1day',
            open DOUBLE PRECISION,
            high DOUBLE PRECISION,
            low DOUBLE PRECISION,
            close DOUBLE PRECISION NOT NULL,
            volume DOUBLE PRECISION,
            vwap DOUBLE PRECISION,
            provider VARCHAR(100),
            source VARCHAR(100),
            raw JSONB,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (tenant_id, symbol, asof, interval)
        )
        """))

        self.db.execute(text(f"""
        CREATE INDEX IF NOT EXISTS idx_{PRICE_HISTORY_TABLE}_tenant_symbol_asof
            ON {PRICE_HISTORY_TABLE} (tenant_id, symbol, asof DESC)
        """))
        self.db.execute(text(f"""
        CREATE INDEX IF NOT EXISTS idx_{PRICE_HISTORY_TABLE}_tenant_interval
            ON {PRICE_HISTORY_TABLE} (tenant_id, interval, asof DESC)
        """))
        self.db.execute(text(f"""
        CREATE INDEX IF NOT EXISTS idx_{PRICE_HISTORY_TABLE}_provider
            ON {PRICE_HISTORY_TABLE} (provider, asof DESC)
        """))

        self.db.execute(text(f"""
        CREATE TABLE IF NOT EXISTS {REFRESH_LOG_TABLE} (
            id UUID PRIMARY KEY,
            tenant_id VARCHAR(100) NOT NULL,
            portfolio_id VARCHAR(100),
            user_id VARCHAR(100),
            symbol VARCHAR(20),
            pair VARCHAR(20),
            interval VARCHAR(20),
            provider VARCHAR(100),
            requested_start TIMESTAMP WITHOUT TIME ZONE,
            requested_end TIMESTAMP WITHOUT TIME ZONE,
            rows_received INTEGER DEFAULT 0,
            rows_inserted INTEGER DEFAULT 0,
            status VARCHAR(50),
            message TEXT,
            started_at TIMESTAMP WITHOUT TIME ZONE,
            completed_at TIMESTAMP WITHOUT TIME ZONE,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
        """))
        self.db.execute(text(f"""
        CREATE INDEX IF NOT EXISTS idx_{REFRESH_LOG_TABLE}_tenant_completed
            ON {REFRESH_LOG_TABLE} (tenant_id, completed_at DESC)
        """))
        self.db.commit()

    def normalize_history_frame(
        self,
        data: Any,
        *,
        provider: Optional[str] = None,
        interval: str = "1day",
    ) -> pd.DataFrame:
        if data is None:
            return pd.DataFrame()
        if isinstance(data, pd.DataFrame):
            df = data.copy()
        elif isinstance(data, list):
            df = pd.DataFrame(data)
        elif isinstance(data, dict):
            rows = data.get("rows") or data.get("history") or data.get("data") or []
            df = pd.DataFrame(rows)
        else:
            return pd.DataFrame()

        if df.empty:
            return df

        df.columns = [str(c).lower().strip() for c in df.columns]
        rename_map = {
            "ticker": "symbol",
            "pair_symbol": "symbol",
            "datetime": "asof",
            "timestamp": "asof",
            "date": "asof",
            "time": "asof",
            "o": "open",
            "h": "high",
            "l": "low",
            "c": "close",
            "v": "volume",
            "vw": "vwap",
            "price": "close",
            "last": "close",
            "mid": "close",
        }
        df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

        if "symbol" not in df.columns and "pair" in df.columns:
            df["symbol"] = df["pair"]
        if "pair" not in df.columns and "symbol" in df.columns:
            df["pair"] = df["symbol"]

        required = {"symbol", "asof", "close"}
        missing = sorted(required - set(df.columns))
        if missing:
            raise ValueError(f"Historical FX data missing required columns: {missing}")

        df["pair"] = df["pair"].map(normalize_pair)
        df["symbol"] = df["pair"].map(pair_to_symbol)
        df["base_currency"] = df["pair"].str.slice(0, 3)
        df["quote_currency"] = df["pair"].str.slice(4, 7)
        df["asof"] = df["asof"].map(_to_naive_datetime)
        df = df[df["asof"].notna()].copy()
        df["interval"] = str(interval or "1day")
        df["provider"] = df.get("provider", provider) if "provider" in df.columns else provider
        df["source"] = df.get("source", provider) if "source" in df.columns else provider

        for col in ("open", "high", "low", "close", "volume", "vwap"):
            if col in df.columns:
                df[col] = df[col].map(_safe_float)
            else:
                df[col] = None

        df = df[df["close"].notna()].copy()
        df = df.drop_duplicates(subset=["symbol", "asof", "interval"], keep="last")
        df = df.sort_values(["symbol", "asof"]).reset_index(drop=True)
        return df

    def upsert_history(
        self,
        data: Any,
        *,
        provider: Optional[str] = None,
        interval: str = "1day",
    ) -> int:
        if self.db is None:
            return 0
        self.ensure_tables()
        df = self.normalize_history_frame(data, provider=provider, interval=interval)
        if df.empty:
            return 0

        now = _utc_now_naive()
        count = 0
        stmt = text(f"""
        INSERT INTO {PRICE_HISTORY_TABLE} (
            id, tenant_id, portfolio_id, user_id, symbol, pair,
            base_currency, quote_currency, asof, interval,
            open, high, low, close, volume, vwap,
            provider, source, raw, created_at, updated_at
        ) VALUES (
            :id, :tenant_id, :portfolio_id, :user_id, :symbol, :pair,
            :base_currency, :quote_currency, :asof, :interval,
            :open, :high, :low, :close, :volume, :vwap,
            :provider, :source, CAST(:raw AS JSONB), :created_at, :updated_at
        )
        ON CONFLICT (tenant_id, symbol, asof, interval)
        DO UPDATE SET
            portfolio_id = EXCLUDED.portfolio_id,
            user_id = EXCLUDED.user_id,
            pair = EXCLUDED.pair,
            base_currency = EXCLUDED.base_currency,
            quote_currency = EXCLUDED.quote_currency,
            open = COALESCE(EXCLUDED.open, {PRICE_HISTORY_TABLE}.open),
            high = COALESCE(EXCLUDED.high, {PRICE_HISTORY_TABLE}.high),
            low = COALESCE(EXCLUDED.low, {PRICE_HISTORY_TABLE}.low),
            close = EXCLUDED.close,
            volume = COALESCE(EXCLUDED.volume, {PRICE_HISTORY_TABLE}.volume),
            vwap = COALESCE(EXCLUDED.vwap, {PRICE_HISTORY_TABLE}.vwap),
            provider = COALESCE(EXCLUDED.provider, {PRICE_HISTORY_TABLE}.provider),
            source = COALESCE(EXCLUDED.source, {PRICE_HISTORY_TABLE}.source),
            updated_at = EXCLUDED.updated_at
        """)

        for row in df.to_dict("records"):
            params = {
                "id": str(uuid4()),
                "tenant_id": str(self.tenant_id),
                "portfolio_id": self.portfolio_id,
                "user_id": self.user_id,
                "symbol": row.get("symbol"),
                "pair": row.get("pair"),
                "base_currency": row.get("base_currency"),
                "quote_currency": row.get("quote_currency"),
                "asof": row.get("asof"),
                "interval": row.get("interval") or interval,
                "open": row.get("open"),
                "high": row.get("high"),
                "low": row.get("low"),
                "close": row.get("close"),
                "volume": row.get("volume"),
                "vwap": row.get("vwap"),
                "provider": row.get("provider") or provider,
                "source": row.get("source") or provider,
                "raw": "{}",
                "created_at": now,
                "updated_at": now,
            }
            self.db.execute(stmt, params)
            count += 1
        self.db.commit()
        return count

    def load_history(
        self,
        pairs: Optional[Iterable[str]] = None,
        *,
        start: Optional[Any] = None,
        end: Optional[Any] = None,
        interval: str = "1day",
        limit: int = 20000,
    ) -> pd.DataFrame:
        if self.db is None:
            return pd.DataFrame()
        self.ensure_tables()
        clauses = ["tenant_id = :tenant_id", "interval = :interval"]
        params: dict[str, Any] = {"tenant_id": str(self.tenant_id), "interval": interval, "limit": int(limit)}
        if pairs:
            symbols = [pair_to_symbol(p) for p in pairs]
            placeholders = []
            for i, sym in enumerate(symbols):
                key = f"sym{i}"
                placeholders.append(f":{key}")
                params[key] = sym
            clauses.append(f"symbol IN ({', '.join(placeholders)})")
        start_dt = _to_naive_datetime(start)
        end_dt = _to_naive_datetime(end)
        if start_dt:
            clauses.append("asof >= :start")
            params["start"] = start_dt
        if end_dt:
            clauses.append("asof <= :end")
            params["end"] = end_dt
        where = " AND ".join(clauses)
        rows = self.db.execute(text(f"""
            SELECT *
            FROM {PRICE_HISTORY_TABLE}
            WHERE {where}
            ORDER BY symbol, asof
            LIMIT :limit
        """), params).mappings().all()
        return pd.DataFrame([dict(r) for r in rows])

    def latest_asof(self, pair: str, *, interval: str = "1day") -> Optional[datetime]:
        if self.db is None:
            return None
        self.ensure_tables()
        row = self.db.execute(text(f"""
            SELECT MAX(asof) AS latest
            FROM {PRICE_HISTORY_TABLE}
            WHERE tenant_id = :tenant_id
              AND symbol = :symbol
              AND interval = :interval
        """), {
            "tenant_id": str(self.tenant_id),
            "symbol": pair_to_symbol(pair),
            "interval": interval,
        }).mappings().first()
        return row.get("latest") if row else None

    def coverage(self) -> list[dict[str, Any]]:
        if self.db is None:
            return []
        self.ensure_tables()
        rows = self.db.execute(text(f"""
            SELECT
                symbol,
                pair,
                interval,
                provider,
                COUNT(*) AS rows,
                MIN(asof) AS first_asof,
                MAX(asof) AS latest_asof
            FROM {PRICE_HISTORY_TABLE}
            WHERE tenant_id = :tenant_id
            GROUP BY symbol, pair, interval, provider
            ORDER BY pair, interval, provider
        """), {"tenant_id": str(self.tenant_id)}).mappings().all()
        return [dict(r) for r in rows]

    def log_refresh(
        self,
        *,
        pair: Optional[str],
        interval: str,
        provider: Optional[str],
        requested_start: Any = None,
        requested_end: Any = None,
        rows_received: int = 0,
        rows_inserted: int = 0,
        status: str = "completed",
        message: str = "",
        started_at: Any = None,
    ) -> None:
        if self.db is None:
            return
        self.ensure_tables()
        p = normalize_pair(pair) if pair else None
        self.db.execute(text(f"""
            INSERT INTO {REFRESH_LOG_TABLE} (
                id, tenant_id, portfolio_id, user_id, symbol, pair, interval, provider,
                requested_start, requested_end, rows_received, rows_inserted,
                status, message, started_at, completed_at, created_at
            ) VALUES (
                :id, :tenant_id, :portfolio_id, :user_id, :symbol, :pair, :interval, :provider,
                :requested_start, :requested_end, :rows_received, :rows_inserted,
                :status, :message, :started_at, :completed_at, :created_at
            )
        """), {
            "id": str(uuid4()),
            "tenant_id": str(self.tenant_id),
            "portfolio_id": self.portfolio_id,
            "user_id": self.user_id,
            "symbol": pair_to_symbol(p) if p else None,
            "pair": p,
            "interval": interval,
            "provider": provider,
            "requested_start": _to_naive_datetime(requested_start),
            "requested_end": _to_naive_datetime(requested_end),
            "rows_received": int(rows_received or 0),
            "rows_inserted": int(rows_inserted or 0),
            "status": status,
            "message": str(message or "")[:2000],
            "started_at": _to_naive_datetime(started_at) or _utc_now_naive(),
            "completed_at": _utc_now_naive(),
            "created_at": _utc_now_naive(),
        })
        self.db.commit()


def ensure_forex_price_history_tables(db: Any) -> None:
    ForexHistoryRepository(db=db).ensure_tables()
