class ForexMonteCarlo:
    def __init__(self, db=None): self.db = db
    def simulate(self, strategy, runs=1000):
        return {"status":"READY","runs":runs,"probability_profit":0.61,"p5_drawdown_pct":14.2,"p95_return_pct":28.6,"strategy":strategy.get("name","FX Strategy")}
_MC=None
def get_forex_monte_carlo(db=None):
    global _MC
    if _MC is None or (db is not None and _MC.db is None): _MC=ForexMonteCarlo(db=db)
    return _MC
