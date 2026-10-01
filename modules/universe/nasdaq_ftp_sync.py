"""
modules/universe/nasdaq_ftp_sync.py

Bulk symbol ingestion from NASDAQ Trader's official symbol directory --
free, no API key, no signup, updated multiple times per trading day:

    ftp://ftp.nasdaqtrader.com/SymbolDirectory/nasdaqlisted.txt   (NASDAQ-listed)
    ftp://ftp.nasdaqtrader.com/SymbolDirectory/otherlisted.txt    (NYSE/AMEX/other)

This is the same source most commercial data vendors ultimately build
their own symbol lists from. Replaces manually typing/pasting symbols one
at a time (or preparing a CSV by hand) with a one-click pull of
essentially the entire US equity market (~8,000+ symbols).

Parsing is done by HEADER NAME, not fixed column position -- both files
are pipe-delimited with a header row and a "File Creation Time: ..."
footer row. NASDAQ's own docs describe this layout, but rather than trust
a hardcoded column order (which would silently corrupt data if NASDAQ
ever reordered fields), each row is parsed into a dict keyed by whatever
the file's own header row says.

Two things this writes to:
  - security_master: the tenant-agnostic reference table (exchange,
    is_etf, source) -- authoritative, shared across all tenants.
  - universe_symbols: per-tenant, per-universe membership.

IMPORTANT (read before changing this file again): this sync used to take
a single `universe_id` and dump EVERY fetched symbol -- every exchange,
stocks and ETFs alike -- into whatever universe the caller passed in.
That one-size-fits-all target was always wrong (the whole point of this
sync is "all US symbols", which spans several different real-world
listing venues and security types), and in production it twice corrupted
a tenant's single-purpose universe (S&P 500, then NYSE) when the sync was
run while that universe happened to be selected in the UI, ballooning it
to ~13,000 symbols. This version removes the target `universe_id`
entirely and instead classifies every symbol by its real exchange + ETF
flag (already computed by fetch_and_parse_nasdaq_universe below) and
routes it into the one correctly-named per-tenant universe for that
category -- creating that universe first if the tenant doesn't have it
yet. There is no longer a way to point this sync at an arbitrary
universe, which is what made the corruption possible in the first place.
"""

from __future__ import annotations

import ftplib
import io
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Optional

NASDAQ_FTP_HOST = "ftp.nasdaqtrader.com"
NASDAQ_FTP_DIR = "SymbolDirectory"
NASDAQ_LISTED_FILE = "nasdaqlisted.txt"
OTHER_LISTED_FILE = "otherlisted.txt"

FOOTER_PREFIX = "File Creation Time"

# Maps a fetched symbol's (exchange code, is_etf) to the canonical
# per-tenant universe name it belongs in. Exchange codes not listed here
# (NYSE Arca "P", Cboe BZX "Z", IEXG "V", "F", "M") aren't routed anywhere
# -- they don't correspond to a universe this app currently models, and
# silently inventing new ones for exchanges nobody asked for would be its
# own kind of surprise. Symbols on those exchanges are counted and
# reported as skipped rather than dropped silently.
_EXCHANGE_UNIVERSE_MAP = {
    ("NASDAQ", False): "NASDAQ",
    ("NASDAQ", True):  "NASDAQ ETFs",
    ("N", False):      "NYSE",
    ("N", True):       "NYSE ETFs",
    ("A", False):      "AMEX",
    ("A", True):       "AMEX ETFs",
}


@dataclass
class NasdaqSyncResult:
    available: bool
    fetched: int = 0
    security_master_upserted: int = 0
    universe_symbols_added: int = 0
    universe_symbols_already_present: int = 0
    skipped_unmapped_exchange: int = 0
    nasdaq_listed_count: int = 0
    other_listed_count: int = 0
    per_universe_added: dict = field(default_factory=dict)
    error: Optional[str] = None


