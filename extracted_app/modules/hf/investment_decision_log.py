from __future__ import annotations
from typing import Any
from sqlalchemy import text
from .common import utc_now, to_json
import uuid
def ensure_decision_tables(db: Any) -> None:
    if db is None: return
    db.execute(text('''CREATE TABLE IF NOT EXISTS hf_investment_decisions (id TEXT PRIMARY KEY, tenant_id TEXT, user_id TEXT, ticker TEXT NOT NULL, decision TEXT, rating TEXT, score REAL, payload_json TEXT, created_at TEXT)'''))
    try: db.commit()
    except Exception: pass
def log_investment_decision(db: Any, tenant_id: str, user_id: str, ticker: str, payload: dict[str,Any]) -> str:
    if db is None: return ''
    ensure_decision_tables(db); oid=str(uuid.uuid4())
    db.execute(text('''INSERT INTO hf_investment_decisions (id,tenant_id,user_id,ticker,decision,rating,score,payload_json,created_at) VALUES (:id,:tenant_id,:user_id,:ticker,:decision,:rating,:score,:payload_json,:created_at)'''), {'id':oid,'tenant_id':tenant_id,'user_id':user_id,'ticker':ticker.upper(),'decision':payload.get('council',{}).get('decision'),'rating':payload.get('vote',{}).get('consensus_rating'),'score':payload.get('scorecard',{}).get('composite_research_score'),'payload_json':to_json(payload),'created_at':utc_now()})
    try: db.commit()
    except Exception: pass
    return oid
def get_decision_history(db: Any, ticker: str|None=None, limit: int=50) -> list[dict[str,Any]]:
    if db is None: return []
    try:
        ensure_decision_tables(db)
        if ticker: rows=db.execute(text('SELECT * FROM hf_investment_decisions WHERE upper(ticker)=upper(:ticker) ORDER BY created_at DESC LIMIT :limit'), {'ticker':ticker,'limit':limit}).mappings().fetchall()
        else: rows=db.execute(text('SELECT * FROM hf_investment_decisions ORDER BY created_at DESC LIMIT :limit'), {'limit':limit}).mappings().fetchall()
        return [dict(r) for r in rows]
    except Exception: return []
