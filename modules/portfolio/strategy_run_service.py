from __future__ import annotations

import json

try:
    from models.strategy_run import StrategyRun
except Exception:
    StrategyRun = None


class StrategyRunService:
    def __init__(self, db_session):
        self.db = db_session

    def log_run(
        self,
        portfolio_id: int,
        strategy_name: str,
        trigger_type: str,
        status: str,
        target_df=None,
        drift_threshold: float | None = None,
        notes: str | None = None,
    ):
        if StrategyRun is None:
            print("WARNING: StrategyRun model not available — skipping log.")
            return None

        payload = None

        if target_df is not None:
            try:
                if hasattr(target_df, "to_dict"):
                    payload = json.dumps(target_df.to_dict(orient="records"))
                else:
                    payload = json.dumps(target_df)
            except Exception:
                payload = None

        try:
            row = StrategyRun(
                portfolio_id=portfolio_id,
                strategy_name=strategy_name,
                trigger_type=trigger_type,
                status=status,
                target_snapshot=payload,
                drift_threshold=drift_threshold,
                notes=notes,
            )

            self.db.add(row)
            self.db.commit()
            self.db.refresh(row)

            return row

        except Exception as e:
            print(f"StrategyRun log failed: {e}")
            self.db.rollback()
            return None