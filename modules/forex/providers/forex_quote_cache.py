
"""
modules/forex/providers/forex_quote_cache.py
"""

from __future__ import annotations

import threading
import time
from typing import Any, Optional


class ForexQuoteCache:
    def __init__(self, ttl_seconds:int=60):
        self.ttl_seconds=ttl_seconds
        self._lock=threading.RLock()
        self._cache:dict[str,dict[str,Any]]={}

    def _key(self,pair:str)->str:
        return pair.upper().replace("/","").replace("-","")

    def get(self,pair:str)->Optional[dict]:
        key=self._key(pair)
        with self._lock:
            item=self._cache.get(key)
            if not item:
                return None
            if time.time()-item["ts"]>self.ttl_seconds:
                self._cache.pop(key,None)
                return None
            return dict(item["value"])

    def put(self,pair:str,value:dict)->dict:
        with self._lock:
            self._cache[self._key(pair)]={"ts":time.time(),"value":dict(value)}
        return value

    def invalidate(self,pair:str)->None:
        with self._lock:
            self._cache.pop(self._key(pair),None)

    def clear(self)->None:
        with self._lock:
            self._cache.clear()

    def stats(self)->dict:
        with self._lock:
            return {
                "entries":len(self._cache),
                "ttl_seconds":self.ttl_seconds
            }


_CACHE:ForexQuoteCache|None=None

def get_forex_quote_cache()->ForexQuoteCache:
    global _CACHE
    if _CACHE is None:
        _CACHE=ForexQuoteCache()
    return _CACHE
