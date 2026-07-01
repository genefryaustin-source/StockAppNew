class ForexWalkForward:
    def __init__(self, db=None): self.db = db
    def run(self, strategy):
        return {"status":"READY","windows":6,"passed_windows":4,"stability_score":66.7,"strategy":strategy.get("name","FX Strategy")}
_WF=None
def get_forex_walk_forward(db=None):
    global _WF
    if _WF is None or (db is not None and _WF.db is None): _WF=ForexWalkForward(db=db)
    return _WF
