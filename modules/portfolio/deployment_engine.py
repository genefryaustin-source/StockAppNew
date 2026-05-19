import io
from typing import Optional

import pandas as pd
import streamlit as st
from sqlalchemy import text


def _safe_float(x, default=0.0):
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


def _find_symbol_col(df: pd.DataFrame) -> Optional[str]:
    for col in ["Ticker", "ticker", "symbol", "Symbol"]:
        if col in df.columns:
            return col
    return None


def _find_weight_col(df: pd.DataFrame) -> Optional[str]:
    for col in ["weight", "Weight", "target_weight", "Target Weight"]:
        if col in df.columns:
            return col
    return None


def _normalize_constructed_portfolio(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["ticker", "target_weight"])

    out = df.copy()

    sym_col = _find_symbol_col(out)
    wt_col = _find_weight_col(out)

    if sym_col is None or wt_col is None:
        return pd.DataFrame(columns=["ticker", "target_weight"])

    out = out[[sym_col, wt_col]].copy()
    out.columns = ["ticker", "target_weight"]

    out["ticker"] = out["ticker"].astype(str).str.upper().str.strip()
    out["target_weight"] = pd.to_numeric(out["target_weight"], errors="coerce").fillna(0.0)

    out = out[out["ticker"] != ""].copy()

    total = out["target_weight"].sum()
    if total > 0:
        out["target_weight"] = out["target_weight"] / total

    return out.reset_index(drop=True)


def _load_current_positions(db, portfolio_id: int) -> pd.DataFrame:
    rows = db.execute(
        text(
            """
            SELECT
                symbol AS ticker,
                quantity AS shares,
                cost_basis
            FROM portfolio_positions
            WHERE portfolio_id = :portfolio_id
            """
        ),
        {"portfolio_id": portfolio_id},
    ).fetchall()

    if not rows:
        return pd.DataFrame(columns=["ticker", "shares", "cost_basis"])

    df = pd.DataFrame(rows, columns=["ticker", "shares", "cost_basis"])
    df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()
    df["shares"] = pd.to_numeric(df["shares"], errors="coerce").fillna(0.0)
    df["cost_basis"] = pd.to_numeric(df["cost_basis"], errors="coerce").fillna(0.0)

    df = (
        df.groupby("ticker", as_index=False)
        .agg(
            shares=("shares", "sum"),
            cost_basis=("cost_basis", "mean"),
        )
        .reset_index(drop=True)
    )
    return df


def _build_last_price_map(price_cache: dict, tickers: list[str]) -> dict[str, float]:
    out: dict[str, float] = {}

    for t in tickers:
        data = price_cache.get(t)

        if data is None:
            out[t] = 0.0
            continue

        if isinstance(data, pd.Series):
            if not data.empty:
                out[t] = _safe_float(data.iloc[-1], 0.0)
            else:
                out[t] = 0.0

        elif isinstance(data, pd.DataFrame):
            if not data.empty:
                if "Close" in data.columns:
                    out[t] = _safe_float(data["Close"].iloc[-1], 0.0)
                elif "close" in data.columns:
                    out[t] = _safe_float(data["close"].iloc[-1], 0.0)
                else:
                    out[t] = 0.0
            else:
                out[t] = 0.0

        elif isinstance(data, dict):
            if "Close" in data:
                out[t] = _safe_float(data["Close"], 0.0)
            elif "close" in data:
                out[t] = _safe_float(data["close"], 0.0)
            else:
                out[t] = 0.0
        else:
            out[t] = 0.0

    return out


def _build_trade_blotter(
    target_df: pd.DataFrame,
    current_df: pd.DataFrame,
    price_map: dict[str, float],
    portfolio_value: float,
) -> pd.DataFrame:
    if target_df is None:
        target_df = pd.DataFrame(columns=["ticker", "target_weight"])
    if current_df is None:
        current_df = pd.DataFrame(columns=["ticker", "shares", "cost_basis"])

    all_tickers = sorted(set(target_df["ticker"].tolist()) | set(current_df["ticker"].tolist()))

    rows = []
    for ticker in all_tickers:
        target_weight = _safe_float(
            target_df.loc[target_df["ticker"] == ticker, "target_weight"].sum(),
            0.0,
        )

        current_shares = _safe_float(
            current_df.loc[current_df["ticker"] == ticker, "shares"].sum(),
            0.0,
        )

        px = _safe_float(price_map.get(ticker), 0.0)
        current_value = current_shares * px if px > 0 else 0.0
        target_value = portfolio_value * target_weight if portfolio_value > 0 else 0.0

        target_shares = (target_value / px) if px > 0 else 0.0
        delta_shares = target_shares - current_shares
        delta_value = target_value - current_value

        if abs(delta_shares) < 1e-9:
            action = "HOLD"
        elif delta_shares > 0:
            action = "BUY"
        else:
            action = "SELL"

        rows.append(
            {
                "ticker": ticker,
                "last_price": px,
                "current_shares": current_shares,
                "current_value": current_value,
                "target_weight": target_weight,
                "target_value": target_value,
                "target_shares": target_shares,
                "delta_shares": delta_shares,
                "delta_value": delta_value,
                "action": action,
            }
        )

    blotter = pd.DataFrame(rows)

    if blotter.empty:
        return blotter

    blotter["abs_delta_value"] = blotter["delta_value"].abs()
    blotter = blotter.sort_values(["abs_delta_value", "ticker"], ascending=[False, True]).reset_index(drop=True)
    blotter.drop(columns=["abs_delta_value"], inplace=True, errors="ignore")
    return blotter

    # -----------------------------------
    # EXECUTION INTELLIGENCE
    # -----------------------------------
    blotter = _apply_execution_intelligence(
        blotter,
        min_trade_value=100,
        max_turnover=0.30,
        slippage_bps=10
    )


