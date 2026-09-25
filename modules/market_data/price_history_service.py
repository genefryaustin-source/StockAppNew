from __future__ import annotations

from datetime import datetime, timedelta, UTC
from typing import List
import time

import pandas as pd
from sqlalchemy.orm.session import Session
from sqlalchemy.dialects.postgresql import insert

from modules.market_data.models import PriceHistory
from modules.market_data.providers.finnhub_provider import (
    get_history as finnhub_history,
)

from modules.market_data.providers.twelvedata_provider import (
    get_history as twelvedata_history,
)
from modules.utils.symbol_classifier import (
    filter_supported_equities,
)
# ---------------------------------------------------
# Load price history from DB
# ---------------------------------------------------

def load_price_history(db: Session, symbol: str) -> pd.DataFrame | None:

    rows = (
        db.query(PriceHistory)
        .filter(PriceHistory.symbol == symbol)
        .order_by(PriceHistory.date.asc())
        .all()
    )

    if not rows:
        return None

    data = {
        "Date": [],
        "Open": [],
        "High": [],
        "Low": [],
        "Close": [],
        "Volume": [],
    }

    for r in rows:

        data["Date"].append(r.date)
        data["Open"].append(r.open)
        data["High"].append(r.high)
        data["Low"].append(r.low)
        data["Close"].append(r.close)
        data["Volume"].append(r.volume)

    df = pd.DataFrame(data)

    df.set_index("Date", inplace=True)

    return df


# ---------------------------------------------------
# Store price history to DB
# ---------------------------------------------------


def bulk_upsert_price_history(db, rows: list[dict], batch_size: int = 500) -> dict:
    """
    True bulk upsert: builds ONE multi-row INSERT ... ON CONFLICT statement
    per batch (default 500 rows) instead of one INSERT + one commit per
    row. This exists specifically for full-market bulk refreshes (e.g.
    modules.market_data.updater.bulk_update_from_grouped_daily) where
    calling store_price_history() in a loop -- one commit per symbol --
    means one network round-trip to the database PER SYMBOL. Against a
    remote database (Neon, etc.), 12,000+ symbols means 12,000+ round
    trips, and a single stalled connection blocks the entire operation
    with no way out short of restarting the process -- exactly what
    happened testing this in production. Batching drops that to roughly
    (row_count / batch_size) round trips -- ~25 for 12,000 rows instead
    of 12,000.

    Unlike store_price_history's on_conflict_do_nothing (which skips
    rows that already exist), this uses on_conflict_do_update -- a bulk
    "refresh" is expected to overwrite that day's bar with fresh data,
    not silently no-op if something already wrote a row for that date.

    rows: list of {"symbol": str, "date": date-like, "open": float,
    "high": float, "low": float, "close": float, "volume": float|None}.

    Returns {"written": int, "failed_batches": int, "errors": [...]}.
    A failed batch is retried once as individual on_conflict_do_nothing
    inserts (same recovery spirit as store_price_history's per-row
    try/except) so one bad row in a 500-row batch doesn't lose the other
    499 -- but this fallback path is the slow one-by-one path, so it
    should only ever trigger rarely, not as the normal case.
    """
    if not rows:
        return {"written": 0, "failed_batches": 0, "errors": []}

    written = 0
    failed_batches = 0
    errors = []

    for batch_start in range(0, len(rows), batch_size):
        batch = rows[batch_start:batch_start + batch_size]
        # Deduplicate by (symbol, date) before building the INSERT --
        # Postgres's "ON CONFLICT DO UPDATE" cannot affect the same row
        # twice within a single statement, and raises a hard
        # CardinalityViolation if two rows in the same batch target the
        # same (symbol, date). This happened in production: Polygon's
        # grouped-daily response (or the .upper() symbol normalization
        # below, which can collide two differently-cased raw symbols)
        # produced two rows for the same symbol+date within one 500-row
        # batch. The batch still succeeded via the row-by-row fallback
        # below, but that's the slow path this function exists to avoid --
        # deduplicating up front means the fast bulk path handles it
        # correctly instead of needing to fall back at all. Last
        # occurrence wins, consistent with ON CONFLICT DO UPDATE's own
        # "newest write wins" semantics for a genuine re-upsert.
        deduped_by_key: dict[tuple[str, object], dict] = {}
        for r in batch:
            try:
                normalized = {
                    "symbol": str(r["symbol"]).upper(),
                    "date": pd.to_datetime(r["date"]).date(),
                    "open": float(r["open"]),
                    "high": float(r["high"]),
                    "low": float(r["low"]),
                    "close": float(r["close"]),
                    "volume": int(r["volume"]) if r.get("volume") is not None and pd.notna(r["volume"]) else None,
                }
            except (KeyError, TypeError, ValueError):
                continue  # malformed row -- skip rather than fail the whole batch up front
            deduped_by_key[(normalized["symbol"], normalized["date"])] = normalized

        values = list(deduped_by_key.values())

        if not values:
            continue

        try:
            stmt = insert(PriceHistory).values(values)
            stmt = stmt.on_conflict_do_update(
                index_elements=["symbol", "date"],
                set_={
                    "open": stmt.excluded.open, "high": stmt.excluded.high,
                    "low": stmt.excluded.low, "close": stmt.excluded.close,
                    "volume": stmt.excluded.volume,
                },
            )
            db.execute(stmt)
            db.commit()
            written += len(values)
        except Exception as batch_err:
            try:
                db.rollback()
            except Exception:
                pass
            # Fallback: retry this one batch row-by-row so a single bad
            # row doesn't lose the whole batch -- slow path, rare case.
            batch_written = 0
            for v in values:
                try:
                    row_stmt = insert(PriceHistory).values(**v).on_conflict_do_update(
                        index_elements=["symbol", "date"],
                        set_={"open": v["open"], "high": v["high"], "low": v["low"],
                              "close": v["close"], "volume": v["volume"]},
                    )
                    db.execute(row_stmt)
                    db.commit()
                    batch_written += 1
                except Exception as row_err:
                    try:
                        db.rollback()
                    except Exception:
                        pass
                    errors.append(f"{v.get('symbol', '?')}: {row_err}")
            written += batch_written
            failed_batches += 1
            print(f"[price_history] batch upsert fell back to row-by-row "
                  f"({batch_written}/{len(values)} recovered): {batch_err}")

    return {"written": written, "failed_batches": failed_batches, "errors": errors[:50]}


