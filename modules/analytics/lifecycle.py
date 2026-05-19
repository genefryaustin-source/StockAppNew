from sqlalchemy import text
from modules.analytics.models import AnalyticsSnapshot


def should_refresh(snapshot) -> bool:
    """
    Determines if analytics needs rebuild
    (prevents unnecessary deletes)
    """

    if not snapshot:
        return True

    # 🔥 critical missing fields
    if snapshot.pe_ttm is None:
        return True

    if snapshot.gross_margin is None:
        return True

    if snapshot.composite_score is None:
        return True

    return False


def reset_symbol_state(db, symbol: str):
    """
    Safe reset of symbol data
    """

    try:
        db.execute(
            text("DELETE FROM analytics_snapshots WHERE symbol = :symbol"),
            {"symbol": symbol},
        )

        db.execute(
            text("DELETE FROM fundamental_snapshots WHERE symbol = :symbol"),
            {"symbol": symbol},
        )

        db.commit()

        return True

    except Exception as e:
        db.rollback()
        print("LIFECYCLE RESET ERROR:", e)
        return False