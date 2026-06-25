"""
modules/forex/providers/common.py
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from functools import lru_cache

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

LOGGER=logging.getLogger("forex.providers")

DEFAULT_TIMEOUT=20

USER_AGENT="StockApp Forex/1.0"

def utc_now():
    return datetime.now(timezone.utc)

def utc_iso():
    return utc_now().replace(microsecond=0).isoformat()

def normalize_pair(pair:str):
    p=str(pair).upper().replace("-","/").replace("_","/").replace(" ","")
    if "/" in p:
        b,q=p.split("/",1)
    else:
        b,q=p[:3],p[3:6]
    return b[:3],q[:3],f"{b[:3]}/{q[:3]}"

def provider_headers(extra=None):
    h={"User-Agent":USER_AGENT,"Accept":"application/json"}
    if extra:
        h.update(extra)
    return h

@lru_cache(maxsize=1)
def session():
    s=requests.Session()
    retry=Retry(total=3,backoff_factor=0.5,status_forcelist=[429,500,502,503,504],allowed_methods=["GET"])
    adapter=HTTPAdapter(max_retries=retry,pool_connections=20,pool_maxsize=20)
    s.mount("https://",adapter)
    s.mount("http://",adapter)
    s.headers.update(provider_headers())
    return s

def request_json(url:str,*,params=None,headers=None,timeout=DEFAULT_TIMEOUT):
    r=session().get(url,params=params,headers=headers or {},timeout=timeout)
    r.raise_for_status()
    return r.json()

def env_key(*names:str)->str:
    for n in names:
        v=os.getenv(n)
        if v:
            return v.strip()
    return ""

def normalize_quote(provider:str,pair:str,rate:float,raw=None):
    base,quote,p=normalize_pair(pair)
    return {
        "pair":p,
        "base":base,
        "quote":quote,
        "mid":float(rate),
        "last":float(rate),
        "provider":provider,
        "source":provider,
        "timestamp":utc_iso(),
        "raw":raw or {},
    }

def provider_error(provider:str,message:str,raw=None):
    return {
        "provider":provider,
        "error":message,
        "timestamp":utc_iso(),
        "raw":raw or {},
    }
