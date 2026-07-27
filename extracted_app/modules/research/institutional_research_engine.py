from __future__ import annotations
from typing import Any
from .fundamental_signal_engine import build_fundamental_signal
from .earnings_intelligence_engine import build_earnings_intelligence
from .analyst_consensus_engine import build_analyst_consensus
from .estimate_revision_engine import build_estimate_revisions
from .institutional_ownership_engine import build_institutional_ownership
from .macro_intelligence_engine import build_macro_intelligence
from .sector_rotation_engine import build_sector_rotation
from .market_regime_engine import build_market_regime
from .catalyst_tracker import build_catalyst_tracker
from .research_scorecard import build_research_scorecard
from .thesis_generation_engine import generate_investment_thesis
from .thesis_validation_engine import validate_thesis
from .research_utils import _now_iso


def build_institutional_research_report(ticker: str) -> dict[str, Any]:
    components = {
        "fundamental": build_fundamental_signal(ticker),
        "earnings": build_earnings_intelligence(ticker),
        "analyst": build_analyst_consensus(ticker),
        "revisions": build_estimate_revisions(ticker),
        "ownership": build_institutional_ownership(ticker),
        "macro": build_macro_intelligence(ticker),
        "sector": build_sector_rotation(ticker),
        "regime": build_market_regime(ticker),
        "catalysts": build_catalyst_tracker(ticker),
    }
    scorecard = build_research_scorecard(components)
    thesis = generate_investment_thesis(ticker, components, scorecard)
    validation = validate_thesis(ticker, thesis, scorecard)
    return {"ticker": ticker.upper(), "generated_at": _now_iso(), "components": components, "scorecard": scorecard, "thesis": thesis, "validation": validation}