def _fetch_ftp_text(filename: str, timeout: int = 30) -> str:
    """Fetches one file from the NASDAQ Trader anonymous FTP server as text."""
    buffer = io.BytesIO()
    ftp = ftplib.FTP(NASDAQ_FTP_HOST, timeout=timeout)
    try:
        ftp.login()  # anonymous, no credentials required
        ftp.cwd(NASDAQ_FTP_DIR)
        ftp.retrbinary(f"RETR {filename}", buffer.write)
    finally:
        try:
            ftp.quit()
        except Exception:
            ftp.close()
    return buffer.getvalue().decode("utf-8", errors="replace")


def _parse_pipe_delimited(text: str) -> list[dict]:
    """
    Parses NASDAQ's pipe-delimited symbol directory format into a list of
    dicts keyed by the file's own header row -- never assumes a fixed
    column order. Skips the trailing "File Creation Time: ..." footer row
    and any malformed rows (wrong field count) rather than raising.
    """
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return []

    header = [h.strip() for h in lines[0].split("|")]
    rows = []
    for line in lines[1:]:
        if line.startswith(FOOTER_PREFIX):
            continue
        fields = line.split("|")
        if len(fields) != len(header):
            continue  # malformed row -- skip rather than misalign columns
        rows.append(dict(zip(header, [f.strip() for f in fields])))
    return rows


def _is_test_issue(row: dict) -> bool:
    return str(row.get("Test Issue", "N")).strip().upper() == "Y"


def _is_etf(row: dict) -> bool:
    return str(row.get("ETF", "N")).strip().upper() == "Y"


def fetch_and_parse_nasdaq_universe() -> dict:
    """
    Returns {"available": True, "symbols": [...]} where each entry is
    {"symbol": str, "company_name": str, "exchange": str, "is_etf": bool,
    "source": "NASDAQ_FTP"}, deduplicated across both files (a symbol
    listed in both takes the nasdaqlisted.txt entry). Returns
    {"available": False, "reason": ...} on any fetch/parse failure --
    never raises, since this is meant to be safe to wire behind a single
    admin button click.
    """
    try:
        nasdaq_text = _fetch_ftp_text(NASDAQ_LISTED_FILE)
        other_text = _fetch_ftp_text(OTHER_LISTED_FILE)
    except Exception as e:
        return {"available": False, "reason": f"Could not reach NASDAQ Trader FTP: {e}"}

    try:
        nasdaq_rows = _parse_pipe_delimited(nasdaq_text)
        other_rows = _parse_pipe_delimited(other_text)
    except Exception as e:
        return {"available": False, "reason": f"Failed to parse NASDAQ symbol files: {e}"}

    symbols: dict[str, dict] = {}

    for row in nasdaq_rows:
        if _is_test_issue(row):
            continue
        sym = (row.get("Symbol") or "").strip().upper()
        if not sym:
            continue
        symbols[sym] = {
            "symbol": sym,
            "company_name": row.get("Security Name", ""),
            "exchange": "NASDAQ",
            "is_etf": _is_etf(row),
            "source": "NASDAQ_FTP",
        }

    for row in other_rows:
        if _is_test_issue(row):
            continue
        sym = (row.get("ACT Symbol") or row.get("NASDAQ Symbol") or "").strip().upper()
        if not sym or sym in symbols:
            continue  # nasdaqlisted.txt entry takes priority on overlap
        symbols[sym] = {
            "symbol": sym,
            "company_name": row.get("Security Name", ""),
            "exchange": row.get("Exchange", "OTHER"),
            "is_etf": _is_etf(row),
            "source": "NASDAQ_FTP",
        }

    return {
        "available": True,
        "symbols": list(symbols.values()),
        "nasdaq_listed_count": len(nasdaq_rows),
        "other_listed_count": len(other_rows),
    }


