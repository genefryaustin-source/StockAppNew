from __future__ import annotations
from typing import Any
from .common import safe_float
def build_recommendation(ticker: str, vote: dict[str,Any], consensus: dict[str,Any], council: dict[str,Any]) -> dict[str,Any]:
    rating=vote.get('consensus_rating','Hold'); decision=council.get('decision','Watchlist'); conv=safe_float(consensus.get('conviction_score'),50)
    if decision=='Approve' and rating in {'Strong Buy','Buy'}: action='Add to Approved Buy List'; size='Full starter position'
    elif decision=='Approve Small': action='Add Small / Watch for Confirmation'; size='Half starter position'
    elif decision=='Watchlist': action='Watchlist Only'; size='No allocation yet'
    else: action='Reject / Avoid'; size='No allocation'
    return {'ticker':ticker.upper(),'committee_rating':rating,'investment_council_decision':decision,'recommended_action':action,'suggested_position_size':size,'conviction':round(conv,1),'notes':['Requires final PM approval before live trading.','Use portfolio risk controls before allocation.']}
