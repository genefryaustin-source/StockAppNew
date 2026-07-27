"""
modules/options/options_refresh_framework.py

Shared professional refresh controls for Options pages.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import time
from typing import Callable, Iterable, Optional

import streamlit as st

try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

REFRESH_OPTIONS = ["Manual", "30 Seconds", "1 Minute", "5 Minutes"]
REFRESH_INTERVALS = {"Manual": 0, "30 Seconds": 30, "1 Minute": 60, "5 Minutes": 300}

@dataclass(frozen=True)
class RefreshState:
    namespace: str
    ticker: str
    mode: str
    interval_seconds: int
    force_refresh: bool
    last_refresh_ts: float

    @property
    def ttl_seconds(self) -> int:
        return self.interval_seconds or 300


def _safe_key(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in str(value or "")).strip("_").lower()


def clear_cache_prefixes(prefixes: Iterable[str]) -> None:
    for prefix in list(prefixes or []):
        for key in list(st.session_state.keys()):
            if str(key).startswith(prefix):
                del st.session_state[key]


def clear_exact_keys(keys: Iterable[str]) -> None:
    for key in list(keys or []):
        if key in st.session_state:
            del st.session_state[key]


def render_refresh_controls(
    namespace: str,
    ticker: str = "",
    *,
    cache_prefixes: Optional[Iterable[str]] = None,
    exact_cache_keys: Optional[Iterable[str]] = None,
    default_mode: str = "1 Minute",
    label: str = "Refresh",
    manual_label: str = "↺ Refresh",
    key_suffix: str = "",
    clear_callback: Optional[Callable[[], None]] = None,
) -> RefreshState:
    safe_ns = _safe_key(namespace)
    safe_ticker = _safe_key(ticker)
    safe_suffix = _safe_key(key_suffix)
    base_key = "_".join(x for x in [safe_ns, safe_ticker, safe_suffix] if x)
    mode_key = f"{base_key}_refresh_mode"
    last_key = f"{base_key}_last_refresh_ts"

    if default_mode not in REFRESH_OPTIONS:
        default_mode = "1 Minute"

    col_manual, col_mode = st.columns([1, 2])
    with col_manual:
        manual_refresh = st.button(manual_label, key=f"{base_key}_manual_refresh", use_container_width=True)
    with col_mode:
        mode = st.selectbox(label, REFRESH_OPTIONS, index=REFRESH_OPTIONS.index(default_mode), key=mode_key)

    interval = REFRESH_INTERVALS.get(mode, 0)
    now = time.time()
    last = float(st.session_state.get(last_key, 0.0) or 0.0)

    if st_autorefresh is not None and interval > 0:
        st_autorefresh(interval=interval * 1000, key=f"{base_key}_autorefresh")

    stale = bool(interval > 0 and (now - last) >= interval)
    force_refresh = bool(manual_refresh or stale)

    if force_refresh:
        clear_cache_prefixes(cache_prefixes or [])
        clear_exact_keys(exact_cache_keys or [])
        if clear_callback is not None:
            try:
                clear_callback()
            except Exception:
                pass
        st.session_state[last_key] = now
        last = now
    elif not last:
        st.session_state[last_key] = now
        last = now

    return RefreshState(namespace, ticker, mode, interval, force_refresh, last)


def load_session_cached(cache_key: str, loader: Callable[[], object], *, refresh_state: Optional[RefreshState] = None, ttl_seconds: Optional[int] = None):
    ttl = ttl_seconds or (refresh_state.ttl_seconds if refresh_state else 300)
    payload = st.session_state.get(cache_key)
    now = time.time()
    stale = (
        (refresh_state.force_refresh if refresh_state else False)
        or not isinstance(payload, dict)
        or "data" not in payload
        or "loaded_at" not in payload
        or (now - float(payload.get("loaded_at") or 0)) >= ttl
    )
    if stale:
        st.session_state[cache_key] = {"data": loader(), "loaded_at": now}
    payload = st.session_state[cache_key]
    return payload["data"], float(payload.get("loaded_at") or now)


def cache_status_caption(*, loaded_at: Optional[float] = None, source: str = "unknown", refresh_state: Optional[RefreshState] = None, prefix: str = "Last Updated") -> None:
    stamp = datetime.fromtimestamp(float(loaded_at)).strftime("%H:%M:%S") if loaded_at else "Not loaded"
    mode = refresh_state.mode if refresh_state else "Manual"
    st.caption(f"{prefix}: {stamp} | Source: {str(source or 'unknown').upper()} | Auto Refresh: {mode}")
