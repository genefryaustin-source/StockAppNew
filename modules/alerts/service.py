
# service.py for Alerts
from datetime import datetime, UTC
from sqlalchemy.orm import Session

from models.trading import Portfolio
from modules.alerts.models import AlertEvent
from modules.alerts.detector import (
    detect_rating_change,
    detect_breakout_breakdown,
    detect_level_touch,
)
from modules.analytics.models import AnalyticsSnapshot

from modules.market_data.settings import md_secrets


def _exists_recent(db: Session, tenant_id: str, symbol: str, alert_type: str, title: str, minutes: int = 120) -> bool:
    cutoff = datetime.now(UTC).timestamp() - (minutes * 60)
    # Compare using created_at (datetime); do conservative filter
    rows = (db.query(AlertEvent)
            .filter(AlertEvent.tenant_id == tenant_id,
                    AlertEvent.symbol == symbol,
                    AlertEvent.alert_type == alert_type,
                    AlertEvent.title == title)
            .order_by(AlertEvent.created_at.desc())
            .limit(1)
            .all())
    if not rows:
        return False
    latest = rows[0]
    return latest.created_at.timestamp() >= cutoff


def run_alert_checks(db: Session, tenant_id: str, symbol: str, include_level_touch: bool = False) -> int:
    sym = symbol.upper()

    snaps = (
        db.query(AnalyticsSnapshot)
        .filter(AnalyticsSnapshot.symbol == sym)
        .order_by(AnalyticsSnapshot.asof.desc())
        .all()
    )

    print("ALERT DB:", db.bind.url)

    latest = snaps[0] if len(snaps) > 0 else None
    prev = snaps[1] if len(snaps) >= 2 else None

    prev_rating = prev.rating if prev else None
    new_rating = latest.rating if latest else None

    support = latest.support if latest else None
    resistance = latest.resistance if latest else None

    from modules.market_data.service import get_price_history
    px = get_price_history(db, sym, period="3mo", interval="1d")

    prev_close = None
    last_close = None
    if px is not None and not px.empty and len(px) >= 2:
        prev_close = float(px.iloc[-2]["Close"])
        last_close = float(px.iloc[-1]["Close"])

    created = 0

    print(
        "ALERT DEBUG:",
        "sym=", sym,
        "latest_exists=", latest is not None,
        "signal=", getattr(latest, "signal", None) if latest else None,
        "composite=", getattr(latest, "composite_score", None) if latest else None,
        "sentiment=", getattr(latest, "sentiment_score", None) if latest else None,
    )

    # --------------------------------------------------
    # SIGNAL / SENTIMENT / COMPOSITE ALERTS
    # --------------------------------------------------
    if latest:
        signal = getattr(latest, "signal", None)
        composite = getattr(latest, "composite_score", None)
        sentiment = getattr(latest, "sentiment_score", None)

        print("ALERT BRANCH INPUTS:", sym, signal, composite, sentiment)

        if signal in ["Buy", "Strong Buy"]:
            print("ALERT BRANCH: BUY")
            title = "🚀 Buy Signal"
            if not _exists_recent(db, tenant_id, sym, "signal", title):
                db.add(AlertEvent(
                    tenant_id=tenant_id,
                    symbol=sym,
                    alert_type="signal",
                    title=title,
                    message=f"{sym} generated a BUY signal (composite {composite:.1f})"
                    if composite is not None else f"{sym} generated a BUY signal",
                    last_price=last_close,
                    support=support,
                    resistance=resistance,
                    previous_rating=prev_rating,
                    new_rating=new_rating,
                ))
                created += 1

        elif signal in ["Sell", "Strong Sell"]:
            print("ALERT BRANCH: SELL")
            title = "⚠️ Sell Signal"
            if not _exists_recent(db, tenant_id, sym, "signal", title):
                db.add(AlertEvent(
                    tenant_id=tenant_id,
                    symbol=sym,
                    alert_type="signal",
                    title=title,
                    message=f"{sym} generated a SELL signal (composite {composite:.1f})"
                    if composite is not None else f"{sym} generated a SELL signal",
                    last_price=last_close,
                    support=support,
                    resistance=resistance,
                    previous_rating=prev_rating,
                    new_rating=new_rating,
                ))
                created += 1

        if composite is not None and composite >= 65:
            print("ALERT BRANCH: STRONG COMPOSITE")
            title = "🔥 Strong Composite"
            if not _exists_recent(db, tenant_id, sym, "composite", title):
                db.add(AlertEvent(
                    tenant_id=tenant_id,
                    symbol=sym,
                    alert_type="composite",
                    title=title,
                    message=f"{sym} has a strong composite score ({composite:.1f})",
                    last_price=last_close,
                    support=support,
                    resistance=resistance,
                    previous_rating=prev_rating,
                    new_rating=new_rating,
                ))
                created += 1

        elif composite is not None and composite <= 30:
            print("ALERT BRANCH: WEAK COMPOSITE")
            title = "❄️ Weak Composite"
            if not _exists_recent(db, tenant_id, sym, "composite", title):
                db.add(AlertEvent(
                    tenant_id=tenant_id,
                    symbol=sym,
                    alert_type="composite",
                    title=title,
                    message=f"{sym} has a weak composite score ({composite:.1f})",
                    last_price=last_close,
                    support=support,
                    resistance=resistance,
                    previous_rating=prev_rating,
                    new_rating=new_rating,
                ))
                created += 1

        if sentiment is not None and sentiment > 0.1:
            print("ALERT BRANCH: POSITIVE SENTIMENT")
            title = "📰 Positive Sentiment"
            if not _exists_recent(db, tenant_id, sym, "sentiment", title):
                db.add(AlertEvent(
                    tenant_id=tenant_id,
                    symbol=sym,
                    alert_type="sentiment",
                    title=title,
                    message=f"{sym} has positive news sentiment ({sentiment:.2f})",
                    last_price=last_close,
                    support=support,
                    resistance=resistance,
                    previous_rating=prev_rating,
                    new_rating=new_rating,
                ))
                created += 1

        elif sentiment is not None and sentiment < -0.1:
            print("ALERT BRANCH: NEGATIVE SENTIMENT")
            title = "📰 Negative Sentiment"
            if not _exists_recent(db, tenant_id, sym, "sentiment", title):
                db.add(AlertEvent(
                    tenant_id=tenant_id,
                    symbol=sym,
                    alert_type="sentiment",
                    title=title,
                    message=f"{sym} has negative news sentiment ({sentiment:.2f})",
                    last_price=last_close,
                    support=support,
                    resistance=resistance,
                    previous_rating=prev_rating,
                    new_rating=new_rating,
                ))
                created += 1

    # --------------------------------------------------
    # BREAKOUT / BREAKDOWN ALERTS
    # --------------------------------------------------
    for a in detect_breakout_breakdown(prev_close, last_close, support, resistance):
        if not _exists_recent(db, tenant_id, sym, a.alert_type, a.title):
            db.add(AlertEvent(
                tenant_id=tenant_id,
                symbol=sym,
                alert_type=a.alert_type,
                title=a.title,
                message=a.message,
                last_price=a.last_price,
                support=a.support,
                resistance=a.resistance,
                previous_rating=prev_rating,
                new_rating=new_rating,
            ))
            created += 1

    # --------------------------------------------------
    # OPTIONAL LEVEL-TOUCH ALERTS
    # --------------------------------------------------
    if include_level_touch:
        for a in detect_level_touch(last_close, support, resistance):
            if not _exists_recent(db, tenant_id, sym, a.alert_type, a.title):
                db.add(AlertEvent(
                    tenant_id=tenant_id,
                    symbol=sym,
                    alert_type=a.alert_type,
                    title=a.title,
                    message=a.message,
                    last_price=a.last_price,
                    support=a.support,
                    resistance=a.resistance,
                    previous_rating=prev_rating,
                    new_rating=new_rating,
                ))
                created += 1

    db.commit()

    # --------------------------------------------------
    # AUTO TRADE TRIGGER
    # --------------------------------------------------
    try:
        from modules.portfolio.auto_rebalance_service import run_auto_rebalance

        AUTO_TRADE_ENABLED = True

        print("AUTO TRADE DEBUG:", {
            "enabled": AUTO_TRADE_ENABLED,
            "symbol": sym,
            "created": created,
            "latest_exists": latest is not None,
            "signal": getattr(latest, "signal", None) if latest else None,
            "confidence": getattr(latest, "confidence_score", None) if latest else None,
        })

        if AUTO_TRADE_ENABLED and latest is not None:
            signal = getattr(latest, "signal", None)
            confidence = float(getattr(latest, "confidence_score", 0) or 0)

            # relax this for testing
            if signal in ["Buy", "Strong Buy", "Sell", "Strong Sell"] and confidence >= 0:
                print(f"🚀 AUTO TRADE TRIGGERED: {sym}")

                portfolio = (
                    db.query(Portfolio)
                    .filter(
                        Portfolio.tenant_id == tenant_id,
                        Portfolio.is_active == True,  # noqa: E712
                    )
                    .order_by(Portfolio.id.asc())
                    .first()
                )

                if portfolio:
                    print(f"🚀 AUTO REBALANCE START: portfolio_id={portfolio.id}")
                    run_auto_rebalance(db, tenant_id, portfolio.id)
                else:
                    print(f"⚠️ AUTO TRADE ERROR: no active portfolio found for tenant {tenant_id}")

    except Exception as e:
        print("⚠️ AUTO TRADE ERROR:", e)

    print("ALERT DEBUG CREATED:", created)
    return created


