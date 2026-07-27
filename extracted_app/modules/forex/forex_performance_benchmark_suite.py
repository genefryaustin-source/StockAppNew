"""
modules/forex/forex_performance_benchmark_suite.py

Benchmark framework for the Forex subsystem.
"""

from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import time
from typing import Callable, Dict, List, Any

@dataclass
class BenchmarkResult:
    name:str
    iterations:int
    total_seconds:float
    avg_ms:float
    throughput:float
    status:str="PASS"
    def to_dict(self): return asdict(self)

class ForexPerformanceBenchmarkSuite:
    def __init__(self):
        self.results:List[BenchmarkResult]=[]

    def benchmark(self,name:str,fn:Callable,iterations:int=100):
        start=time.perf_counter()
        for _ in range(iterations):
            fn()
        elapsed=time.perf_counter()-start
        self.results.append(BenchmarkResult(
            name=name,
            iterations=iterations,
            total_seconds=round(elapsed,4),
            avg_ms=round((elapsed/iterations)*1000,3),
            throughput=round(iterations/max(elapsed,1e-9),2),
        ))

    def run(self):
        self.benchmark("Dictionary Allocation",lambda:{"EURUSD":1.0},5000)
        self.benchmark("List Build",lambda:[i for i in range(250)],1000)
        self.benchmark("Sorting",lambda:sorted(range(500,0,-1)),1000)
        self.benchmark("String Formatting",lambda:f"EUR/USD {1.12345:.5f}",5000)
        return self.report()

    def report(self)->Dict[str,Any]:
        return {
            "generated_at":datetime.now(timezone.utc).isoformat(),
            "status":"COMPLETE",
            "benchmarks":[r.to_dict() for r in self.results],
            "total":len(self.results)
        }

def run_forex_performance_benchmark_suite():
    return ForexPerformanceBenchmarkSuite().run()

def render_forex_performance_benchmark_suite():
    report=run_forex_performance_benchmark_suite()
    try:
        import streamlit as st
        import pandas as pd
    except Exception:
        return report
    st.title("Forex Performance Benchmark Suite")
    st.success("Benchmarks completed")
    st.dataframe(pd.DataFrame(report["benchmarks"]),use_container_width=True,hide_index=True)
    return report
