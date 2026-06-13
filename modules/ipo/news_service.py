# ============================================================
# modules/ipo/news_service.py
# IPO & Pre-IPO News Service
#
# Compatible with: SQLite (local dev) + PostgreSQL / Neon (prod)
#
# Key compatibility decisions vs the first draft:
#
#  1. DateTime(timezone=True) on all timestamp columns.
#     Neon is strict about timezone-aware vs naive datetimes.
#     datetime.now(UTC) is tz-aware; without timezone=True on the
#     column SQLAlchemy emits a naive TIMESTAMP type in DDL and
#     Postgres will raise "can't compare offset-naive and
#     offset-aware datetimes" on INSERT/filter.
#
#  2. url column changed from Text → String(2048).
#     Postgres cannot build a B-tree index on an unbounded Text
#     column — create_all() raises "index row size exceeds
#     maximum 2712 for index".  String(2048) maps to
#     VARCHAR(2048) which is indexable on both SQLite and PG.
#
#  3. Boolean server_default added.
#     Python default= is only applied by SQLAlchemy at INSERT time
#     when the value is omitted in Python.  server_default="true"
#     ensures Neon's DDL emits DEFAULT TRUE so the column is
#     never null if a row is inserted via raw SQL or a future
#     migration tool.
#
#  4. Removed bare `index=True` from url — the composite
#     __table_args__ index covers tenant_id+url lookups and
#     avoids the unbounded-text-index problem entirely.
#
#  5. _now_utc() used consistently everywhere; no datetime.utcnow()
#     calls (deprecated in Python 3.12, produces naive datetimes).
#
#  6. Cutoff comparison uses timezone-aware datetime throughout so
#     Neon's TIMESTAMPTZ columns compare correctly.
# ============================================================

from __future__ import annotations

from datetime import datetime, UTC, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Session

from modules.db.core import Base
from modules.db.models import gen_uuid
from modules.ipo.news_providers import fetch_all_ipo_news, fetch_finnhub_company_news


# ---------------------------------------------------------------------------
# ORM Model
# ---------------------------------------------------------------------------

class IPONewsArticle(Base):
    __tablename__ = "ipo_news_articles"

    id          = Column(String,          primary_key=True, default=gen_uuid)
    tenant_id   = Column(String,          nullable=False)

    title       = Column(Text,            nullable=False)
    # VARCHAR(2048) — indexable on Postgres; Text is not directly indexable.
    url         = Column(String(2048),    nullable=True)
    source      = Column(String(256),     nullable=True)
    published_at= Column(DateTime(timezone=True), nullable=True)
    summary     = Column(Text,            nullable=True)

    # Bullish / Bearish / Neutral
    sentiment       = Column(String(32),  nullable=True)
    # Optional numeric score in [-1, 1] for future ML enrichment
    sentiment_score = Column(Float,       nullable=True)
    # Ticker or company name linked to this article
    company_hint    = Column(String(256), nullable=True)

    # server_default keeps the column non-null even for raw SQL inserts
    ipo_relevant = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        # Deduplication lookup — tenant + url
        Index("ix_ipo_news_url",            "tenant_id", "url"),
        # Feed queries — tenant + time window
        Index("ix_ipo_news_tenant_pub",     "tenant_id", "published_at"),
        # Per-company news lookup
        Index("ix_ipo_news_tenant_company", "tenant_id", "company_hint"),
        # Sentiment filter
        Index("ix_ipo_news_tenant_sent",    "tenant_id", "sentiment"),
        # Relevance filter (partial-index-like; full index on boolean is cheap)
        Index("ix_ipo_news_relevant",       "tenant_id", "ipo_relevant", "published_at"),
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _now_utc() -> datetime:
    """Always returns a timezone-aware UTC datetime — safe for Neon TIMESTAMPTZ."""
    return datetime.now(UTC)