def _to_csv_download(df: pd.DataFrame) -> bytes:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")


def render_portfolio_deployment(db, user):
    st.subheader("Portfolio Deployment")

    constructed = st.session_state.get("constructed_portfolio")
    if constructed is None or len(constructed) == 0:
        st.warning("Run Portfolio Construction first.")
        return

    target_df = _normalize_constructed_portfolio(pd.DataFrame(constructed))
    if target_df.empty:
        st.warning("Constructed portfolio is missing ticker/weight columns.")
        return

    portfolios = db.execute(
        text(
            """
            SELECT id, name
            FROM portfolios
            ORDER BY name
            """
        )
    ).fetchall()

    if not portfolios:
        st.warning("No portfolios found.")
        return

    portfolio_map = {p[1]: p[0] for p in portfolios}
    selected_name = st.selectbox("Deploy into Portfolio", list(portfolio_map.keys()), key="deploy_portfolio_select")
    portfolio_id = portfolio_map[selected_name]

    c1, c2 = st.columns(2)
    with c1:
        capital_mode = st.selectbox(
            "Target Capital Mode",
            ["Use current market value", "Manual capital amount"],
            key="deploy_capital_mode",
        )
    with c2:
        execution_buffer_bps = st.number_input(
            "Execution Buffer (bps)",
            min_value=0,
            max_value=500,
            value=0,
            step=5,
            key="deploy_buffer_bps",
        )

    current_df = _load_current_positions(db, portfolio_id)

    price_cache = st.session_state.get("price_cache", {})
    tickers = sorted(set(target_df["ticker"].tolist()) | set(current_df["ticker"].tolist()))
    price_map = _build_last_price_map(price_cache, tickers)

    current_market_value = 0.0
    if not current_df.empty:
        tmp = current_df.copy()
        tmp["last_price"] = tmp["ticker"].map(price_map).fillna(0.0)
        tmp["market_value"] = tmp["shares"] * tmp["last_price"]
        current_market_value = float(tmp["market_value"].sum())

    if capital_mode == "Manual capital amount":
        portfolio_value = st.number_input(
            "Target Capital ($)",
            min_value=0.0,
            value=float(max(current_market_value, 100000.0)),
            step=1000.0,
            key="deploy_manual_capital",
        )
    else:
        portfolio_value = current_market_value

    if portfolio_value <= 0:
        st.warning("Current or target portfolio value is zero. Provide a positive target capital.")
        return

    blotter = _build_trade_blotter(
        target_df=target_df,
        current_df=current_df,
        price_map=price_map,
        portfolio_value=portfolio_value,
    )

    if blotter.empty:
        st.warning("No trades to generate.")
        return

    if execution_buffer_bps > 0:
        buffer_mult = execution_buffer_bps / 10000.0
        blotter["buffered_price"] = blotter["last_price"] * (
            1 + buffer_mult * blotter["action"].map({"BUY": 1, "SELL": -1, "HOLD": 0}).fillna(0)
        )
    else:
        blotter["buffered_price"] = blotter["last_price"]

    st.markdown("### Deployment Summary")

    s1, s2, s3 = st.columns(3)
    with s1:
        st.metric("Target Capital", f"${portfolio_value:,.2f}")
    with s2:
        buy_value = float(blotter.loc[blotter["action"] == "BUY", "delta_value"].clip(lower=0).sum())
        st.metric("Gross Buys", f"${buy_value:,.2f}")
    with s3:
        sell_value = float((-blotter.loc[blotter["action"] == "SELL", "delta_value"].clip(upper=0)).sum())
        st.metric("Gross Sells", f"${sell_value:,.2f}")

    st.markdown("### Trade Blotter")

    display_cols = [
        "ticker",
        "action",
        "last_price",
        "execution_price",
        "current_shares",
        "target_shares",
        "exec_shares",
        "exec_value",
        "priority"
    ]

    st.dataframe(
        blotter[display_cols],
        use_container_width=True,
        hide_index=True,
    )

    csv_bytes = _to_csv_download(blotter[display_cols])
    st.download_button(
        "Download Trade Blotter CSV",
        data=csv_bytes,
        file_name="trade_blotter.csv",
        mime="text/csv",
        key="deploy_download_csv",
    )

    st.session_state["deployment_blotter"] = blotter.copy()

    st.markdown("### Persist Rebalance Plan")

    plan_name = st.text_input("Plan Name", value=f"Rebalance - {selected_name}", key="deploy_plan_name")

    if st.button("Save Deployment Plan", key="deploy_save_plan"):
        db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS portfolio_rebalance_plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    portfolio_id INTEGER,
                    tenant_id TEXT,
                    plan_name TEXT,
                    created_at TEXT
                )
                """
            )
        )

        db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS portfolio_rebalance_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plan_id INTEGER,
                    ticker TEXT,
                    action TEXT,
                    last_price REAL,
                    buffered_price REAL,
                    current_shares REAL,
                    target_shares REAL,
                    delta_shares REAL,
                    current_value REAL,
                    target_value REAL,
                    delta_value REAL,
                    target_weight REAL
                )
                """
            )
        )

        db.execute(
            text(
                """
                INSERT INTO portfolio_rebalance_plans
                (portfolio_id, tenant_id, plan_name, created_at)
                VALUES (:portfolio_id, :tenant_id, :plan_name, :created_at)
                """
            ),
            {
                "portfolio_id": portfolio_id,
                "tenant_id": user.get("tenant_id", "default_tenant"),
                "plan_name": plan_name,
                "created_at": datetime.now(UTC).isoformat(),
            },
        )

        plan_id = db.execute(text("SELECT last_insert_rowid()")).scalar()

        for _, row in blotter.iterrows():
            db.execute(
                text(
                    """
                    INSERT INTO portfolio_rebalance_trades
                    (
                        plan_id, ticker, action, last_price, buffered_price,
                        current_shares, target_shares, delta_shares,
                        current_value, target_value, delta_value, target_weight
                    )
                    VALUES
                    (
                        :plan_id, :ticker, :action, :last_price, :buffered_price,
                        :current_shares, :target_shares, :delta_shares,
                        :current_value, :target_value, :delta_value, :target_weight
                    )
                    """
                ),
                {
                    "plan_id": plan_id,
                    "ticker": row["ticker"],
                    "action": row["action"],
                    "last_price": _safe_float(row["last_price"]),
                    "buffered_price": _safe_float(row["buffered_price"]),
                    "current_shares": _safe_float(row["current_shares"]),
                    "target_shares": _safe_float(row["target_shares"]),
                    "delta_shares": _safe_float(row["delta_shares"]),
                    "current_value": _safe_float(row["current_value"]),
                    "target_value": _safe_float(row["target_value"]),
                    "delta_value": _safe_float(row["delta_value"]),
                    "target_weight": _safe_float(row["target_weight"]),
                },
            )

        db.commit()
        st.success("Deployment plan saved.")