def list_alerts(db: Session, tenant_id: str, symbol: str | None = None, only_unack: bool = False, limit: int = 200):
    q = db.query(AlertEvent).filter(AlertEvent.tenant_id == tenant_id)
    if symbol:
        q = q.filter(AlertEvent.symbol == symbol.upper())
    if only_unack:
        q = q.filter(AlertEvent.acknowledged == False)  # noqa: E712
    return q.order_by(AlertEvent.created_at.desc()).limit(limit).all()


def acknowledge_alert(db: Session, tenant_id: str, alert_id: str):
    row = (db.query(AlertEvent)
           .filter(AlertEvent.tenant_id == tenant_id, AlertEvent.id == alert_id)
           .first())
    if not row:
        return False
    row.acknowledged = True
    row.acknowledged_at = datetime.now(UTC)
    db.commit()
    return True

# ---------------------------------
# 🔔 ALERT SERVICE WRAPPER (COMPAT)
# ---------------------------------
class AlertService:
    def __init__(self, db_session):
        self.db = db_session

    def create_alert(
            self,
            portfolio_id=None,
            symbol=None,
            alert_type="general",
            message="",
            severity="info"
    ):
        try:
            # ✅ SAFE IMPORT (fixes PyCharm + runtime)
            try:
                from modules.alerts.service import create_alert as create_alert_fn
            except ImportError:
                create_alert_fn = None

            if create_alert_fn:
                return create_alert_fn(
                    db=self.db,
                    portfolio_id=portfolio_id,
                    symbol=symbol,
                    alert_type=alert_type,
                    message=message,
                    severity=severity,
                )

            # ---------------------------------
            # Fallback: direct DB insert
            # ---------------------------------
            from modules.alerts.models import AlertEvent
            from datetime import datetime

            alert = AlertEvent(
                portfolio_id=portfolio_id,
                symbol=symbol,
                alert_type=alert_type,
                message=message,
                severity=severity,
                created_at=datetime.now(UTC)
            )

            self.db.add(alert)
            self.db.commit()

            return alert

        except Exception as e:
            print("ALERT SERVICE ERROR:", e)
            return None




