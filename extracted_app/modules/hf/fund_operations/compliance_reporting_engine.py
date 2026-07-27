from __future__ import annotations
from typing import Any


def build_compliance_report(risk: dict[str, Any], exposure: dict[str, Any]) -> dict[str, Any]:
    exceptions = []
    if float(risk.get('largest_position_weight') or 0) > 0.15:
        exceptions.append('Largest position exceeds 15% policy threshold.')
    if float(exposure.get('gross_exposure') or 0) > 1.25:
        exceptions.append('Gross exposure exceeds 125% policy threshold.')
    return {'status': 'Exceptions' if exceptions else 'Compliant', 'exceptions': exceptions, 'review_required': bool(exceptions)}
