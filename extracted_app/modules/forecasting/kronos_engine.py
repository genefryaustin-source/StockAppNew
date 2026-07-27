"""
modules/forecasting/kronos_engine.py

Real candlestick-foundation-model forecasting, powered by Kronos
(https://github.com/shiyu-coder/Kronos, MIT licensed). This is the same
model family used by the Kronos live BTC/USDT demo: an autoregressive
decoder-only Transformer that was pre-trained directly on K-line (OHLCV)
token sequences, rather than an LLM asked to eyeball a price chart.

Model classes are vendored in modules/forecasting/kronos_lib (pure Python,
no weights). Pretrained weights are streamed from the Hugging Face Hub on
first use and cached locally by huggingface_hub / torch.

Public API
----------
kronos_dependencies_available() -> bool
kronos_status() -> dict                 # human-readable diagnostics
run_kronos_forecast(price_df, ...) -> dict

`run_kronos_forecast` always returns the same schema. If torch / the
Kronos weights aren't available in this environment, it transparently
falls back to a candlestick-aware statistical Monte Carlo engine (bootstrap
resampling of historical bar-to-bar moves) so the UI never breaks — the
returned dict's "engine" field tells you which one actually ran.
"""

from __future__ import annotations

import math
from datetime import timedelta
from typing import Optional

import numpy as np
import pandas as pd
import streamlit as st


# ─────────────────────────────────────────────────────────────
# Model registry — mirrors the sizes published under NeoQuasar/*
# ─────────────────────────────────────────────────────────────

KRONOS_MODELS = {
    "Kronos-mini (4M, fastest, 2048 ctx)": {
        "model": "NeoQuasar/Kronos-mini",
        "tokenizer": "NeoQuasar/Kronos-Tokenizer-2k",
        "max_context": 2048,
    },
    "Kronos-small (25M, balanced, 512 ctx)": {
        "model": "NeoQuasar/Kronos-small",
        "tokenizer": "NeoQuasar/Kronos-Tokenizer-base",
        "max_context": 512,
    },
    "Kronos-base (102M, most accurate, 512 ctx)": {
        "model": "NeoQuasar/Kronos-base",
        "tokenizer": "NeoQuasar/Kronos-Tokenizer-base",
        "max_context": 512,
    },
}
DEFAULT_MODEL_LABEL = "Kronos-small (25M, balanced, 512 ctx)"


# ─────────────────────────────────────────────────────────────
# Dependency / availability checks
# ─────────────────────────────────────────────────────────────

def kronos_dependencies_available() -> bool:
    try:
        import torch  # noqa: F401
        import einops  # noqa: F401
        import huggingface_hub  # noqa: F401
        import safetensors  # noqa: F401
        from modules.forecasting.kronos_lib import Kronos, KronosTokenizer, KronosPredictor  # noqa: F401
        return True
    except Exception:
        return False


def kronos_status() -> dict:
    """Diagnostics used by the UI to explain why real Kronos may be unavailable."""
    missing = []
    for pkg in ("torch", "einops", "huggingface_hub", "safetensors"):
        try:
            __import__(pkg)
        except Exception:
            missing.append(pkg)

    gpu = False
    try:
        import torch
        gpu = bool(torch.cuda.is_available())
    except Exception:
        pass

    return {
        "available": len(missing) == 0,
        "missing_packages": missing,
        "gpu": gpu,
    }


# ─────────────────────────────────────────────────────────────
# Model loading (cached per Streamlit process)
# ─────────────────────────────────────────────────────────────

@st.cache_resource(show_spinner=False)
def load_kronos_predictor(model_label: str = DEFAULT_MODEL_LABEL):
    """
    Downloads (first call only, then cached on disk by huggingface_hub) and
    loads the Kronos tokenizer + model, and wraps them in a KronosPredictor.
    Cached in-process via st.cache_resource so repeat forecasts are instant.
    """
    from modules.forecasting.kronos_lib import Kronos, KronosTokenizer, KronosPredictor

    spec = KRONOS_MODELS[model_label]
    tokenizer = KronosTokenizer.from_pretrained(spec["tokenizer"])
    model = Kronos.from_pretrained(spec["model"])
    predictor = KronosPredictor(model, tokenizer, max_context=spec["max_context"])
    return predictor


# ─────────────────────────────────────────────────────────────
# Data prep: app's price_df -> Kronos's expected k-line frame
# ─────────────────────────────────────────────────────────────