def store_price_history(db, symbol, df):
    df = df.copy()

    if df is None or df.empty:
        return

    # -----------------------------------
    # Flatten MultiIndex columns
    # -----------------------------------

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [
            str(c[0]).strip()
            for c in df.columns
        ]

    # -----------------------------------
    # Normalize column names
    # -----------------------------------

    df.columns = [
        str(c).strip().title()
        for c in df.columns
    ]

    # -----------------------------------
    # Normalize index -> Date column
    # -----------------------------------

    if "Date" not in df.columns:

        if isinstance(df.index, pd.MultiIndex):

            try:
                df = df.reset_index()

            except Exception:
                pass

        elif df.index.name is not None:

            df = df.reset_index()

        else:

            df = df.reset_index().rename(
                columns={"index": "Date"}
            )

    # -----------------------------------
    # Normalize columns AGAIN after reset
    # -----------------------------------

    df.columns = [
        str(c).strip().title()
        for c in df.columns
    ]

    # -----------------------------------
    # Ensure required columns exist
    # -----------------------------------

    required = [
        "Date",
        "Open",
        "High",
        "Low",
        "Close",
    ]

    missing = [
        c for c in required
        if c not in df.columns
    ]

    if missing:
        print(
            "PRICE HISTORY MISSING COLUMNS",
            symbol,
            missing,
            df.columns.tolist(),
        )

        return

    symbol = symbol.upper()

    # Batch upsert with per-row error recovery.
    # Wraps each execute in try/except so a single bad row (duplicate cursor,
    # type error, etc.) never poisons the entire session.
    batch_size = 50
    rows_list = list(df.iterrows())

    for batch_start in range(0, len(rows_list), batch_size):
        batch = rows_list[batch_start:batch_start + batch_size]

        for _, row in batch:
            try:
                stmt = insert(PriceHistory).values(
                    symbol=symbol,
                    date=pd.to_datetime(row["Date"]),
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=(
                        int(row["Volume"])
                        if (
                            "Volume" in row
                            and pd.notna(row["Volume"])
                        )
                        else None
                    ),
                )

                stmt = stmt.on_conflict_do_nothing()

                db.execute(stmt)

            except Exception as _row_err:
                # Roll back so the session is usable for the next row
                try:
                    db.rollback()
                except Exception:
                    pass
                print(f"[price_history] skip {symbol} {row.get('Date','?')}: {_row_err}")

        # Commit each batch — smaller transactions = less cursor contention
        try:
            db.commit()
        except Exception as _commit_err:
            try:
                db.rollback()
            except Exception:
                pass
            print(f"[price_history] batch commit failed {symbol}: {_commit_err}")