def _apply_execution_intelligence(
    blotter: pd.DataFrame,
    min_trade_value: float = 100.0,
    max_turnover: float = 0.30,
    slippage_bps: float = 10.0
) -> pd.DataFrame:

    if blotter is None or blotter.empty:
        return blotter

    df = blotter.copy()

    # -----------------------------------
    # 1. LOT SIZING (WHOLE SHARES)
    # -----------------------------------
    df["exec_shares"] = df["delta_shares"].round(0)

    # -----------------------------------
    # 2. RECOMPUTE VALUE FROM LOTS
    # -----------------------------------
    df["exec_value"] = df["exec_shares"] * df["last_price"]

    # -----------------------------------
    # 3. MIN TRADE FILTER
    # -----------------------------------
    df = df[df["exec_value"].abs() >= min_trade_value].copy()

    if df.empty:
        return df

    # -----------------------------------
    # 4. TURNOVER CONTROL
    # -----------------------------------
    total_turnover = df["exec_value"].abs().sum()

    if total_turnover > 0:
        turnover_limit = total_turnover * max_turnover

        df = df.sort_values("exec_value", key=lambda x: x.abs(), ascending=False)

        cumulative = df["exec_value"].abs().cumsum()
        df = df[cumulative <= turnover_limit]

    # -----------------------------------
    # 5. SLIPPAGE MODEL
    # -----------------------------------
    slippage = slippage_bps / 10000.0

    df["execution_price"] = df["last_price"]

    df.loc[df["action"] == "BUY", "execution_price"] *= (1 + slippage)
    df.loc[df["action"] == "SELL", "execution_price"] *= (1 - slippage)

    # -----------------------------------
    # 6. PRIORITY SCORE (EXECUTION ORDER)
    # -----------------------------------
    df["priority"] = df["exec_value"].abs()

    df = df.sort_values("priority", ascending=False)

    return df.reset_index(drop=True)