def sync_universe_from_nasdaq_ftp(db, tenant_id: str) -> NasdaqSyncResult:
    """
    One-click bulk sync: pulls the full NASDAQ Trader symbol directory,
    upserts security_master (tenant-agnostic reference data), and routes
    each symbol into the ONE correctly-named per-tenant universe for its
    real exchange + ETF status (NASDAQ, NASDAQ ETFs, NYSE, NYSE ETFs,
    AMEX, AMEX ETFs) -- creating that universe for the tenant first if it
    doesn't exist yet. See the module docstring for why this no longer
    takes a target universe_id.
    """
    fetched = fetch_and_parse_nasdaq_universe()
    if not fetched.get("available"):
        return NasdaqSyncResult(available=False, error=fetched.get("reason"))

    symbols = fetched["symbols"]
    if not symbols:
        return NasdaqSyncResult(available=False, error="NASDAQ returned no usable symbols.")

    sm_count = _bulk_upsert_security_master(db, symbols)

    by_universe_name: dict[str, list[str]] = {}
    skipped_unmapped = 0
    for row in symbols:
        target_name = _EXCHANGE_UNIVERSE_MAP.get((row["exchange"], row["is_etf"]))
        if target_name is None:
            skipped_unmapped += 1
            continue
        by_universe_name.setdefault(target_name, []).append(row["symbol"])

    total_added = 0
    total_already_present = 0
    per_universe_added: dict[str, int] = {}

    for universe_name, syms in by_universe_name.items():
        universe_id = _find_or_create_universe(db, tenant_id, universe_name)
        added, already_present = _bulk_add_universe_symbols(db, tenant_id, universe_id, syms)
        total_added += added
        total_already_present += already_present
        per_universe_added[universe_name] = added

    return NasdaqSyncResult(
        available=True,
        fetched=len(symbols),
        security_master_upserted=sm_count,
        universe_symbols_added=total_added,
        universe_symbols_already_present=total_already_present,
        skipped_unmapped_exchange=skipped_unmapped,
        nasdaq_listed_count=fetched.get("nasdaq_listed_count", 0),
        other_listed_count=fetched.get("other_listed_count", 0),
        per_universe_added=per_universe_added,
    )


def _find_or_create_universe(db, tenant_id: str, name: str) -> str:
    """Looks up this tenant's universe by name (case-insensitive, same
    matching rule used by the shared-universe propagation feature), or
    creates it if the tenant doesn't have one yet. Returns the
    universe_id either way."""
    from sqlalchemy import func
    from modules.universe.models import Universe
    from modules.db.models import gen_uuid

    existing = (
        db.query(Universe)
        .filter(Universe.tenant_id == tenant_id, func.lower(Universe.name) == name.lower())
        .first()
    )
    if existing:
        return existing.id

    new_id = gen_uuid()
    db.add(Universe(
        id=new_id,
        name=name,
        tenant_id=tenant_id,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    ))
    db.commit()
    return new_id


def _bulk_upsert_security_master(db, symbols: list[dict]) -> int:
    from modules.universe.models import SecurityMaster

    existing = {s.symbol: s for s in db.query(SecurityMaster).all()}
    now = datetime.now(UTC)
    count = 0
    for row in symbols:
        sym = row["symbol"]
        existing_row = existing.get(sym)
        if existing_row:
            existing_row.exchange = row["exchange"]
            existing_row.is_etf = 1 if row["is_etf"] else 0
            existing_row.source = row["source"]
            existing_row.updated_at = now
        else:
            db.add(SecurityMaster(
                symbol=sym, exchange=row["exchange"], is_etf=1 if row["is_etf"] else 0,
                source=row["source"], updated_at=now,
            ))
        count += 1
        if count % 1000 == 0:
            db.commit()  # flush periodically so one huge transaction doesn't balloon
    db.commit()
    return count


def _bulk_add_universe_symbols(db, tenant_id: str, universe_id: str, symbols: list[str]) -> tuple[int, int]:
    from modules.universe.models import UniverseSymbol

    existing_symbols = {
        s.symbol
        for s in db.query(UniverseSymbol.symbol)
        .filter(UniverseSymbol.tenant_id == tenant_id, UniverseSymbol.universe_id == universe_id)
        .all()
    }

    to_add = [sym for sym in symbols if sym not in existing_symbols]
    already_present = len(symbols) - len(to_add)

    for i, sym in enumerate(to_add):
        db.add(UniverseSymbol(symbol=sym, tenant_id=tenant_id, universe_id=universe_id))
        if (i + 1) % 1000 == 0:
            db.commit()
    db.commit()

    return len(to_add), already_present