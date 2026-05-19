import pandas as pd
import numpy as np
import streamlit as st


def _safe_num(series):
    return pd.to_numeric(series, errors="coerce")


def _normalize_weights(df: pd.DataFrame, weight_col: str = "weight") -> pd.DataFrame:
    df = df.copy()
    total = df[weight_col].sum()
    if total <= 0:
        df[weight_col] = 1.0 / len(df)
    else:
        df[weight_col] = df[weight_col] / total
    return df


def _apply_max_position(df: pd.DataFrame, max_position: float, weight_col: str = "weight") -> pd.DataFrame:
    df = df.copy()
    df[weight_col] = df[weight_col].clip(upper=max_position)
    return _normalize_weights(df, weight_col)


def _apply_sector_caps(
    df: pd.DataFrame,
    sector_cap: float,
    weight_col: str = "weight",
    sector_col: str = "sector",
) -> pd.DataFrame:
    df = df.copy()

    if sector_col not in df.columns:
        return _normalize_weights(df, weight_col)

    df[sector_col] = df[sector_col].fillna("Unknown")

    # Iterative cap + renormalize
    for _ in range(10):
        sector_totals = df.groupby(sector_col)[weight_col].sum()
        over = sector_totals[sector_totals > sector_cap]

        if over.empty:
            break

        for sector_name, sector_weight in over.items():
            mask = df[sector_col] == sector_name
            if sector_weight > 0:
                scale = sector_cap / sector_weight
                df.loc[mask, weight_col] = df.loc[mask, weight_col] * scale

        df = _normalize_weights(df, weight_col)

    return df


def _build_risk_model(
    price_history_map: dict[str, pd.Series],
    annualization: int = 252,
) -> tuple[pd.DataFrame, pd.Series]:
    """
    Returns covariance matrix and annualized vol vector.
    """
    if not price_history_map:
        return pd.DataFrame(), pd.Series(dtype=float)

    prices_df = pd.DataFrame(price_history_map).sort_index()
    prices_df = prices_df.dropna(axis=1, how="all")

    if prices_df.empty:
        return pd.DataFrame(), pd.Series(dtype=float)

    rets = prices_df.pct_change().replace([np.inf, -np.inf], np.nan).dropna(how="all")
    if rets.empty:
        return pd.DataFrame(), pd.Series(dtype=float)

    cov = rets.cov() * annualization
    vol = rets.std() * np.sqrt(annualization)
    return cov, vol


def _apply_inverse_vol_tilt(
    df: pd.DataFrame,
    vol_map: dict[str, float],
    weight_col: str = "weight",
    symbol_col: str = "Ticker",
) -> pd.DataFrame:
    df = df.copy()

    inv_vol = []
    for sym in df[symbol_col]:
        vol = vol_map.get(sym)
        if vol is None or pd.isna(vol) or vol <= 0:
            inv_vol.append(1.0)
        else:
            inv_vol.append(1.0 / vol)

    df["_inv_vol"] = inv_vol
    df[weight_col] = df[weight_col] * df["_inv_vol"]
    df = _normalize_weights(df, weight_col)
    return df.drop(columns=["_inv_vol"], errors="ignore")


def _compute_portfolio_risk_stats(
    df: pd.DataFrame,
    cov: pd.DataFrame,
    weight_col: str = "weight",
    symbol_col: str = "Ticker",
) -> dict:
    if cov is None or cov.empty or df.empty:
        return {
            "portfolio_vol": None,
            "top_risk_contributors": pd.DataFrame(),
        }

    syms = [s for s in df[symbol_col].tolist() if s in cov.index and s in cov.columns]
    if not syms:
        return {
            "portfolio_vol": None,
            "top_risk_contributors": pd.DataFrame(),
        }

    sub = df.set_index(symbol_col).loc[syms]
    w = sub[weight_col].values
    c = cov.loc[syms, syms].values

    port_var = float(w @ c @ w)
    port_vol = float(np.sqrt(max(port_var, 0.0)))

    if port_vol > 0:
        marginal = c @ w / port_vol
        contrib = w * marginal
    else:
        contrib = np.zeros_like(w)

    rc_df = pd.DataFrame({
        "Ticker": syms,
        "weight": w,
        "risk_contribution": contrib,
    }).sort_values("risk_contribution", ascending=False)

    return {
        "portfolio_vol": port_vol,
        "top_risk_contributors": rc_df,
    }


