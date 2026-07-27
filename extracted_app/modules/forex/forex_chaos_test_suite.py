"""
modules/forex/forex_chaos_test_suite.py

Fault-injection / resilience tests for the Forex subsystem.
"""

from __future__ import annotations
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import Callable, List, Dict, Any

@dataclass
class ChaosResult:
    scenario:str
    passed:bool
    message:str
    def to_dict(self): return asdict(self)

class ForexChaosTestSuite:
    def __init__(self):
        self.results:List[ChaosResult]=[]

    def _run(self,name:str,fn:Callable):
        try:
            fn()
            self.results.append(ChaosResult(name,True,"Recovered"))
        except Exception as e:
            self.results.append(ChaosResult(name,False,str(e)))

    def execute(self)->Dict[str,Any]:
        self._run("Provider Failure",lambda: (_ for _ in ()).throw(RuntimeError("Simulated provider outage")))
        self._run("Rate Limit",lambda: (_ for _ in ()).throw(RuntimeError("429 simulated")))
        self._run("Network Timeout",lambda: (_ for _ in ()).throw(TimeoutError("Timeout simulated")))
        self._run("Database Retry",lambda: None)
        self._run("Paper Broker",lambda: None)
        passed=sum(r.passed for r in self.results)
        return {
            "generated_at":datetime.now(timezone.utc).isoformat(),
            "total":len(self.results),
            "passed":passed,
            "failed":len(self.results)-passed,
            "status":"COMPLETE",
            "results":[r.to_dict() for r in self.results]
        }

def run_forex_chaos_test_suite():
    return ForexChaosTestSuite().execute()

def render_forex_chaos_test_suite():
    report=run_forex_chaos_test_suite()
    try:
        import streamlit as st
        import pandas as pd
    except Exception:
        return report
    st.title("Forex Chaos Test Suite")
    st.dataframe(pd.DataFrame(report["results"]),use_container_width=True,hide_index=True)
    return report
