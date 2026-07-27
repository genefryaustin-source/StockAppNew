from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
try:
    from modules.forex._forex_runtime_common import iso, safe_float
    from modules.forex.forex_persistence_engine import ForexPersistenceEngine
except Exception:
    from _forex_runtime_common import iso, safe_float
    from forex_persistence_engine import ForexPersistenceEngine
@dataclass
class ForexAlertRule:
    name: str; metric: str; operator: str; threshold: float; severity: str = 'warning'; enabled: bool = True
class ForexAlertEngine:
    DEFAULT_RULES = [ForexAlertRule('High Queue Backlog','queued_jobs','>',100,'warning'), ForexAlertRule('Runtime Failures','failed_jobs','>',0,'critical'), ForexAlertRule('Low Throughput','throughput_per_minute','<',1,'warning'), ForexAlertRule('Provider Health Weak','provider_health_score','<',70,'warning')]
    def __init__(self, persistence: Optional[ForexPersistenceEngine] = None, rules: Optional[List[ForexAlertRule]] = None): self.persistence = persistence or ForexPersistenceEngine(); self.rules = rules or list(self.DEFAULT_RULES)
    def _compare(self, v: float, op: str, t: float) -> bool: return {'>':v>t,'>=':v>=t,'<':v<t,'<=':v<=t,'==':v==t,'!=':v!=t}.get(op, False)
    def evaluate(self, state: Dict[str, Any]) -> List[Dict[str, Any]]:
        st = dict(state); ph = st.get('provider_health', {})
        if isinstance(ph, dict) and ph: st['provider_health_score'] = sum(safe_float(v) for v in ph.values())/len(ph)
        alerts = []
        for r in self.rules:
            if not r.enabled: continue
            value = safe_float(st.get(r.metric))
            if self._compare(value, r.operator, r.threshold):
                alert = {'name':r.name,'metric':r.metric,'value':value,'operator':r.operator,'threshold':r.threshold,'severity':r.severity,'created_at':iso()}
                self.persistence.log_event('forex_alert', f'{r.name}: {r.metric}={value}', r.severity, alert); alerts.append(alert)
        return alerts