def render_portfolio_construction(rows):
    st.subheader("Portfolio Construction")
    st.session_state.setdefault("constructed_portfolio", None)
    if rows is None or len(rows) == 0:
        st.warning("No rankings available.")
        return

    df = pd.DataFrame(rows)

    if df.empty:
        st.warning("No rankings available.")
        return

    # Support either old or new column names
    if "Ticker" not in df.columns and "symbol" in df.columns:
        df["Ticker"] = df["symbol"]

    if "sector" not in df.columns and "Sector" in df.columns:
        df["sector"] = df["Sector"]

    if "weight" not in df.columns:
        if "alpha_percentile" in df.columns:
            df["weight"] = _safe_num(df["alpha_percentile"])
        elif "Alpha Score" in df.columns:
            df["weight"] = _safe_num(df["Alpha Score"])
        elif "alpha_score" in df.columns:
            df["weight"] = _safe_num(df["alpha_score"])
        else:
            st.warning("No usable weight source found in rankings.")
            return

    df = df.dropna(subset=["Ticker", "weight"]).copy()
    df["weight"] = _safe_num(df["weight"]).fillna(0.0)

    if df.empty or df["weight"].sum() <= 0:
        st.warning("Weights are empty after cleanup.")
        return

    st.markdown("### Constraints")

    c1, c2, c3 = st.columns(3)
    with c1:
        max_position = st.slider("Max position", 0.02, 0.25, 0.10, 0.01)
    with c2:
        sector_cap = st.slider("Max sector cap", 0.10, 0.60, 0.30, 0.05)
    with c3:
        use_risk_tilt = st.checkbox("Apply inverse-vol tilt", value=True)

    max_n = len(df)

    if max_n <= 1:
        st.warning("Not enough securities to construct a portfolio.")
        return

    min_n = min(5, max_n)
    max_slider = min(50, max_n)
    default_n = min(10, max_n)

    if min_n >= max_slider:
        top_n = max_n
    else:
        top_n = st.slider(
            "Portfolio size",
            min_n,
            max_slider,
            default_n,
            1
        )

    # Start from top names by current weight proxy
    df = df.sort_values("weight", ascending=False).head(top_n).copy()
    df = _normalize_weights(df)

    # Optional risk model inputs from session state
    price_cache = st.session_state.get("price_cache", {})
    price_history_map = {}

    for sym in df["Ticker"]:
        series = price_cache.get(sym)
        if isinstance(series, pd.Series) and len(series) >= 20:
            price_history_map[sym] = pd.to_numeric(series, errors="coerce").dropna()

    cov, vol = _build_risk_model(price_history_map)
    vol_map = vol.to_dict() if not vol.empty else {}

    if use_risk_tilt and vol_map:
        df = _apply_inverse_vol_tilt(df, vol_map)

    df = _apply_max_position(df, max_position=max_position)
    df = _apply_sector_caps(df, sector_cap=sector_cap)
    df = _normalize_weights(df)

    stats = _compute_portfolio_risk_stats(df, cov)

    st.markdown("### Proposed Portfolio")

    show_cols = ["Ticker", "sector", "weight"]
    if vol_map:
        df["ann_vol"] = df["Ticker"].map(vol_map)
        show_cols.append("ann_vol")

    st.dataframe(
        df[show_cols].sort_values("weight", ascending=False),
        use_container_width=True,
        hide_index=True,
    )

    c1, c2 = st.columns(2)
    with c1:
        if stats["portfolio_vol"] is not None:
            st.metric("Estimated Portfolio Vol", f"{stats['portfolio_vol']:.2%}")
        else:
            st.metric("Estimated Portfolio Vol", "N/A")
    with c2:
        if "sector" in df.columns:
            largest_sector = df.groupby("sector")["weight"].sum().max()
            st.metric("Largest Sector Weight", f"{largest_sector:.2%}")
        else:
            st.metric("Largest Sector Weight", "N/A")

    if stats["top_risk_contributors"] is not None and not stats["top_risk_contributors"].empty:
        st.markdown("### Top Risk Contributors")
        st.dataframe(
            stats["top_risk_contributors"].head(10),
            use_container_width=True,
            hide_index=True,
        )

    # Save for deployment/rebalance
    # -----------------------------------
    # STANDARDIZE FOR DEPLOYMENT ENGINE
    # -----------------------------------
    portfolio_out = df.copy()

    portfolio_out = portfolio_out.rename(columns={
        "Ticker": "ticker",
        "weight": "target_weight"
    })

    portfolio_out["ticker"] = portfolio_out["ticker"].astype(str).str.upper()
    portfolio_out["target_weight"] = pd.to_numeric(portfolio_out["target_weight"], errors="coerce").fillna(0)

    # normalize again (safety)
    total = portfolio_out["target_weight"].sum()
    if total > 0:
        portfolio_out["target_weight"] = portfolio_out["target_weight"] / total

    # store clean version
    st.session_state["constructed_portfolio"] = portfolio_out

    # debug (temporary)
    st.write("✅ PORTFOLIO READY FOR DEPLOYMENT:", portfolio_out.shape)