# ---------------------------------------------------
# Batch downloader
# ---------------------------------------------------

def download_price_batch(
    symbols,
    batch_size=5,
    pause=1,
):

    """
    Multi-provider institutional price loader.

    Provider priority:
    1. Finnhub
    2. TwelveData

    Returns:
        {
            "AAPL": DataFrame,
            ...
        }
    """



    PROVIDERS = [

        finnhub_history,

        twelvedata_history,
    ]

    results = {}

    if not symbols:
        return results

    symbols = filter_supported_equities(
        symbols
    )

    total = len(symbols)

    print(
        f"🚀 DOWNLOAD PRICE BATCH START "
        f"({total} symbols)"
    )

    for i, symbol in enumerate(symbols):

        print(
            f"📈 [{i+1}/{total}] "
            f"{symbol}"
        )
        # -----------------------------------
        # Skip unsupported OTC/warrant/etc
        # -----------------------------------

        bad_suffixes = (
            "W",
            "WS",
            "U",
            "R",
        )

        if (
                len(symbol) > 5
                and symbol.endswith(bad_suffixes)
        ):
            continue
        success = False

        for provider in PROVIDERS:

            try:

                print(
                    "🔎 TRY PROVIDER:",
                    provider.__name__,
                    symbol,
                )

                df = provider(
                    symbol=symbol,
                    period="1y",
                    interval="1d",
                )

                if (
                    isinstance(df, pd.DataFrame)
                    and not df.empty
                ):

                    results[symbol] = df

                    print(
                        "✅ PROVIDER SUCCESS:",
                        provider.__name__,
                        symbol,
                        len(df),
                    )

                    success = True

                    break

                else:

                    print(
                        "⚠️ EMPTY DATA:",
                        provider.__name__,
                        symbol,
                    )

            except Exception as e:

                print(
                    "❌ PROVIDER FAILED:",
                    provider.__name__,
                    symbol,
                    e,
                )

        if not success:

            print(
                "❌ ALL PROVIDERS FAILED:",
                symbol,
            )

        time.sleep(pause)

    print(
        f"✅ DOWNLOAD COMPLETE: "
        f"{len(results)} / {total}"
    )

    return results


# ---------------------------------------------------
# Close matrix loader
# ---------------------------------------------------

def load_close_matrix(db: Session, symbols: list[str], *, lookback_days: int | None = None) -> pd.DataFrame:
    """
    lookback_days: when given, only rows from the last N calendar days
    are fetched -- for callers that only need a recent value (e.g. a
    1-day % change, which only ever reads the last two rows). Left as
    None (full history) for callers building longer return series
    (correlation, factor analysis), which need many months of data.

    Using calendar days rather than trading days as the cutoff is
    deliberate: a small buffer (7+ days) safely covers weekends and
    holidays without needing to know the market calendar here.
    """

    if not symbols:
        return pd.DataFrame()

    query = (
        db.query(
            PriceHistory.symbol,
            PriceHistory.date,
            PriceHistory.close,
        )
        .filter(PriceHistory.symbol.in_(symbols))
    )

    if lookback_days is not None:
        from datetime import datetime, timedelta, UTC
        cutoff = datetime.now(UTC) - timedelta(days=lookback_days)
        query = query.filter(PriceHistory.date >= cutoff)

    rows = query.order_by(PriceHistory.date.asc()).all()

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(
        [(r.symbol, r.date, r.close) for r in rows],
        columns=["symbol", "date", "close"],
    )

    if df.empty:
        return pd.DataFrame()

    pivot = df.pivot(index="date", columns="symbol", values="close")

    pivot.index = pd.to_datetime(pivot.index)

    pivot = pivot.sort_index()

    return pivot