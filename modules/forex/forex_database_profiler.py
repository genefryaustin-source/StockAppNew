"""Sprint26 Database Profiler"""
from __future__ import annotations
import json,time,threading,uuid
from collections import deque
from dataclasses import dataclass,asdict,field
from datetime import datetime,timezone
SLOW_QUERY_MS=250.0

def _utc(): return datetime.now(timezone.utc).isoformat()
@dataclass
class QueryRecord:
 id:str=field(default_factory=lambda:str(uuid.uuid4()));timestamp:str=field(default_factory=_utc);module:str="";function:str="";sql:str="";duration_ms:float=0.0;rows:int|None=None;session_id:str|None=None;connection_id:str|None=None;success:bool=True;error:str|None=None;query_type:str="READ"
class ForexDatabaseProfiler:
 def __init__(self,max_history=5000): self._h=deque(maxlen=max_history);self._a={};self._l=threading.RLock();self.s={"queries":0,"reads":0,"writes":0,"slow_queries":0,"failures":0,"retries":0,"rollbacks":0,"commits":0,"sessions_created":0,"sessions_closed":0,"session_invalidations":0,"total_ms":0.0,"max_ms":0.0}
 def start_query(self,sql,module="",function="",session_id=None,connection_id=None): t=str(uuid.uuid4());self._a[t]={"st":time.perf_counter(),"sql":sql,"module":module,"function":function,"sid":session_id,"cid":connection_id};return t
 def end_query(self,t,rows=None,success=True,error=None): a=self._a.pop(t,None); 
  
  
  
  
  
  
  
  
  
  
  
  
  
  
  
  
  
  
  
  
  
  
  
  
  
  
  
  
  
  
  
  
  
  
  
  
  
 if not a:return None;ms=(time.perf_counter()-a["st"])*1000;q="WRITE" if a["sql"].strip().upper().startswith(("INSERT","UPDATE","DELETE","CREATE","ALTER","DROP","MERGE")) else "READ";r=QueryRecord(module=a["module"],function=a["function"],sql=a["sql"],duration_ms=round(ms,3),rows=rows,session_id=a["sid"],connection_id=a["cid"],success=success,error=error,query_type=q);self._h.append(r);self.s["queries"]+=1;self.s["total_ms"]+=r.duration_ms;self.s["max_ms"]=max(self.s["max_ms"],r.duration_ms);self.s["reads" if q=="READ" else "writes"]+=1;self.s["slow_queries"]+=1 if r.duration_ms>=SLOW_QUERY_MS else 0;self.s["failures"]+=0 if success else 1;return r
 def summary(self): avg=self.s["total_ms"]/self.s["queries"] if self.s["queries"] else 0;d=dict(self.s);d.update({"average_ms":round(avg,3),"active_queries":len(self._a),"history_size":len(self._h)});return d
 def recent_queries(self,limit=50): return [asdict(x) for x in list(self._h)[-limit:]]
 def slowest_queries(self,limit=25): return [asdict(x) for x in sorted(self._h,key=lambda z:z.duration_ms,reverse=True)[:limit]]
 def export_json(self): return json.dumps({"summary":self.summary(),"queries":self.recent_queries(1000)},indent=2)
 def reset(self): self.__init__(self._h.maxlen)
_P=None
def get_forex_database_profiler():
 global _P
 if _P is None:_P=ForexDatabaseProfiler()
 return _P
