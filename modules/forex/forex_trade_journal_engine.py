"""
modules/forex/forex_trade_journal_engine.py

Forex Trade Journal Engine

Provides journal persistence, trade review, setup classification, mistake
tagging, outcome attribution, and summary analytics for Forex trading.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from sqlalchemy import text
except Exception:
    text = None

try:
    from modules.forex.forex_performance_analytics_engine import (
        get_forex_performance_analytics_engine,
    )
except Exception:
    get_forex_performance_analytics_engine = None


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().replace(microsecond=0).isoformat()


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        out = float(value)
        if math.isnan(out) or math.isinf(out):
            return default
        return out
    except Exception:
        return default


def normalize_pair(pair: str) -> str:
    text = str(pair or "").upper().replace("-", "/").replace("_", "/").replace(" ", "")
    if "/" in text:
        left, right = text.split("/", 1)
        return f"{left[:3]}/{right[:3]}"
    if len(text) >= 6:
        return f"{text[:3]}/{text[3:6]}"
    return text


@dataclass
class ForexJournalEntry:
    pair: str
    side: str
    setup: str
    thesis: str
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    units: Optional[float] = None
    pnl: Optional[float] = None
    outcome: str = "OPEN"
    emotion: Optional[str] = None
    mistake_tags: Optional[str] = None
    lesson: Optional[str] = None
    screenshot_url: Optional[str] = None
    trade_order_id: Optional[str] = None
    portfolio_id: Optional[str] = None
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ForexTradeJournalEngine:

    def __init__(self, db=None):
        self.db = db
        self.performance = (
            get_forex_performance_analytics_engine(db=db)
            if get_forex_performance_analytics_engine
            else None
        )

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------

    def ensure_tables(self) -> None:
        if self.db is None or text is None:
            return

        self.db.execute(text("""
            CREATE TABLE IF NOT EXISTS forex_trade_journal (
                id SERIAL PRIMARY KEY,
                tenant_id VARCHAR(100),
                portfolio_id VARCHAR(100),
                user_id VARCHAR(100),
                trade_order_id VARCHAR(100),
                pair VARCHAR(20),
                side VARCHAR(20),
                setup VARCHAR(120),
                thesis TEXT,
                entry_price DOUBLE PRECISION,
                exit_price DOUBLE PRECISION,
                units DOUBLE PRECISION,
                pnl DOUBLE PRECISION,
                outcome VARCHAR(50),
                emotion VARCHAR(100),
                mistake_tags TEXT,
                lesson TEXT,
                screenshot_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        self.db.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_forex_trade_journal_pair
            ON forex_trade_journal(pair)
        """))

        self.db.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_forex_trade_journal_user
            ON forex_trade_journal(user_id)
        """))

        self.db.commit()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_entry(
        self,
        pair: str,
        side: str,
        setup: str,
        thesis: str,
        entry_price: Optional[float] = None,
        units: Optional[float] = None,
        trade_order_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        emotion: Optional[str] = None,
        screenshot_url: Optional[str] = None,
    ) -> Dict[str, Any]:

        entry = ForexJournalEntry(
            pair=normalize_pair(pair),
            side=str(side or "").upper(),
            setup=setup,
            thesis=thesis,
            entry_price=entry_price,
            units=units,
            outcome="OPEN",
            emotion=emotion,
            screenshot_url=screenshot_url,
            trade_order_id=trade_order_id,
            portfolio_id=portfolio_id,
            user_id=user_id,
            tenant_id=tenant_id,
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )

        if self.db is not None and text is not None:
            self.ensure_tables()
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            result = self.db.execute(text("""
                INSERT INTO forex_trade_journal (
                    tenant_id,
                    portfolio_id,
                    user_id,
                    trade_order_id,
                    pair,
                    side,
                    setup,
                    thesis,
                    entry_price,
                    units,
                    outcome,
                    emotion,
                    screenshot_url,
                    created_at,
                    updated_at
                )
                VALUES (
                    :tenant_id,
                    :portfolio_id,
                    :user_id,
                    :trade_order_id,
                    :pair,
                    :side,
                    :setup,
                    :thesis,
                    :entry_price,
                    :units,
                    :outcome,
                    :emotion,
                    :screenshot_url,
                    :created_at,
                    :updated_at
                )
                RETURNING id
            """), {
                "tenant_id": tenant_id,
                "portfolio_id": portfolio_id,
                "user_id": user_id,
                "trade_order_id": trade_order_id,
                "pair": entry.pair,
                "side": entry.side,
                "setup": setup,
                "thesis": thesis,
                "entry_price": entry_price,
                "units": units,
                "outcome": "OPEN",
                "emotion": emotion,
                "screenshot_url": screenshot_url,
                "created_at": now,
                "updated_at": now,
            })
            row = result.fetchone()
            self.db.commit()
            data = entry.to_dict()
            data["id"] = row[0] if row else None
            return data

        return entry.to_dict()

    def update_entry(
        self,
        entry_id: int,
        **updates,
    ) -> Dict[str, Any]:
        if self.db is None or text is None:
            updates["id"] = entry_id
            updates["status"] = "not_persisted"
            return updates

        self.ensure_tables()

        allowed = {
            "setup",
            "thesis",
            "exit_price",
            "units",
            "pnl",
            "outcome",
            "emotion",
            "mistake_tags",
            "lesson",
            "screenshot_url",
        }

        assignments = []
        params = {"id": int(entry_id), "updated_at": datetime.now(timezone.utc).replace(tzinfo=None)}

        for key, value in updates.items():
            if key in allowed:
                assignments.append(f"{key} = :{key}")
                params[key] = value

        if not assignments:
            return {"status": "no_changes", "id": entry_id}

        assignments.append("updated_at = :updated_at")

        self.db.execute(text(f"""
            UPDATE forex_trade_journal
            SET {', '.join(assignments)}
            WHERE id = :id
        """), params)
        self.db.commit()

        return self.get_entry(entry_id) or {"status": "updated", "id": entry_id}

    def close_entry(
        self,
        entry_id: int,
        exit_price: float,
        pnl: Optional[float] = None,
        outcome: Optional[str] = None,
        lesson: Optional[str] = None,
        mistake_tags: Optional[str] = None,
    ) -> Dict[str, Any]:
        current = self.get_entry(entry_id) or {}

        if outcome is None:
            pnl_value = safe_float(pnl)
            outcome = "WIN" if pnl_value > 0 else "LOSS" if pnl_value < 0 else "BREAKEVEN"

        return self.update_entry(
            entry_id,
            exit_price=exit_price,
            pnl=pnl,
            outcome=outcome,
            lesson=lesson,
            mistake_tags=mistake_tags,
        )

    def get_entry(self, entry_id: int) -> Optional[Dict[str, Any]]:
        if self.db is None or text is None:
            return None

        self.ensure_tables()

        row = self.db.execute(text("""
            SELECT *
            FROM forex_trade_journal
            WHERE id = :id
            LIMIT 1
        """), {"id": int(entry_id)}).fetchone()

        return dict(row._mapping) if row else None

    def list_entries(
        self,
        pair: Optional[str] = None,
        outcome: Optional[str] = None,
        setup: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        limit: int = 250,
    ) -> List[Dict[str, Any]]:
        if self.db is None or text is None:
            return []

        self.ensure_tables()

        where = ["1=1"]
        params: Dict[str, Any] = {"limit": int(limit)}

        if pair:
            where.append("pair = :pair")
            params["pair"] = normalize_pair(pair)

        if outcome:
            where.append("outcome = :outcome")
            params["outcome"] = str(outcome).upper()

        if setup:
            where.append("setup = :setup")
            params["setup"] = setup

        if portfolio_id:
            where.append("portfolio_id = :portfolio_id")
            params["portfolio_id"] = str(portfolio_id)

        if user_id:
            where.append("user_id = :user_id")
            params["user_id"] = str(user_id)

        if tenant_id:
            where.append("tenant_id = :tenant_id")
            params["tenant_id"] = str(tenant_id)

        rows = self.db.execute(text(f"""
            SELECT *
            FROM forex_trade_journal
            WHERE {' AND '.join(where)}
            ORDER BY created_at DESC
            LIMIT :limit
        """), params).fetchall()

        return [dict(r._mapping) for r in rows]

    # ------------------------------------------------------------------
    # Reviews / analytics
    # ------------------------------------------------------------------

    def review_trade(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        pnl = safe_float(entry.get("pnl"))
        outcome = str(entry.get("outcome") or "").upper()
        mistake_tags = str(entry.get("mistake_tags") or "")
        lesson = str(entry.get("lesson") or "")

        quality_score = 70.0

        if outcome == "WIN":
            quality_score += 10
        elif outcome == "LOSS":
            quality_score -= 10

        if mistake_tags:
            quality_score -= min(25, len([x for x in mistake_tags.split(",") if x.strip()]) * 5)

        if lesson:
            quality_score += 5

        return {
            "entry_id": entry.get("id"),
            "pair": entry.get("pair"),
            "outcome": outcome,
            "pnl": pnl,
            "quality_score": round(max(0, min(100, quality_score)), 2),
            "review": self._review_text(entry, quality_score),
            "mistake_tags": mistake_tags,
            "lesson": lesson,
        }

    def summarize(
        self,
        portfolio_id: Optional[str] = None,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        limit: int = 500,
    ) -> Dict[str, Any]:
        entries = self.list_entries(
            portfolio_id=portfolio_id,
            user_id=user_id,
            tenant_id=tenant_id,
            limit=limit,
        )

        closed = [e for e in entries if str(e.get("outcome") or "").upper() in {"WIN", "LOSS", "BREAKEVEN"}]
        wins = [e for e in closed if str(e.get("outcome") or "").upper() == "WIN"]
        losses = [e for e in closed if str(e.get("outcome") or "").upper() == "LOSS"]
        pnl = [safe_float(e.get("pnl")) for e in closed]

        setup_stats: Dict[str, Dict[str, Any]] = {}
        for e in closed:
            setup = e.get("setup") or "Unclassified"
            row = setup_stats.setdefault(setup, {"trades": 0, "wins": 0, "pnl": 0.0})
            row["trades"] += 1
            row["wins"] += 1 if str(e.get("outcome") or "").upper() == "WIN" else 0
            row["pnl"] += safe_float(e.get("pnl"))

        for setup, row in setup_stats.items():
            row["win_rate"] = round(row["wins"] / max(row["trades"], 1) * 100.0, 2)
            row["pnl"] = round(row["pnl"], 2)

        reviews = [self.review_trade(e) for e in closed[:50]]

        return {
            "generated_at": utc_now_iso(),
            "entries": len(entries),
            "closed_trades": len(closed),
            "open_trades": len(entries) - len(closed),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(len(wins) / max(len(closed), 1) * 100.0, 2),
            "net_pnl": round(sum(pnl), 2),
            "average_pnl": round(sum(pnl) / max(len(pnl), 1), 2),
            "setup_stats": setup_stats,
            "recent_reviews": reviews,
        }

    def search(
        self,
        query: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        if self.db is None or text is None:
            return []

        self.ensure_tables()

        q = f"%{query}%"
        rows = self.db.execute(text("""
            SELECT *
            FROM forex_trade_journal
            WHERE
                pair ILIKE :q
                OR setup ILIKE :q
                OR thesis ILIKE :q
                OR lesson ILIKE :q
                OR mistake_tags ILIKE :q
            ORDER BY created_at DESC
            LIMIT :limit
        """), {"q": q, "limit": int(limit)}).fetchall()

        return [dict(r._mapping) for r in rows]

    def _review_text(self, entry: Dict[str, Any], quality_score: float) -> str:
        outcome = str(entry.get("outcome") or "OPEN").upper()
        setup = entry.get("setup") or "Unclassified"
        mistake_tags = entry.get("mistake_tags")

        if outcome == "WIN":
            base = f"{setup} produced a winning Forex trade."
        elif outcome == "LOSS":
            base = f"{setup} resulted in a losing Forex trade."
        elif outcome == "BREAKEVEN":
            base = f"{setup} ended near breakeven."
        else:
            base = f"{setup} remains open."

        if mistake_tags:
            base += f" Review mistake tags: {mistake_tags}."

        if quality_score >= 80:
            base += " Execution quality appears strong."
        elif quality_score < 55:
            base += " Execution quality needs review."
        else:
            base += " Execution quality is acceptable."

        return base


_ENGINE = None


def get_forex_trade_journal_engine(db=None) -> ForexTradeJournalEngine:
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None):
        _ENGINE = ForexTradeJournalEngine(db=db)
    return _ENGINE
