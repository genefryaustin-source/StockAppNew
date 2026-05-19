import pandas as pd
import json


class StrategyBridge:
    def __init__(self, db, tenant_id):
        self.db = db
        self.tenant_id = tenant_id

    def load_strategy_to_weights(self, strategy_row):
        """
        Convert DiscoveredStrategy → weights DataFrame
        """

        if strategy_row is None:
            return pd.DataFrame()

        holdings = strategy_row.holdings

        if not holdings:
            return pd.DataFrame()

        # -----------------------------------------
        # Parse holdings
        # -----------------------------------------
        symbols = []

        try:
            # If JSON list
            parsed = json.loads(holdings)

            if isinstance(parsed, list):
                symbols = parsed

        except Exception:
            # fallback: comma-separated string
            symbols = [s.strip() for s in holdings.split(",")]

        symbols = [str(s).upper() for s in symbols if s]

        if not symbols:
            return pd.DataFrame()

        # -----------------------------------------
        # Equal weight (v1)
        # -----------------------------------------
        w = 1.0 / len(symbols)

        df = pd.DataFrame({
            "Symbol": symbols,
            "Target Weight": [w] * len(symbols)
        })

        return df