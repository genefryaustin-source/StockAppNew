
from sqlalchemy import text
POSTGRES_SQL="""
CREATE TABLE IF NOT EXISTS execution_events(
 id BIGSERIAL PRIMARY KEY,
 event_id VARCHAR(36) UNIQUE NOT NULL,
 schema_version INT NOT NULL,
 event_type VARCHAR(64) NOT NULL,
 occurred_at TIMESTAMP NOT NULL,
 asset_class VARCHAR(32),
 account_id VARCHAR(64),
 portfolio_id VARCHAR(64),
 symbol VARCHAR(32),
 position_id VARCHAR(64),
 order_id VARCHAR(64),
 execution_id VARCHAR(64),
 correlation_id VARCHAR(64),
 causation_id VARCHAR(64),
 quantity DOUBLE PRECISION,
 price DOUBLE PRECISION,
 payload JSONB,
 metadata JSONB,
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
"""
SQLITE_SQL=POSTGRES_SQL.replace("BIGSERIAL","INTEGER").replace("JSONB","TEXT").replace("DOUBLE PRECISION","REAL").replace("VARCHAR","TEXT")
class ExecutionSchema:
    def __init__(self,db): self.db=db
    def ensure(self):
        d=self.db.bind.dialect.name.lower()
        self.db.execute(text(SQLITE_SQL if "sqlite" in d else POSTGRES_SQL)); self.db.commit()
