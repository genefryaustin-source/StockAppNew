from contextlib import contextmanager
from sqlalchemy.orm import sessionmaker

class ForexDBSessionManager:

    def __init__(self, engine):
        self._session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def session(self):
        db = self._session_factory()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def execute(self, stmt, params=None):
        with self.session() as db:
            return db.execute(stmt, params or {})

    def fetchall(self, stmt, params=None):
        with self.session() as db:
            return db.execute(stmt, params or {}).fetchall()

    def fetchone(self, stmt, params=None):
        with self.session() as db:
            return db.execute(stmt, params or {}).fetchone()