def _normalize_price_df(price_df: pd.DataFrame) -> pd.DataFrame:
    """Map the app's various column-naming conventions to Kronos's schema:
    lowercase open/high/low/close/volume + a datetime 'timestamps' column."""
    df = price_df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    rename_map = {}
    for want, options in {
        "timestamps": ["Date", "date", "datetime", "Datetime", "timestamp", "index"],
        "open": ["Open", "open"],
        "high": ["High", "high"],
        "low": ["Low", "low"],
        "close": ["Close", "close", "Adj Close", "adj_close"],
        "volume": ["Volume", "volume"],
    }.items():
        for opt in options:
            if opt in df.columns:
                rename_map[opt] = want
                break

    df = df.rename(columns=rename_map)

    if "timestamps" not in df.columns:
        df = df.reset_index().rename(columns={df.index.name or "index": "timestamps"})

    for col in ("open", "high", "low", "close"):
        if col not in df.columns and "close" in df.columns:
            df[col] = df["close"]
    if "volume" not in df.columns:
        df["volume"] = 0.0

    df["timestamps"] = pd.to_datetime(df["timestamps"], utc=True, errors="coerce").dt.tz_localize(None)
    df = df.dropna(subset=["timestamps", "close"]).sort_values("timestamps").reset_index(drop=True)
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["open", "high", "low", "close"]).reset_index(drop=True)
    return df[["timestamps", "open", "high", "low", "close", "volume"]]


def _infer_bar_timedelta(timestamps: pd.Series) -> timedelta:
    diffs = timestamps.diff().dropna()
    if diffs.empty:
        return timedelta(days=1)
    return pd.Timedelta(diffs.median()).to_pytimedelta()


def _future_timestamps(last_ts: pd.Timestamp, step: timedelta, n: int) -> pd.Series:
    return pd.Series([last_ts + step * i for i in range(1, n + 1)])


# ─────────────────────────────────────────────────────────────
# Core forecast (real Kronos)
# ─────────────────────────────────────────────────────────────

def _run_real_kronos(
    kdf: pd.DataFrame,
    lookback: int,
    pred_len: int,
    n_paths: int,
    temperature: float,
    top_p: float,
    model_label: str,
) -> dict:
    predictor = load_kronos_predictor(model_label)

    hist = kdf.tail(lookback).reset_index(drop=True)
    x_df = hist[["open", "high", "low", "close", "volume"]]
    x_timestamp = hist["timestamps"]
    step = _infer_bar_timedelta(hist["timestamps"])
    y_timestamp = _future_timestamps(hist["timestamps"].iloc[-1], step, pred_len)

    paths_close, paths_ohlc = [], []
    for i in range(n_paths):
        pred_df = predictor.predict(
            df=x_df,
            x_timestamp=x_timestamp,
            y_timestamp=y_timestamp,
            pred_len=pred_len,
            T=temperature,
            top_p=top_p,
            sample_count=1,
            verbose=False,
        )
        paths_close.append(pred_df["close"].to_numpy())
        paths_ohlc.append(pred_df[["open", "high", "low", "close"]].to_numpy())

    return _summarize_paths(
        hist=hist,
        y_timestamp=y_timestamp,
        paths_close=np.array(paths_close),
        paths_ohlc=np.array(paths_ohlc),
        engine="kronos",
        engine_label=model_label,
    )


# ─────────────────────────────────────────────────────────────
# Fallback (no torch / weights unavailable): bootstrap Monte Carlo
# ─────────────────────────────────────────────────────────────

def _run_statistical_fallback(
    kdf: pd.DataFrame,
    lookback: int,
    pred_len: int,
    n_paths: int,
) -> dict:
    hist = kdf.tail(lookback).reset_index(drop=True)
    closes = hist["close"].to_numpy()
    rets = np.diff(closes) / closes[:-1]
    rets = rets[np.isfinite(rets)]
    if len(rets) < 5:
        rets = np.array([0.0, 0.0])

    last_close = closes[-1]
    last_bar = hist.iloc[-1]
    avg_range = float((hist["high"] - hist["low"]).tail(30).mean()) if len(hist) else last_close * 0.01
    step = _infer_bar_timedelta(hist["timestamps"])
    y_timestamp = _future_timestamps(hist["timestamps"].iloc[-1], step, pred_len)

    rng = np.random.default_rng()
    paths_close = np.zeros((n_paths, pred_len))
    paths_ohlc = np.zeros((n_paths, pred_len, 4))
    for p in range(n_paths):
        price = last_close
        prev_close = last_close
        for t in range(pred_len):
            r = rng.choice(rets)
            price = max(price * (1 + r), 1e-6)
            o = prev_close
            c = price
            hi = max(o, c) + abs(rng.normal(0, avg_range * 0.25))
            lo = min(o, c) - abs(rng.normal(0, avg_range * 0.25))
            paths_ohlc[p, t] = [o, hi, lo, c]
            paths_close[p, t] = c
            prev_close = c

    return _summarize_paths(
        hist=hist,
        y_timestamp=y_timestamp,
        paths_close=paths_close,
        paths_ohlc=paths_ohlc,
        engine="statistical_fallback",
        engine_label="Bootstrap Monte Carlo (Kronos unavailable in this environment)",
    )


