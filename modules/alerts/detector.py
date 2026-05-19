# detector.py for Alerts
from dataclasses import dataclass
from typing import Optional, List, Dict

@dataclass
class DetectedAlert:
    alert_type: str
    title: str
    message: str
    last_price: Optional[float] = None
    support: Optional[float] = None
    resistance: Optional[float] = None
    previous_rating: Optional[str] = None
    new_rating: Optional[str] = None


def detect_rating_change(prev_rating: Optional[str], new_rating: Optional[str]) -> Optional[DetectedAlert]:
    if not prev_rating or not new_rating:
        return None
    if prev_rating == new_rating:
        return None
    return DetectedAlert(
        alert_type="RATING_CHANGE",
        title=f"Rating change: {prev_rating} → {new_rating}",
        message=f"Overall rating changed from {prev_rating} to {new_rating}.",
        previous_rating=prev_rating,
        new_rating=new_rating,
    )


def detect_breakout_breakdown(prev_close: Optional[float],
                              last_close: Optional[float],
                              support: Optional[float],
                              resistance: Optional[float]) -> List[DetectedAlert]:
    alerts: List[DetectedAlert] = []
    if prev_close is None or last_close is None:
        return alerts

    # Breakout: cross above resistance
    if resistance is not None and prev_close <= resistance and last_close > resistance:
        alerts.append(DetectedAlert(
            alert_type="BREAKOUT",
            title="Breakout above resistance",
            message=f"Price crossed above resistance. Prev close={prev_close:.2f}, last close={last_close:.2f}, resistance={resistance:.2f}.",
            last_price=last_close,
            resistance=resistance,
            support=support,
        ))

    # Breakdown: cross below support
    if support is not None and prev_close >= support and last_close < support:
        alerts.append(DetectedAlert(
            alert_type="BREAKDOWN",
            title="Breakdown below support",
            message=f"Price crossed below support. Prev close={prev_close:.2f}, last close={last_close:.2f}, support={support:.2f}.",
            last_price=last_close,
            resistance=resistance,
            support=support,
        ))

    return alerts


def detect_level_touch(last_close: Optional[float],
                       support: Optional[float],
                       resistance: Optional[float],
                       tolerance_pct: float = 0.003) -> List[DetectedAlert]:
    """
    Optional: emits LEVEL_TOUCH if price is within tolerance of support/resistance.
    tolerance_pct=0.003 ~ 0.3%
    """
    alerts: List[DetectedAlert] = []
    if last_close is None:
        return alerts

    def near(a: float, b: float) -> bool:
        if a is None or b is None:
            return False
        return abs(a - b) / max(b, 1e-9) <= tolerance_pct

    if support is not None and near(last_close, support):
        alerts.append(DetectedAlert(
            alert_type="LEVEL_TOUCH",
            title="Price near support",
            message=f"Price is near support. last close={last_close:.2f}, support={support:.2f}.",
            last_price=last_close,
            support=support,
            resistance=resistance,
        ))

    if resistance is not None and near(last_close, resistance):
        alerts.append(DetectedAlert(
            alert_type="LEVEL_TOUCH",
            title="Price near resistance",
            message=f"Price is near resistance. last close={last_close:.2f}, resistance={resistance:.2f}.",
            last_price=last_close,
            support=support,
            resistance=resistance,
        ))

    return alerts