def _coerce_pub_date(value: Any) -> Optional[datetime]:
    """
    Normalize published_at to a timezone-aware datetime.
    Accepts: datetime (naive or aware), ISO string, None.
    Returns None if unparseable.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            # Treat naive datetimes from providers as UTC
            return value.replace(tzinfo=UTC)
        return value
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt
        except Exception:
            return None
    return None


def _upsert_article(db: Session, tenant_id: str, article: Dict[str, Any]) -> bool:
    """
    Insert article if not already stored (dedup by tenant+url).
    Returns True if a new row was added.
    """
    url   = (article.get("url")   or "").strip()[:2048]
    title = (article.get("title") or "").strip()

    if not title:
        return False

    # Dedup by URL when present
    if url:
        exists = (
            db.query(IPONewsArticle.id)
            .filter(
                IPONewsArticle.tenant_id == tenant_id,
                IPONewsArticle.url == url,
            )
            .first()
        )
        if exists:
            return False

    pub = _coerce_pub_date(article.get("published_at"))

    db.add(IPONewsArticle(
        tenant_id       = tenant_id,
        title           = title,
        url             = url or None,
        source          = (article.get("source") or "")[:256] or None,
        published_at    = pub,
        summary         = (article.get("summary") or ""),
        sentiment       = (article.get("sentiment") or "Neutral")[:32],
        sentiment_score = article.get("sentiment_score"),
        company_hint    = (article.get("company_hint") or "")[:256] or None,
        ipo_relevant    = bool(article.get("ipo_relevant", True)),
    ))
    return True


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------

def refresh_ipo_news(
    db: Session,
    tenant_id: str,
    days_back: int = 7,
    symbol: Optional[str] = None,
) -> Dict[str, Any]:
    """Fetch fresh IPO/pre-IPO news from all providers and upsert into the DB."""
    articles = fetch_all_ipo_news(
        days_back=days_back,
        symbol=symbol,
        include_rss=True,
        include_newsapi=True,
        include_finnhub_market=True,
    )

    inserted = 0
    for art in articles:
        try:
            if _upsert_article(db, tenant_id, art):
                inserted += 1
        except Exception as e:
            db.rollback()
            print(f"[news_service] upsert error: {e}")

    db.commit()
    return {"fetched": len(articles), "inserted": inserted}


def refresh_company_news(
    db: Session,
    tenant_id: str,
    symbol: str,
    days_back: int = 14,
) -> Dict[str, Any]:
    """Targeted news refresh for a single ticker (e.g. from IPO watchlist)."""
    articles = fetch_finnhub_company_news(symbol=symbol, days_back=days_back)
    inserted = 0
    for art in articles:
        try:
            if _upsert_article(db, tenant_id, art):
                inserted += 1
        except Exception as e:
            db.rollback()
            print(f"[news_service] company upsert error: {e}")
    db.commit()
    return {"symbol": symbol, "fetched": len(articles), "inserted": inserted}


def list_ipo_news(
    db: Session,
    tenant_id: str,
    days_back: int = 14,
    sentiment_filter: Optional[str] = None,
    search: Optional[str] = None,
    company_hint: Optional[str] = None,
    limit: int = 100,
) -> List[IPONewsArticle]:
    # _now_utc() is tz-aware — safe to compare against DateTime(timezone=True)
    cutoff = _now_utc() - timedelta(days=days_back)

    q = (
        db.query(IPONewsArticle)
        .filter(
            IPONewsArticle.tenant_id    == tenant_id,
            IPONewsArticle.ipo_relevant == True,        # noqa: E712
            IPONewsArticle.published_at >= cutoff,
        )
    )

    if sentiment_filter and sentiment_filter.lower() != "all":
        q = q.filter(IPONewsArticle.sentiment == sentiment_filter)

    if company_hint:
        pattern = f"%{company_hint.strip()}%"
        q = q.filter(
            (IPONewsArticle.company_hint.ilike(pattern))
            | (IPONewsArticle.title.ilike(pattern))
        )

    if search:
        pattern = f"%{search.strip()}%"
        q = q.filter(
            (IPONewsArticle.title.ilike(pattern))
            | (IPONewsArticle.summary.ilike(pattern))
            | (IPONewsArticle.source.ilike(pattern))
        )

    return q.order_by(IPONewsArticle.published_at.desc()).limit(limit).all()


def news_to_dataframe(articles: List[IPONewsArticle]) -> pd.DataFrame:
    rows = []
    for a in articles or []:
        summary = a.summary or ""
        rows.append({
            "Published": a.published_at,
            "Title":     a.title,
            "Source":    a.source,
            "Sentiment": a.sentiment,
            "Company":   a.company_hint,
            "Summary":   summary[:160] + ("..." if len(summary) > 160 else ""),
            "URL":       a.url,
        })
    df = pd.DataFrame(rows)
    if not df.empty and "Published" in df.columns:
        df["Published"] = pd.to_datetime(df["Published"], errors="coerce", utc=True)
    return df


def sentiment_summary(
    db: Session,
    tenant_id: str,
    days_back: int = 14,
    company_hint: Optional[str] = None,
) -> Dict[str, Any]:
    """Returns sentiment counts and a net-sentiment score (Bull% - Bear%)."""
    articles = list_ipo_news(
        db=db,
        tenant_id=tenant_id,
        days_back=days_back,
        company_hint=company_hint,
        limit=500,
    )
    total = len(articles)
    if total == 0:
        return {
            "total": 0, "bullish": 0, "bearish": 0, "neutral": 0,
            "net_sentiment": 0.0, "label": "Neutral",
        }

    bull    = sum(1 for a in articles if a.sentiment == "Bullish")
    bear    = sum(1 for a in articles if a.sentiment == "Bearish")
    neutral = total - bull - bear
    net     = round((bull - bear) / total * 100, 1)

    label = "Bullish" if net >= 15 else ("Bearish" if net <= -15 else "Neutral")

    return {
        "total": total, "bullish": bull, "bearish": bear,
        "neutral": neutral, "net_sentiment": net, "label": label,
    }


def source_breakdown(
    db: Session,
    tenant_id: str,
    days_back: int = 14,
) -> pd.DataFrame:
    cutoff = _now_utc() - timedelta(days=days_back)
    rows = (
        db.query(
            IPONewsArticle.source,
            func.count(IPONewsArticle.id).label("count"),
        )
        .filter(
            IPONewsArticle.tenant_id    == tenant_id,
            IPONewsArticle.published_at >= cutoff,
            IPONewsArticle.ipo_relevant == True,        # noqa: E712
        )
        .group_by(IPONewsArticle.source)
        .order_by(func.count(IPONewsArticle.id).desc())
        .all()
    )
    return pd.DataFrame([
        {"Source": r.source or "Unknown", "Articles": r.count}
        for r in rows
    ])


def sentiment_over_time(
    db: Session,
    tenant_id: str,
    days_back: int = 30,
) -> pd.DataFrame:
    """Returns daily sentiment counts for stacked bar charting."""
    cutoff = _now_utc() - timedelta(days=days_back)
    articles = (
        db.query(IPONewsArticle)
        .filter(
            IPONewsArticle.tenant_id    == tenant_id,
            IPONewsArticle.published_at >= cutoff,
            IPONewsArticle.ipo_relevant == True,        # noqa: E712
        )
        .all()
    )

    if not articles:
        return pd.DataFrame(columns=["Date", "Bullish", "Bearish", "Neutral"])

    df = pd.DataFrame([{
        "date":      a.published_at.date() if a.published_at else None,
        "sentiment": a.sentiment or "Neutral",
    } for a in articles]).dropna(subset=["date"])

    pivot = (
        df.groupby(["date", "sentiment"])
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )
    pivot.columns.name = None

    for col in ["Bullish", "Bearish", "Neutral"]:
        if col not in pivot.columns:
            pivot[col] = 0

    return pivot.rename(columns={"date": "Date"}).sort_values("Date")