# ─────────────────────────────────────────────────────────────
# Shared summary: turn N sampled paths into forecast + probabilities
# ─────────────────────────────────────────────────────────────

def _summarize_paths(
    hist: pd.DataFrame,
    y_timestamp: pd.Series,
    paths_close: np.ndarray,
    paths_ohlc: np.ndarray,
    engine: str,
    engine_label: str,
) -> dict:
    last_close = float(hist["close"].iloc[-1])
    n_paths, pred_len = paths_close.shape

    mean_close = paths_close.mean(axis=0)
    p10 = np.percentile(paths_close, 10, axis=0)
    p90 = np.percentile(paths_close, 90, axis=0)
    mean_ohlc = paths_ohlc.mean(axis=0)  # (pred_len, 4) open/high/low/close

    forecast_df = pd.DataFrame(
        {
            "timestamps": y_timestamp.values,
            "open": mean_ohlc[:, 0],
            "high": mean_ohlc[:, 1],
            "low": mean_ohlc[:, 2],
            "close": mean_ohlc[:, 3],
            "p10": p10,
            "p90": p90,
        }
    )

    # Direction confidence: fraction of simulated paths that finish higher.
    direction_up_prob = float(np.mean(paths_close[:, -1] > last_close))

    # Realized (historical) volatility, annualization-agnostic (per-bar).
    hist_closes = hist["close"].to_numpy()
    hist_rets = np.diff(hist_closes) / hist_closes[:-1]
    hist_rets = hist_rets[np.isfinite(hist_rets)]
    realized_vol = float(np.std(hist_rets[-min(60, len(hist_rets)):])) if len(hist_rets) > 1 else 0.0

    # Predicted volatility per path, then probability it exceeds realized vol.
    path_vols = []
    for p in range(n_paths):
        c = paths_close[p]
        r = np.diff(np.concatenate([[last_close], c])) / np.concatenate([[last_close], c])[:-1]
        r = r[np.isfinite(r)]
        path_vols.append(float(np.std(r)) if len(r) > 1 else 0.0)
    path_vols = np.array(path_vols)
    predicted_vol = float(np.mean(path_vols))
    vol_elevated_prob = float(np.mean(path_vols > realized_vol)) if realized_vol > 0 else float("nan")

    return {
        "engine": engine,
        "engine_label": engine_label,
        "last_close": last_close,
        "forecast_df": forecast_df,
        "sample_paths_close": paths_close,  # (n_paths, pred_len) for spaghetti plot
        "y_timestamp": y_timestamp,
        "direction_up_prob": direction_up_prob,
        "target_price": float(mean_close[-1]),
        "target_change_pct": float((mean_close[-1] - last_close) / last_close * 100),
        "realized_vol_per_bar": realized_vol,
        "predicted_vol_per_bar": predicted_vol,
        "vol_elevated_prob": vol_elevated_prob,
        "n_paths": n_paths,
        "pred_len": pred_len,
    }


# ─────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────

def run_kronos_forecast(
    price_df: pd.DataFrame,
    lookback: int = 400,
    pred_len: int = 24,
    n_paths: int = 20,
    temperature: float = 1.0,
    top_p: float = 0.9,
    model_label: str = DEFAULT_MODEL_LABEL,
) -> dict:
    """
    Run a Kronos-style probabilistic candlestick forecast.

    Returns a dict (see _summarize_paths) with a mean OHLC forecast, an
    uncertainty band, raw sample paths (for a fan/spaghetti chart), a
    direction-confidence probability, and a volatility forecast+probability
    — mirroring the metrics shown on Kronos's own live demo.
    """
    kdf = _normalize_price_df(price_df)
    if len(kdf) < 30:
        raise ValueError("Not enough historical bars to forecast (need at least 30).")

    lookback = min(lookback, len(kdf), KRONOS_MODELS[model_label]["max_context"])
    n_paths = max(1, min(n_paths, 50))
    pred_len = max(1, min(pred_len, 180))

    if kronos_dependencies_available():
        try:
            return _run_real_kronos(kdf, lookback, pred_len, n_paths, temperature, top_p, model_label)
        except Exception as e:
            # Weights failed to download / OOM / etc. — degrade gracefully.
            result = _run_statistical_fallback(kdf, lookback, pred_len, n_paths)
            result["error"] = f"Kronos model call failed, used fallback: {e}"
            return result

    return _run_statistical_fallback(kdf, lookback, pred_len, n_paths)
