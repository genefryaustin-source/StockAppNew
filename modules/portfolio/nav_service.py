import pandas as pd
from sqlalchemy import text


from collections import deque
import uuid
class NavService:

    def __init__(self, db_session, market_data_service):
        self.db = db_session
        self.market_data = market_data_service

    # =====================================================
    # 🔧 INTERNAL HELPERS
    # =====================================================
    def _safe_get_price_history(self, symbol, period="6mo"):
        try:
            from modules.market_data.service import get_price_history

            df = get_price_history(self.db, symbol, period=period)

            if df is None or df.empty:
                return pd.DataFrame()

            if "Date" not in df.columns or "Close" not in df.columns:
                return pd.DataFrame()

            df = df.copy()
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

            # normalize timezone safely
            if df["Date"].dt.tz is not None:
                df["Date"] = df["Date"].dt.tz_convert(None)

            df["Date"] = df["Date"].dt.normalize()
            df = df.dropna(subset=["Date", "Close"])

            return df.sort_values("Date")

        except Exception as e:
            print(f"⚠️ Price history error for {symbol}: {e}")
            return pd.DataFrame()

    def _get_sector(self, symbol: str) -> str:
        try:
            if hasattr(self, "market_data") and self.market_data:
                meta = self.market_data.get_security_metadata(symbol)

                if meta:
                    return (
                            meta.get("sector")
                            or meta.get("Sector")
                            or meta.get("gics_sector")
                            or "Unknown"
                    )

        except Exception as e:
            print(f"⚠️ sector lookup failed for {symbol}: {e}")

        return "Unknown"



    def _get_positions(self, portfolio_id):
        rows = self.db.execute(text("""
            SELECT symbol, qty
            FROM portfolio_positions
            WHERE portfolio_id = :pid
        """), {"pid": portfolio_id}).fetchall()

        return [{"symbol": r[0], "qty": r[1]} for r in rows]

    def _get_period_days(self, period):
        return {
            "1mo": 30,
            "3mo": 90,
            "6mo": 180,
            "1y": 365
        }.get(period, 180)

    # =====================================================
    # 📈 BUILD NAV SERIES
    # =====================================================
    def build_nav_series(self, portfolio_id, period="6mo"):

        positions = self._get_positions(portfolio_id)
        if not positions:
            return pd.DataFrame()

        price_data = {}
        for pos in positions:
            hist = self._safe_get_price_history(pos["symbol"], period=period)
            if not hist.empty:
                price_data[pos["symbol"]] = hist.set_index("Date")["Close"]

        if not price_data:
            return pd.DataFrame()

        price_matrix = pd.concat(price_data, axis=1)

        # CLEAN
        price_matrix = price_matrix.sort_index().ffill().dropna(how="all")

        # NORMALIZE INDEX
        price_matrix.index = pd.to_datetime(price_matrix.index).tz_localize(None)
        price_matrix.index = price_matrix.index.normalize()

        # TIME WINDOW
        end_date = pd.Timestamp.utcnow().tz_localize(None).normalize()
        start_date = (end_date - pd.Timedelta(days=self._get_period_days(period))).normalize()

        price_matrix = price_matrix[
            (price_matrix.index >= start_date) &
            (price_matrix.index <= end_date)
        ]

        if price_matrix.empty:
            return pd.DataFrame()

        # BUILD NAV
        nav = None
        for pos in positions:
            sym = pos["symbol"]
            qty = pos["qty"]

            if sym in price_matrix.columns:
                series = price_matrix[sym] * qty
                nav = series if nav is None else nav.add(series, fill_value=0)

        if nav is None:
            return pd.DataFrame()

        nav_df = nav.reset_index()
        nav_df.columns = ["Date", "NAV"]
        nav_df["Date"] = pd.to_datetime(nav_df["Date"]).dt.normalize()

        return nav_df

    # =====================================================
    # 📊 BUILD BENCHMARK SERIES
    # =====================================================
    def build_benchmark_series(self, symbol="SPY", period="6mo"):

        hist = self._safe_get_price_history(symbol, period=period)
        if hist.empty:
            return pd.DataFrame()

        hist = hist.copy()
        hist["Date"] = pd.to_datetime(hist["Date"], errors="coerce")

        if hist["Date"].dt.tz is not None:
            hist["Date"] = hist["Date"].dt.tz_convert(None)

        hist["Date"] = hist["Date"].dt.normalize()

        # TIME WINDOW
        end_date = pd.Timestamp.utcnow().tz_localize(None).normalize()
        start_date = (end_date - pd.Timedelta(days=self._get_period_days(period))).normalize()

        hist = hist[
            (hist["Date"] >= start_date) &
            (hist["Date"] <= end_date)
        ]

        if hist.empty:
            return pd.DataFrame()

        first_close = float(hist["Close"].iloc[0])
        if first_close <= 0:
            return pd.DataFrame()

        hist["Benchmark"] = hist["Close"] / first_close

        return hist[["Date", "Benchmark"]]

    # =====================================================
    # ⚖️ NAV VS BENCHMARK
    # =====================================================
    def compute_nav_vs_benchmark(self, portfolio_id, benchmark="SPY", period="6mo"):

        nav_df = self.build_nav_series(portfolio_id, period=period)
        bench_df = self.build_benchmark_series(benchmark, period=period)

        if nav_df.empty or bench_df.empty:
            return None

        # ENSURE CLEAN DATES
        nav_df["Date"] = pd.to_datetime(nav_df["Date"]).dt.normalize()
        bench_df["Date"] = pd.to_datetime(bench_df["Date"]).dt.normalize()

        # MERGE
        df = pd.merge(
            nav_df[["Date", "NAV"]],
            bench_df[["Date", "Benchmark"]],
            on="Date",
            how="inner"
        )

        df = df.sort_values("Date").drop_duplicates(subset=["Date"])

        if len(df) < 5:
            return None

        # RETURNS
        df["rp"] = df["NAV"].pct_change().clip(-0.95, 0.95).fillna(0)
        df["rb"] = df["Benchmark"].pct_change().clip(-0.95, 0.95).fillna(0)

        # CUMULATIVE RETURNS
        df["cum_p"] = (1 + df["rp"]).cumprod() - 1
        df["cum_b"] = (1 + df["rb"]).cumprod() - 1

        return {
            "nav_df": nav_df,
            "benchmark_df": bench_df,
            "comparison_df": df
        }

    # =====================================================
    # 📊 NAV HISTORY (COMPATIBILITY LAYER)
    # =====================================================
    def get_nav_history(self, portfolio_id, period="6mo"):
        """
        Compatibility wrapper used by UI / reporting.
        Returns NAV time series in expected format.
        """

        nav_df = self.build_nav_series(portfolio_id, period=period)

        if nav_df is None or nav_df.empty:
            return pd.DataFrame()

        nav_df = nav_df.copy()
        nav_df["Date"] = pd.to_datetime(nav_df["Date"]).dt.normalize()

        return nav_df.sort_values("Date")

    def compute_real_pnl_attribution(self, portfolio_id: str):
        """
        Returns per-position realized / unrealized / total pnl attribution.
        Uses current positions and trade history.
        """

        import pandas as pd
        from sqlalchemy import text

        # ---------------------------------
        # POSITIONS
        # ---------------------------------
        positions = self.db.execute(text("""
            SELECT
                symbol,
                qty,
                avg_cost,
                market_price,
                market_value,
                unrealized_pnl
            FROM portfolio_positions
            WHERE portfolio_id = :pid
        """), {"pid": portfolio_id}).fetchall()

        if not positions:
            return {
                "summary": {
                    "realized_pnl": 0.0,
                    "unrealized_pnl": 0.0,
                    "total_pnl": 0.0,
                },
                "detail": pd.DataFrame()
            }

        pos_df = pd.DataFrame(positions, columns=[
            "Symbol",
            "Qty",
            "Avg Cost",
            "Market Price",
            "Market Value",
            "Unrealized PnL"
        ])

        for col in ["Qty", "Avg Cost", "Market Price", "Market Value", "Unrealized PnL"]:
            pos_df[col] = pd.to_numeric(pos_df[col], errors="coerce").fillna(0.0)

        pos_df["Symbol"] = pos_df["Symbol"].astype(str).str.upper().str.strip()

        # ---------------------------------
        # TRADES
        # ---------------------------------
        trades = self.db.execute(text("""
            SELECT
                symbol,
                side,
                filled_qty,
                avg_fill_price
            FROM trade_orders
            WHERE portfolio_id = :pid
              AND status IN ('filled', 'partially_filled', 'executed')
        """), {"pid": portfolio_id}).fetchall()

        trades_df = pd.DataFrame(trades, columns=[
            "Symbol",
            "Side",
            "Filled Qty",
            "Avg Fill Price"
        ]) if trades else pd.DataFrame(columns=[
            "Symbol",
            "Side",
            "Filled Qty",
            "Avg Fill Price"
        ])

        if not trades_df.empty:
            trades_df["Symbol"] = trades_df["Symbol"].astype(str).str.upper().str.strip()
            trades_df["Side"] = trades_df["Side"].astype(str).str.lower().str.strip()
            trades_df["Filled Qty"] = pd.to_numeric(trades_df["Filled Qty"], errors="coerce").fillna(0.0)
            trades_df["Avg Fill Price"] = pd.to_numeric(trades_df["Avg Fill Price"], errors="coerce").fillna(0.0)

        # ---------------------------------
        # REALIZED PNL (APPROX USING CURRENT AVG COST BASIS)
        # ---------------------------------
        realized_rows = []

        for symbol, grp in trades_df.groupby("Symbol"):

            sells = grp[grp["Side"] == "sell"].copy()

            if sells.empty:
                realized_rows.append({
                    "Symbol": symbol,
                    "Realized PnL": 0.0
                })
                continue

            avg_cost_row = pos_df[pos_df["Symbol"] == symbol]
            avg_cost = float(avg_cost_row["Avg Cost"].iloc[0]) if not avg_cost_row.empty else 0.0

            sells["Realized Trade PnL"] = (
                    (sells["Avg Fill Price"] - avg_cost) * sells["Filled Qty"]
            )

            realized_rows.append({
                "Symbol": symbol,
                "Realized PnL": float(sells["Realized Trade PnL"].sum())
            })

        realized_df = pd.DataFrame(realized_rows) if realized_rows else pd.DataFrame(columns=[
            "Symbol", "Realized PnL"
        ])

        # ---------------------------------
        # MERGE
        # ---------------------------------
        df = pos_df.merge(realized_df, on="Symbol", how="left")
        df["Realized PnL"] = pd.to_numeric(df["Realized PnL"], errors="coerce").fillna(0.0)
        df["Unrealized PnL"] = pd.to_numeric(df["Unrealized PnL"], errors="coerce").fillna(0.0)

        df["Total PnL"] = df["Realized PnL"] + df["Unrealized PnL"]

        portfolio_total_pnl = float(df["Total PnL"].sum())
        portfolio_market_value = float(df["Market Value"].sum())

        if abs(portfolio_total_pnl) > 1e-9:
            df["PnL Contribution"] = df["Total PnL"] / portfolio_total_pnl
        else:
            df["PnL Contribution"] = 0.0

        if abs(portfolio_market_value) > 1e-9:
            df["Weight"] = df["Market Value"] / portfolio_market_value
        else:
            df["Weight"] = 0.0

        df = df[[
            "Symbol",
            "Qty",
            "Avg Cost",
            "Market Price",
            "Market Value",
            "Weight",
            "Realized PnL",
            "Unrealized PnL",
            "Total PnL",
            "PnL Contribution",
        ]].sort_values("Total PnL", ascending=True).reset_index(drop=True)

        summary = {
            "realized_pnl": float(df["Realized PnL"].sum()),
            "unrealized_pnl": float(df["Unrealized PnL"].sum()),
            "total_pnl": float(df["Total PnL"].sum()),
        }

        return {
            "summary": summary,
            "detail": df
        }

    # ================================
    # 💵 LOT-LEVEL PNL ATTRIBUTION ENGINE
    # =========================================
    def compute_lot_level_pnl_attribution(
            self,
            portfolio_id: str,
            method: str = "FIFO",
            specific_lot_map: dict | None = None,
    ):

        try:
            method = str(method).upper().strip()
            if method not in {"FIFO", "LIFO", "SPECIFIC"}:
                raise ValueError(f"Unsupported lot method: {method}")

            # ---------------------------------
            # LOAD TRADES
            # ---------------------------------
            trades = self.db.execute(text("""
                SELECT
                    id,
                    symbol,
                    side,
                    COALESCE(filled_qty, qty, 0),
                    COALESCE(avg_fill_price, limit_price, 0),
                    COALESCE(actual_commission, 0),
                    COALESCE(actual_slippage, 0),
                    COALESCE(filled_at, submitted_at, created_at)
                FROM trade_orders
                WHERE portfolio_id = :pid
                  AND LOWER(COALESCE(status, '')) IN ('filled','partially_filled','executed')
                ORDER BY COALESCE(filled_at, submitted_at, created_at), id
            """), {"pid": portfolio_id}).fetchall()

            cols = ["TradeID", "Symbol", "Side", "Qty", "Price", "Commission", "Slippage", "Time"]
            df = pd.DataFrame(trades, columns=cols)

            if df.empty:
                return self._empty_lot_response(method)

            # ---------------------------------
            # CLEAN DATA
            # ---------------------------------
            df["Symbol"] = df["Symbol"].astype(str).str.upper().str.strip()
            df["Side"] = df["Side"].astype(str).str.lower().str.strip()
            df["Qty"] = pd.to_numeric(df["Qty"], errors="coerce").fillna(0.0)
            df["Price"] = pd.to_numeric(df["Price"], errors="coerce").fillna(0.0)
            df["Commission"] = pd.to_numeric(df["Commission"], errors="coerce").fillna(0.0)
            df["Slippage"] = pd.to_numeric(df["Slippage"], errors="coerce").fillna(0.0)
            df["Time"] = pd.to_datetime(df["Time"], errors="coerce")

            df = df[
                df["Symbol"].ne("") &
                df["Qty"].gt(0) &
                df["Price"].gt(0)
                ].copy()

            # ---------------------------------
            # LOAD MARKET PRICES
            # ---------------------------------
            pos = self.db.execute(text("""
                SELECT symbol, market_price
                FROM portfolio_positions
                WHERE portfolio_id = :pid
            """), {"pid": portfolio_id}).fetchall()

            price_map = {str(r[0]).upper(): float(r[1] or 0.0) for r in pos}

            # ---------------------------------
            # LOT ENGINE
            # ---------------------------------
            lots_by_symbol = {}
            realized_rows = []

            def make_lot(row):
                qty = float(row["Qty"])
                price = float(row["Price"])
                commission = float(row["Commission"])
                slippage = float(row["Slippage"])

                cost_adj = (commission + slippage) / qty if qty > 0 else 0.0
                effective_cost = price + cost_adj

                return {
                    "lot_id": str(uuid.uuid4()),
                    "symbol": row["Symbol"],
                    "qty": qty,
                    "remaining_qty": qty,
                    "cost": effective_cost,
                    "buy_trade_id": row["TradeID"],
                    "buy_time": row["Time"],
                    "matched_sells": [],
                    "time": row["Time"]
                }

            for symbol, grp in df.groupby("Symbol", sort=False):
                grp = grp.sort_values("Time")
                lots = deque()
                lots_by_symbol[symbol] = lots

                for _, row in grp.iterrows():
                    side = row["Side"]

                    if side == "buy":
                        lots.append(make_lot(row))
                        continue

                    # SELL
                    sell_qty = float(row["Qty"])
                    sell_price = float(row["Price"])

                    total_costs = row["Commission"] + row["Slippage"]
                    sell_eff = sell_price - (total_costs / sell_qty if sell_qty > 0 else 0)

                    qty_to_match = sell_qty

                    while qty_to_match > 0 and len(lots) > 0:
                        lot = lots[0] if method != "LIFO" else lots[-1]

                        remaining_qty = float(lot["remaining_qty"])
                        if remaining_qty <= 0:
                            lots.popleft() if method != "LIFO" else lots.pop()
                            continue

                        matched_qty = min(qty_to_match, remaining_qty)
                        pnl = (sell_eff - lot["cost"]) * matched_qty

                        realized_rows.append({
                            "Symbol": symbol,
                            "Lot ID": lot["lot_id"],
                            "Buy Trade ID": lot["buy_trade_id"],
                            "Buy Time": lot["buy_time"],
                            "Sell Trade ID": row["TradeID"],
                            "Sell Time": row["Time"],
                            "Qty": matched_qty,
                            "Sell Price": sell_price,
                            "Cost Basis": lot["cost"],
                            "PnL": pnl
                        })

                        lot["remaining_qty"] -= matched_qty
                        qty_to_match -= matched_qty

                        if lot["remaining_qty"] <= 0:
                            lots.popleft() if method != "LIFO" else lots.pop()

            # ---------------------------------
            # REALIZED DF
            # ---------------------------------
            realized_df = pd.DataFrame(realized_rows)

            if not realized_df.empty:
                total_realized = realized_df["PnL"].sum()
                realized_df["Realized Contribution %"] = (
                    realized_df["PnL"] / total_realized if abs(total_realized) > 1e-12 else 0
                )

            # ---------------------------------
            # OPEN LOTS
            # ---------------------------------
            open_rows = []

            for sym, lots in lots_by_symbol.items():
                market_price = float(price_map.get(sym, 0.0))

                for lot in lots:
                    remaining_qty = float(lot["remaining_qty"])
                    if remaining_qty <= 0:
                        continue

                    cost = float(lot["cost"])
                    pnl = (market_price - cost) * remaining_qty

                    open_rows.append({
                        "Symbol": sym,
                        "Lot ID": lot["lot_id"],
                        "Buy Trade ID": lot["buy_trade_id"],
                        "Open Qty": remaining_qty,
                        "Effective Cost": cost,
                        "Market Price": market_price,
                        "PnL": pnl,
                        "Time": lot["buy_time"]
                    })

            open_df = pd.DataFrame(open_rows)

            if not open_df.empty:
                total_unrealized = open_df["PnL"].sum()
                open_df["Unrealized Contribution %"] = (
                    open_df["PnL"] / total_unrealized if abs(total_unrealized) > 1e-12 else 0
                )

            # ---------------------------------
            # PER-LOT DETAIL TABLE (CLEAN SCHEMA)
            # ---------------------------------
            realized_detail = pd.DataFrame()
            unrealized_detail = pd.DataFrame()

            # -------------------------------
            # REALIZED LOT ROWS
            # -------------------------------
            if not realized_df.empty:
                realized_detail = realized_df.copy()

                # normalize schema for realized rows
                realized_detail["Lot Status"] = "Realized"
                realized_detail["Open Qty"] = 0.0
                realized_detail["Effective Cost"] = realized_detail.get("Cost Basis", 0.0)
                realized_detail["Market Price"] = 0.0
                realized_detail["Unrealized PnL"] = 0.0
                realized_detail["Realized PnL"] = realized_detail["PnL"]
                realized_detail["Total PnL"] = realized_detail["PnL"]

                # fields open lots have but realized rows may not
                if "Buy Trade ID" not in realized_detail.columns:
                    realized_detail["Buy Trade ID"] = None
                if "Time" not in realized_detail.columns:
                    realized_detail["Time"] = realized_detail.get("Buy Time")

            # -------------------------------
            # OPEN LOT ROWS
            # -------------------------------
            if not open_df.empty:
                unrealized_detail = open_df.copy()

                # normalize schema for open rows
                unrealized_detail["Lot Status"] = "Open"
                unrealized_detail["Qty"] = 0.0
                unrealized_detail["Cost Basis"] = unrealized_detail.get("Effective Cost", 0.0)
                unrealized_detail["Sell Trade ID"] = None
                unrealized_detail["Sell Time"] = None
                unrealized_detail["Sell Price"] = 0.0
                unrealized_detail["Buy Time"] = unrealized_detail.get("Time")
                unrealized_detail["Unrealized PnL"] = unrealized_detail["PnL"]
                unrealized_detail["Realized PnL"] = 0.0
                unrealized_detail["Total PnL"] = unrealized_detail["PnL"]

            # -------------------------------
            # COMBINE
            # -------------------------------
            detail = pd.concat([realized_detail, unrealized_detail], ignore_index=True, sort=False)

            # -------------------------------
            # CLEAN TYPES
            # -------------------------------
            if detail.empty:
                detail = pd.DataFrame(columns=[
                    "Symbol",
                    "Lot ID",
                    "Buy Trade ID",
                    "Buy Time",
                    "Sell Trade ID",
                    "Sell Time",
                    "Lot Status",
                    "Qty",
                    "Open Qty",
                    "Cost Basis",
                    "Effective Cost",
                    "Sell Price",
                    "Market Price",
                    "Realized PnL",
                    "Unrealized PnL",
                    "Total PnL",
                    "Realized Contribution %",
                    "Unrealized Contribution %",
                    "Total Contribution %",
                    "Time",
                ])
            else:
                numeric_cols = [
                    "Qty",
                    "Open Qty",
                    "Cost Basis",
                    "Effective Cost",
                    "Sell Price",
                    "Market Price",
                    "Realized PnL",
                    "Unrealized PnL",
                    "Total PnL",
                    "Realized Contribution %",
                    "Unrealized Contribution %",
                ]

                for col in numeric_cols:
                    if col in detail.columns:
                        detail[col] = pd.to_numeric(detail[col], errors="coerce").fillna(0.0)

                # normalize datetime columns
                for col in ["Buy Time", "Sell Time", "Time"]:
                    if col in detail.columns:
                        detail[col] = pd.to_datetime(detail[col], errors="coerce")
                        try:
                            if getattr(detail[col].dt, "tz", None) is not None:
                                detail[col] = detail[col].dt.tz_convert(None)
                        except Exception:
                            try:
                                detail[col] = detail[col].dt.tz_localize(None)
                            except Exception:
                                pass

                total_pnl = float(detail["Total PnL"].sum()) if "Total PnL" in detail.columns else 0.0

                if abs(total_pnl) > 1e-12:
                    detail["Total Contribution %"] = detail["Total PnL"] / total_pnl
                else:
                    detail["Total Contribution %"] = 0.0

                preferred_cols = [
                    "Symbol",
                    "Lot ID",
                    "Buy Trade ID",
                    "Buy Time",
                    "Sell Trade ID",
                    "Sell Time",
                    "Lot Status",
                    "Qty",
                    "Open Qty",
                    "Cost Basis",
                    "Effective Cost",
                    "Sell Price",
                    "Market Price",
                    "Realized PnL",
                    "Unrealized PnL",
                    "Total PnL",
                    "Realized Contribution %",
                    "Unrealized Contribution %",
                    "Total Contribution %",
                    "Time",
                ]

                detail = detail[[c for c in preferred_cols if c in detail.columns]]

            # ---------------------------------
            # POSITION-LEVEL ATTRIBUTION
            # ---------------------------------
            position_df = pd.DataFrame()

            if detail is not None and not detail.empty:
                agg_cols = {}
                for col in ["Realized PnL", "Unrealized PnL", "Total PnL"]:
                    if col in detail.columns:
                        agg_cols[col] = "sum"

                if agg_cols:
                    position_df = detail.groupby("Symbol", dropna=False).agg(agg_cols).reset_index()

                    total_position_pnl = float(
                        position_df["Total PnL"].sum()) if "Total PnL" in position_df.columns else 0.0
                    if "Total PnL" in position_df.columns and abs(total_position_pnl) > 1e-12:
                        position_df["Contribution %"] = position_df["Total PnL"] / total_position_pnl
                    else:
                        position_df["Contribution %"] = 0.0



            # ---------------------------------
            # SUMMARY
            # ---------------------------------
            realized = realized_df["PnL"].sum() if not realized_df.empty else 0.0
            unrealized = open_df["PnL"].sum() if not open_df.empty else 0.0

            summary = {
                "realized_pnl": float(realized),
                "unrealized_pnl": float(unrealized),
                "total_pnl": float(realized + unrealized),
                "total_commission": float(df["Commission"].sum()),
                "total_slippage": float(df["Slippage"].sum()),
                "method": method
            }

            return {
                "summary": summary,
                "detail": detail,
                "positions": position_df,  # 👈 NEW
                "realized_trades": realized_df,
                "open_lots": open_df
            }

        except Exception as e:
            print("🚨 LOT ENGINE ERROR:", e)
            return self._empty_lot_response("ERROR")

    # =========================================
    # 🧠 TAX OPTIMIZER (FULLY FIXED)
    # =========================================
    def compute_tax_optimized_lot_selection(
            self,
            portfolio_id: str,
            sell_trade_id: str,
            objective: str = "MIN_GAIN",
            method_fallback: str = "FIFO",
    ):


        try:
            objective = str(objective).upper().strip()

            # ---------------------------------
            # LOAD SELL TRADE
            # ---------------------------------
            row = self.db.execute(text("""
                SELECT
                    symbol,
                    COALESCE(filled_qty, qty, 0),
                    COALESCE(avg_fill_price, limit_price, 0)
                FROM trade_orders
                WHERE id = :tid AND portfolio_id = :pid
                LIMIT 1
            """), {"tid": sell_trade_id, "pid": portfolio_id}).fetchone()

            if not row:
                return {
                    "summary": {"status": "sell_trade_not_found"},
                    "recommendation": pd.DataFrame(),
                    "raw_open_lots": pd.DataFrame()
                }

            symbol = str(row[0]).upper()
            sell_qty = float(row[1] or 0)
            sell_price = float(row[2] or 0)

            if sell_qty <= 0:
                return {
                    "summary": {"status": "invalid_sell_qty"},
                    "recommendation": pd.DataFrame(),
                    "raw_open_lots": pd.DataFrame()
                }

            # ---------------------------------
            # GET OPEN LOTS
            # ---------------------------------
            lot_pack = self.compute_lot_level_pnl_attribution(
                portfolio_id=portfolio_id,
                method=method_fallback
            )

            if not lot_pack:
                return {
                    "summary": {"status": "lot_engine_failed"},
                    "recommendation": pd.DataFrame(),
                    "raw_open_lots": pd.DataFrame()
                }

            open_lots = lot_pack.get("open_lots", pd.DataFrame()).copy()

            if open_lots is None or open_lots.empty:
                return {
                    "summary": {"status": "no_open_lots"},
                    "recommendation": pd.DataFrame(),
                    "raw_open_lots": pd.DataFrame()
                }

            open_lots["Symbol"] = open_lots["Symbol"].astype(str).str.upper()
            open_lots = open_lots[open_lots["Symbol"] == symbol].copy()

            if open_lots.empty:
                return {
                    "summary": {"status": "no_symbol_lots"},
                    "recommendation": pd.DataFrame(),
                    "raw_open_lots": open_lots
                }

            # ---------------------------------
            # VALIDATE COLUMNS
            # ---------------------------------
            required_cols = ["Open Qty", "Effective Cost"]
            for col in required_cols:
                if col not in open_lots.columns:
                    raise ValueError(f"Missing column: {col}")

            open_lots["Open Qty"] = pd.to_numeric(open_lots["Open Qty"], errors="coerce").fillna(0.0)
            open_lots["Effective Cost"] = pd.to_numeric(open_lots["Effective Cost"], errors="coerce").fillna(0.0)

            # ---------------------------------
            # CALCULATE PnL
            # ---------------------------------
            open_lots["PnL_per_share"] = sell_price - open_lots["Effective Cost"]
            open_lots["Total_PnL"] = open_lots["PnL_per_share"] * open_lots["Open Qty"]
            # ---------------------------------
            # HOLDING PERIOD (FIXED + SAFE)
            # ---------------------------------
            sell_time = pd.Timestamp.utcnow().tz_localize(None)

            if "Time" in open_lots.columns:
                open_lots["Time"] = pd.to_datetime(open_lots["Time"], errors="coerce")
                open_lots["Time"] = open_lots["Time"].dt.tz_localize(None)
                open_lots["Holding Days"] = (sell_time - open_lots["Time"]).dt.days
            else:
                open_lots["Holding Days"] = 0

            open_lots["Tax Class"] = open_lots["Holding Days"].apply(
                lambda x: "LONG" if x >= 365 else "SHORT"
            )
            # ---------------------------------
            # RANK
            # ---------------------------------
            from datetime import datetime

            sell_time = pd.Timestamp.utcnow().tz_localize(None)

            if "Time" in open_lots.columns:
                open_lots["Time"] = pd.to_datetime(open_lots["Time"], errors="coerce")
                open_lots["Time"] = open_lots["Time"].dt.tz_localize(None)

            open_lots["Holding Days"] = (sell_time - open_lots["Time"]).dt.days
            open_lots["Tax Class"] = open_lots["Holding Days"].apply(
                lambda x: "LONG" if x >= 365 else "SHORT"
            )

            # Tax-adjusted scoring
            # ---------------------------------
            # TAX-AWARE RANKING
            # ---------------------------------
            if objective == "MIN_GAIN":

                open_lots["Tax Priority"] = open_lots.apply(
                    lambda row: (
                        0 if row["PnL_per_share"] < 0 else 1,  # losses first
                        0 if row["Tax Class"] == "LONG" else 1,  # long-term better
                        row["PnL_per_share"]  # then smallest gain
                    ),
                    axis=1
                )

                ranked = open_lots.sort_values(
                    by=["PnL_per_share", "Tax Class"],
                    ascending=[True, True]
                )

            elif objective == "MAX_LOSS_HARVEST":

                ranked = open_lots.sort_values("PnL_per_share", ascending=True)
                ranked = ranked[ranked["PnL_per_share"] < 0]

                if ranked.empty:
                    ranked = open_lots.sort_values("PnL_per_share", ascending=True)

            elif objective == "MAX_GAIN":

                ranked = open_lots.sort_values("PnL_per_share", ascending=False)

            elif objective == "MAX_LOSS_HARVEST":
                ranked = open_lots.sort_values("PnL_per_share", ascending=True)
                ranked = ranked[ranked["PnL_per_share"] < 0]
                if ranked.empty:
                    ranked = open_lots.sort_values("PnL_per_share", ascending=True)

            elif objective == "MAX_GAIN":
                ranked = open_lots.sort_values("PnL_per_share", ascending=False)

            else:
                raise ValueError(f"Unsupported objective: {objective}")

            # ---------------------------------
            # SELECT LOTS
            # ---------------------------------
            qty_remaining = float(sell_qty)
            selections = []

            for _, lot in ranked.iterrows():
                if qty_remaining <= 0:
                    break

                lot_qty = float(lot["Open Qty"])
                if lot_qty <= 0:
                    continue

                selected_qty = min(qty_remaining, lot_qty)

                selections.append({
                    "Symbol": symbol,
                    "Selected Qty": selected_qty,
                    "Open Qty": lot_qty,
                    "Effective Cost": float(lot["Effective Cost"]),
                    "Sell Price": sell_price,
                    "PnL_per_share": float(lot["PnL_per_share"]),
                    "Estimated PnL": float(selected_qty * lot["PnL_per_share"])
                })

                qty_remaining -= selected_qty

            rec_df = pd.DataFrame(selections)

            total_pnl = float(rec_df["Estimated PnL"].sum()) if not rec_df.empty else 0.0

            # ---------------------------------
            # ✅ FIXED SUMMARY (CRITICAL)
            # ---------------------------------
            summary = {
                "status": "ok",
                "symbol": symbol,
                "sell_qty_requested": sell_qty,
                "sell_qty_selected": float(rec_df["Selected Qty"].sum()) if not rec_df.empty else 0.0,
                "qty_unfilled": float(qty_remaining),
                "estimated_realized_pnl": total_pnl,
                "objective": objective,
                "method_basis": method_fallback
            }

            return {
                "summary": summary,
                "recommendation": rec_df,
                "raw_open_lots": open_lots
            }

        except Exception as e:
            print("🚨 TAX OPTIMIZER ERROR:", e)
            return {
                "summary": {"status": "error", "message": str(e)},
                "recommendation": pd.DataFrame(),
                "raw_open_lots": pd.DataFrame()
            }



    # =========================================
    # 🚫 WASH SALE DETECTION
    # =========================================
    def detect_wash_sales(
            self,
            portfolio_id: str,
            lookback_days: int = 30,
    ):
        import pandas as pd
        from sqlalchemy import text

        try:
            trades = self.db.execute(text("""
                SELECT
                    id,
                    symbol,
                    LOWER(side) AS side,
                    COALESCE(filled_qty, qty, 0) AS qty,
                    COALESCE(avg_fill_price, limit_price, 0) AS price,
                    COALESCE(filled_at, submitted_at, created_at) AS trade_time
                FROM trade_orders
                WHERE portfolio_id = :pid
                  AND LOWER(COALESCE(status, '')) IN ('filled', 'partially_filled', 'executed')
                ORDER BY COALESCE(filled_at, submitted_at, created_at) ASC, id ASC
            """), {"pid": portfolio_id}).fetchall()

            cols = ["Trade ID", "Symbol", "Side", "Qty", "Price", "Time"]
            df = pd.DataFrame(trades, columns=cols) if trades else pd.DataFrame(columns=cols)

            if df.empty:
                return {
                    "summary": {
                        "status": "ok",
                        "wash_sale_count": 0,
                        "flagged_symbols": 0
                    },
                    "detail": pd.DataFrame()
                }

            df["Symbol"] = df["Symbol"].astype(str).str.upper().str.strip()
            df["Side"] = df["Side"].astype(str).str.lower().str.strip()
            df["Qty"] = pd.to_numeric(df["Qty"], errors="coerce").fillna(0.0)
            df["Price"] = pd.to_numeric(df["Price"], errors="coerce").fillna(0.0)
            df["Time"] = pd.to_datetime(df["Time"], errors="coerce")

            if getattr(df["Time"].dt, "tz", None) is not None:
                df["Time"] = df["Time"].dt.tz_convert(None)

            df = df[
                df["Symbol"].ne("") &
                df["Qty"].gt(0) &
                df["Price"].gt(0) &
                df["Side"].isin(["buy", "sell"])
            ].copy()

            if df.empty:
                return {
                    "summary": {
                        "status": "ok",
                        "wash_sale_count": 0,
                        "flagged_symbols": 0
                    },
                    "detail": pd.DataFrame()
                }

            # Use current lot engine to estimate sell-side realized pnl rows
            lot_pack = self.compute_lot_level_pnl_attribution(
                portfolio_id=portfolio_id,
                method="FIFO"
            )
            realized_trades = lot_pack.get("realized_trades", pd.DataFrame()).copy()

            if realized_trades is None or realized_trades.empty:
                return {
                    "summary": {
                        "status": "ok",
                        "wash_sale_count": 0,
                        "flagged_symbols": 0
                    },
                    "detail": pd.DataFrame()
                }

            # Expected columns from your current lot engine:
            # Symbol, Sell Trade ID, Sell Time, Matched Qty, PnL
            # Handle minimal schema safely
            if "Symbol" not in realized_trades.columns or "PnL" not in realized_trades.columns:
                return {
                    "summary": {
                        "status": "ok",
                        "wash_sale_count": 0,
                        "flagged_symbols": 0
                    },
                    "detail": pd.DataFrame()
                }

            if "Sell Time" in realized_trades.columns:
                realized_trades["Sell Time"] = pd.to_datetime(realized_trades["Sell Time"], errors="coerce")
                if getattr(realized_trades["Sell Time"].dt, "tz", None) is not None:
                    realized_trades["Sell Time"] = realized_trades["Sell Time"].dt.tz_convert(None)
            else:
                realized_trades["Sell Time"] = pd.NaT

            if "Matched Qty" not in realized_trades.columns:
                realized_trades["Matched Qty"] = 0.0

            realized_trades["Matched Qty"] = pd.to_numeric(
                realized_trades["Matched Qty"], errors="coerce"
            ).fillna(0.0)

            loss_sales = realized_trades[realized_trades["PnL"] < 0].copy()

            if loss_sales.empty:
                return {
                    "summary": {
                        "status": "ok",
                        "wash_sale_count": 0,
                        "flagged_symbols": 0
                    },
                    "detail": pd.DataFrame()
                }

            buy_df = df[df["Side"] == "buy"].copy()

            flags = []

            for _, loss_row in loss_sales.iterrows():
                symbol = str(loss_row["Symbol"]).upper().strip()
                sell_time = loss_row["Sell Time"]
                loss_qty = float(loss_row["Matched Qty"])
                loss_pnl = float(loss_row["PnL"])

                if pd.isna(sell_time):
                    continue

                window_start = sell_time - pd.Timedelta(days=lookback_days)
                window_end = sell_time + pd.Timedelta(days=lookback_days)

                rebuys = buy_df[
                    (buy_df["Symbol"] == symbol) &
                    (buy_df["Time"] >= window_start) &
                    (buy_df["Time"] <= window_end)
                ].copy()

                if rebuys.empty:
                    continue

                rebuy_qty = float(rebuys["Qty"].sum())
                disallowed_qty = min(loss_qty, rebuy_qty)

                if disallowed_qty <= 0:
                    continue

                flags.append({
                    "Symbol": symbol,
                    "Sell Time": sell_time,
                    "Loss Qty": loss_qty,
                    "Loss PnL": loss_pnl,
                    "Rebuy Qty (±30d)": rebuy_qty,
                    "Potential Disallowed Qty": disallowed_qty,
                    "Wash Sale Flag": True
                })

            detail = pd.DataFrame(flags)

            summary = {
                "status": "ok",
                "wash_sale_count": int(len(detail)),
                "flagged_symbols": int(detail["Symbol"].nunique()) if not detail.empty else 0
            }

            return {
                "summary": summary,
                "detail": detail
            }

        except Exception as e:
            print("🚨 WASH SALE ERROR:", e)
            return {
                "summary": {
                    "status": "error",
                    "message": str(e),
                    "wash_sale_count": 0,
                    "flagged_symbols": 0
                },
                "detail": pd.DataFrame()
            }


    # =========================================
    # 📊 TAX-ADJUSTED PORTFOLIO SCORE
    # =========================================
    def compute_tax_adjusted_portfolio_score(
            self,
            portfolio_id: str,
            base_portfolio_score: float | None = None,
    ):


        try:
            # Pull lot-level attribution
            lot_pack = self.compute_lot_level_pnl_attribution(
                portfolio_id=portfolio_id,
                method="FIFO"
            )

            summary = lot_pack.get("summary", {}) if lot_pack else {}
            open_lots = lot_pack.get("open_lots", pd.DataFrame()) if lot_pack else pd.DataFrame()

            realized_df = lot_pack.get("realized_trades", pd.DataFrame())

            if realized_df is not None and not realized_df.empty:
                realized_pnl = float(realized_df["PnL"].sum())
            else:
                realized_pnl = 0.0

            # ---------------------------------
            # REALIZED CONTRIBUTION
            # ---------------------------------
            total_realized = float(realized_df["PnL"].sum()) if not realized_df.empty else 0.0

            if not realized_df.empty and total_realized != 0:
                realized_df["Contribution %"] = realized_df["PnL"] / total_realized
            else:
                realized_df["Contribution %"] = 0.0

            unrealized_pnl = float(summary.get("unrealized_pnl", 0.0) or 0.0)
            total_pnl = float(summary.get("total_pnl", 0.0) or 0.0)

            wash_pack = self.detect_wash_sales(portfolio_id=portfolio_id)
            wash_summary = wash_pack.get("summary", {}) if wash_pack else {}
            wash_count = int(wash_summary.get("wash_sale_count", 0) or 0)

            # Start with provided score or a neutral fallback
            score = float(base_portfolio_score) if base_portfolio_score is not None else 50.0

            # ---------------------------------
            # TAX EFFICIENCY HEURISTICS
            # ---------------------------------
            # Reward unrealized > realized (tax deferral)
            if total_pnl != 0:
                realized_ratio = abs(realized_pnl) / max(abs(total_pnl), 1e-9)
                unrealized_ratio = abs(unrealized_pnl) / max(abs(total_pnl), 1e-9)
            else:
                realized_ratio = 0.0
                unrealized_ratio = 0.0

            score += unrealized_ratio * 10.0
            score -= realized_ratio * 10.0

            # Penalize wash-sale risk
            score -= min(wash_count * 5.0, 20.0)

            # Reward loss inventory for harvesting opportunity
            loss_inventory_bonus = 0.0
            long_term_bonus = 0.0

            if open_lots is not None and not open_lots.empty:
                open_lots = open_lots.copy()

                if "PnL" in open_lots.columns:
                    open_lots["PnL"] = pd.to_numeric(open_lots["PnL"], errors="coerce").fillna(0.0)
                    loss_lots = open_lots[open_lots["PnL"] < 0]
                    gain_lots = open_lots[open_lots["PnL"] > 0]

                    loss_inventory_bonus = min(len(loss_lots) * 1.5, 10.0)
                    score += loss_inventory_bonus

                    # Holding-period preference if Time exists
                    if "Time" in open_lots.columns:
                        time_col = "Buy Time" if "Buy Time" in open_lots.columns else "Time"

                        open_lots[time_col] = pd.to_datetime(open_lots[time_col], errors="coerce")
                        open_lots[time_col] = open_lots[time_col].dt.tz_localize(None)

                        age_days = (pd.Timestamp.utcnow().tz_localize(None) - open_lots[time_col]).dt.days
                        if getattr(open_lots["Time"].dt, "tz", None) is not None:
                            open_lots["Time"] = open_lots["Time"].dt.tz_convert(None)

                        age_days = (pd.Timestamp.utcnow().tz_localize(None) - open_lots["Time"]).dt.days
                        long_term_bonus = float((age_days >= 365).mean() * 10.0) if len(open_lots) else 0.0
                        score += long_term_bonus


            score = max(0.0, min(100.0, score))

            detail = pd.DataFrame([{
                "Base Score": float(base_portfolio_score) if base_portfolio_score is not None else 50.0,
                "Realized PnL": realized_pnl,
                "Unrealized PnL": unrealized_pnl,
                "Total PnL": total_pnl,
                "Wash Sale Count": wash_count,
                "Loss Inventory Bonus": loss_inventory_bonus,
                "Long-Term Bonus": long_term_bonus,
                "Tax-Adjusted Score": score
            }])

            return {
                "summary": {
                    "status": "ok",
                    "tax_adjusted_score": score,
                    "wash_sale_count": wash_count
                },
                "detail": detail
            }

        except Exception as e:
            print("🚨 TAX-ADJUSTED SCORE ERROR:", e)
            return {
                "summary": {
                    "status": "error",
                    "message": str(e),
                    "tax_adjusted_score": 0.0,
                    "wash_sale_count": 0
                },
                "detail": pd.DataFrame()
            }

    # =========================================
    # 🧩 EMPTY RESPONSE HELPER
    # =========================================
    def _empty_lot_response(self, method: str = "FIFO"):

        print("DEBUG NavService methods:", dir(self))
        return {
            "summary": {
                "realized_pnl": 0.0,
                "unrealized_pnl": 0.0,
                "total_pnl": 0.0,
                "total_commission": 0.0,
                "total_slippage": 0.0,
                "method": method
            },
            "detail": pd.DataFrame(),
            "realized_trades": pd.DataFrame(),
            "open_lots": pd.DataFrame()
        }

    def compute_benchmark_relative_attribution(
            self,
            portfolio_id: str,
            benchmark_symbol: str = "SPY",
            method: str = "FIFO",
    ):


        try:
            # ---------------------------------
            # BASE POSITION ATTRIBUTION
            # ---------------------------------
            lot_pack = self.compute_lot_level_pnl_attribution(
                portfolio_id=portfolio_id,
                method=method
            )

            positions = lot_pack.get("positions", pd.DataFrame()).copy()
            open_lots = lot_pack.get("open_lots", pd.DataFrame()).copy()

            if positions is None or positions.empty:
                return {
                    "summary": {
                        "status": "no_positions",
                        "benchmark_symbol": benchmark_symbol
                    },
                    "detail": pd.DataFrame()
                }

            # ---------------------------------
            # LOAD BENCHMARK SERIES
            # ---------------------------------
            try:
                bench = self.build_benchmark_series(symbol=benchmark_symbol)
            except Exception:
                bench = pd.DataFrame()

            if bench is None or bench.empty:
                return {
                    "summary": {
                        "status": "no_benchmark",
                        "benchmark_symbol": benchmark_symbol
                    },
                    "detail": pd.DataFrame()
                }

            # Expect latest benchmark cumulative return from existing benchmark logic
            benchmark_return = 0.0
            if "Benchmark" in bench.columns and len(bench) > 1:
                b0 = float(bench["Benchmark"].iloc[0] or 0.0)
                b1 = float(bench["Benchmark"].iloc[-1] or 0.0)
                if abs(b0) > 1e-12:
                    benchmark_return = (b1 / b0) - 1.0

            # ---------------------------------
            # POSITION WEIGHTS
            # ---------------------------------
            # Prefer market-value weighted open lots if available
            position_weights = pd.DataFrame()

            if open_lots is not None and not open_lots.empty:
                temp = open_lots.copy()

                if "Market Price" not in temp.columns:
                    temp["Market Price"] = 0.0

                temp["Open Qty"] = pd.to_numeric(temp.get("Open Qty", 0.0), errors="coerce").fillna(0.0)
                temp["Market Price"] = pd.to_numeric(temp.get("Market Price", 0.0), errors="coerce").fillna(0.0)
                temp["Market Value"] = temp["Open Qty"] * temp["Market Price"]

                position_weights = (
                    temp.groupby("Symbol", dropna=False)["Market Value"]
                    .sum()
                    .reset_index()
                )

                total_mv = float(position_weights["Market Value"].sum()) if not position_weights.empty else 0.0
                if abs(total_mv) > 1e-12:
                    position_weights["Weight"] = position_weights["Market Value"] / total_mv
                else:
                    position_weights["Weight"] = 0.0
            else:
                position_weights = positions[["Symbol"]].copy()
                n = len(position_weights)
                position_weights["Weight"] = (1.0 / n) if n > 0 else 0.0

            # ---------------------------------
            # MERGE
            # ---------------------------------
            detail = positions.copy()
            detail = detail.merge(
                position_weights[["Symbol", "Weight"]],
                on="Symbol",
                how="left"
            )

            detail["Weight"] = pd.to_numeric(detail["Weight"], errors="coerce").fillna(0.0)
            detail["Total PnL"] = pd.to_numeric(detail.get("Total PnL", 0.0), errors="coerce").fillna(0.0)

            total_portfolio_pnl = float(detail["Total PnL"].sum()) if not detail.empty else 0.0

            if abs(total_portfolio_pnl) > 1e-12:
                detail["Portfolio Contribution %"] = detail["Total PnL"] / total_portfolio_pnl
            else:
                detail["Portfolio Contribution %"] = 0.0

            # ---------------------------------
            # BENCHMARK-RELATIVE ATTRIBUTION
            # ---------------------------------
            # Simple but useful model:
            # expected contribution if portfolio matched benchmark return
            # expected_pnl = weight * benchmark_return * total portfolio value proxy
            #
            # Since your current pipeline is PnL-centric, use total absolute pnl as proxy base.
            proxy_base = float(detail["Total PnL"].abs().sum()) if not detail.empty else 0.0

            if abs(proxy_base) > 1e-12:
                detail["Benchmark-Expected PnL"] = detail["Weight"] * benchmark_return * proxy_base
            else:
                detail["Benchmark-Expected PnL"] = 0.0

            detail["Excess Contribution"] = detail["Total PnL"] - detail["Benchmark-Expected PnL"]

            total_excess = float(detail["Excess Contribution"].sum()) if not detail.empty else 0.0
            if abs(total_excess) > 1e-12:
                detail["Excess Contribution %"] = detail["Excess Contribution"] / total_excess
            else:
                detail["Excess Contribution %"] = 0.0

            detail = detail.sort_values("Excess Contribution", ascending=False).reset_index(drop=True)

            summary = {
                "status": "ok",
                "benchmark_symbol": benchmark_symbol,
                "benchmark_return": benchmark_return,
                "total_excess_contribution": total_excess
            }

            return {
                "summary": summary,
                "detail": detail
            }

        except Exception as e:
            print("🚨 BENCHMARK ATTRIBUTION ERROR:", e)
            return {
                "summary": {
                    "status": "error",
                    "message": str(e),
                    "benchmark_symbol": benchmark_symbol
                },
                "detail": pd.DataFrame()
            }

    def compute_sector_benchmark_attribution(
            self,
            portfolio_id: str,
            benchmark_symbol: str = "SPY",
            method: str = "FIFO",
    ):

        def _normalize_sector(self, sector: str) -> str:
            if not sector:
                return "Unknown"

            s = sector.lower()

            if "tech" in s:
                return "Technology"
            if "health" in s:
                return "Healthcare"
            if "fin" in s:
                return "Financials"
            if "energy" in s:
                return "Energy"
            if "consumer" in s:
                return "Consumer"
            if "indus" in s:
                return "Industrials"

            return sector

        try:
            # ---------------------------------
            # BASE DATA
            # ---------------------------------
            bench_attr = self.compute_benchmark_relative_attribution(
                portfolio_id=portfolio_id,
                benchmark_symbol=benchmark_symbol,
                method=method
            )

            df = bench_attr.get("detail", pd.DataFrame()).copy()

            if df is None or df.empty:
                return {
                    "summary": {"status": "no_data"},
                    "detail": pd.DataFrame()
                }

            # ---------------------------------
            # ADD SECTOR
            # ---------------------------------
            symbols = df["Symbol"].dropna().unique().tolist()

            meta = []
            for sym in symbols:
                try:
                    sector = self._get_sector(sym)

                    meta.append({
                        "Symbol": sym,
                        "Sector": sector
                    })
                except Exception:
                    meta.append({
                        "Symbol": sym,
                        "Sector": "Unknown"
                    })

            meta_df = pd.DataFrame(meta)

            df = df.merge(meta_df, on="Symbol", how="left")
            df["Sector"] = df["Sector"].fillna("Unknown")

            # ---------------------------------
            # AGGREGATE
            # ---------------------------------
            agg_cols = {}
            for col in [
                "Weight",
                "Total PnL",
                "Benchmark-Expected PnL",
                "Excess Contribution"
            ]:
                if col in df.columns:
                    agg_cols[col] = "sum"

            if not agg_cols:
                return {
                    "summary": {"status": "no_valid_columns"},
                    "detail": pd.DataFrame()
                }

            sector_df = df.groupby("Sector", dropna=False).agg(agg_cols).reset_index()

            # ---------------------------------
            # CONTRIBUTION %
            # ---------------------------------
            total_excess = float(
                sector_df["Excess Contribution"].sum()) if "Excess Contribution" in sector_df.columns else 0.0

            if abs(total_excess) > 1e-12:
                sector_df["Excess Contribution %"] = sector_df["Excess Contribution"] / total_excess
            else:
                sector_df["Excess Contribution %"] = 0.0

            # ---------------------------------
            # SORT
            # ---------------------------------
            if "Excess Contribution" in sector_df.columns:
                sector_df = sector_df.sort_values("Excess Contribution", ascending=False).reset_index(drop=True)

            return {
                "summary": {
                    "status": "ok",
                    "benchmark_symbol": benchmark_symbol,
                    "top_sector": sector_df.iloc[0]["Sector"] if not sector_df.empty else None,
                    "bottom_sector": sector_df.iloc[-1]["Sector"] if not sector_df.empty else None
                },
                "detail": sector_df
            }


        except Exception as e:
            print("🚨 SECTOR ATTRIBUTION ERROR:", e)
            return {
                "summary": {"status": "error", "message": str(e)},
                "detail": pd.DataFrame()
            }

    def compute_portfolio_signal_overlay(
            self,
            portfolio_id: str,
            benchmark_symbol: str = "SPY",
            method: str = "FIFO",
    ):

        try:
            bench_attr_pack = self.compute_benchmark_relative_attribution(
                portfolio_id=portfolio_id,
                benchmark_symbol=benchmark_symbol,
                method=method
            )

            detail = bench_attr_pack.get("detail", pd.DataFrame()).copy()
            summary = bench_attr_pack.get("summary", {})

            if detail is None or detail.empty:
                return {
                    "summary": {
                        "status": "no_data",
                        "signal": "Hold",
                        "signal_score": 50.0
                    },
                    "leaders": pd.DataFrame(),
                    "laggards": pd.DataFrame()
                }

            detail["Excess Contribution"] = pd.to_numeric(
                detail.get("Excess Contribution", 0.0), errors="coerce"
            ).fillna(0.0)

            leaders = detail.sort_values("Excess Contribution", ascending=False).head(5).reset_index(drop=True)
            laggards = detail.sort_values("Excess Contribution", ascending=True).head(5).reset_index(drop=True)

            total_excess = float(detail["Excess Contribution"].sum())
            positive_count = int((detail["Excess Contribution"] > 0).sum())
            negative_count = int((detail["Excess Contribution"] < 0).sum())

            # Simple portfolio score overlay
            signal_score = 50.0
            signal_score += min(max(total_excess, -20.0), 20.0)

            breadth = positive_count - negative_count
            signal_score += max(min(breadth * 2.5, 15.0), -15.0)

            signal_score = max(0.0, min(100.0, signal_score))

            if signal_score >= 70:
                signal = "Buy"
            elif signal_score >= 55:
                signal = "Hold"
            else:
                signal = "Reduce"

            return {
                "summary": {
                    "status": "ok",
                    "signal": signal,
                    "signal_score": signal_score,
                    "total_excess": total_excess,
                    "benchmark_symbol": benchmark_symbol
                },
                "leaders": leaders,
                "laggards": laggards
            }

        except Exception as e:
            print("🚨 PORTFOLIO SIGNAL OVERLAY ERROR:", e)
            return {
                "summary": {
                    "status": "error",
                    "message": str(e),
                    "signal": "Hold",
                    "signal_score": 50.0
                },
                "leaders": pd.DataFrame(),
                "laggards": pd.DataFrame()
            }

    def compute_allocation_selection_attribution(
            self,
            portfolio_id: str,
            benchmark_symbol: str = "SPY",
            method: str = "FIFO",
    ):

        def _normalize_sector(self, sector: str) -> str:
            if not sector:
                return "Unknown"
            sector = self._get_sector(sym)
            print(f"DEBUG sector lookup: {sym} -> {sector}")
            s = sector.lower()

            if "tech" in s:
                return "Technology"
            if "health" in s:
                return "Healthcare"
            if "fin" in s:
                return "Financials"
            if "energy" in s:
                return "Energy"
            if "consumer" in s:
                return "Consumer"
            if "indus" in s:
                return "Industrials"
            print("DEBUG symbols:", symbols)
            return sector

        try:
            # ---------------------------------
            # BASE DATA
            # ---------------------------------
            bench_attr = self.compute_benchmark_relative_attribution(
                portfolio_id=portfolio_id,
                benchmark_symbol=benchmark_symbol,
                method=method
            )

            df = bench_attr.get("detail", pd.DataFrame()).copy()

            if df is None or df.empty:
                return {"summary": {"status": "no_data"}, "detail": pd.DataFrame()}

            # ---------------------------------
            # ADD SECTOR
            # ---------------------------------
            symbols = df["Symbol"].dropna().unique().tolist()

            meta = []
            for sym in symbols:
                try:
                    sec = self.get_security_metadata(sym)
                    meta.append({"Symbol": sym, "Sector": sec.get("sector", "Unknown")})
                except Exception:
                    meta.append({"Symbol": sym, "Sector": "Unknown"})

            meta_df = pd.DataFrame(meta)
            df = df.merge(meta_df, on="Symbol", how="left")
            df["Sector"] = df["Sector"].fillna("Unknown")

            # ---------------------------------
            # WEIGHTS & RETURNS
            # ---------------------------------
            df["Weight"] = pd.to_numeric(df.get("Weight", 0.0), errors="coerce").fillna(0.0)
            df["Total PnL"] = pd.to_numeric(df.get("Total PnL", 0.0), errors="coerce").fillna(0.0)

            total_portfolio_pnl = float(df["Total PnL"].sum())

            if abs(total_portfolio_pnl) > 1e-12:
                df["Portfolio Return Proxy"] = df["Total PnL"] / total_portfolio_pnl
            else:
                df["Portfolio Return Proxy"] = 0.0

            # ---------------------------------
            # SECTOR AGGREGATION
            # ---------------------------------
            sector = df.groupby("Sector").agg({
                "Weight": "sum",
                "Portfolio Return Proxy": "sum"
            }).reset_index()

            # ---------------------------------
            # BENCHMARK RETURN
            # ---------------------------------
            bench_series = self.build_benchmark_series(symbol=benchmark_symbol)

            bench_return = 0.0
            if bench_series is not None and not bench_series.empty and len(bench_series) > 1:
                b0 = float(bench_series["Benchmark"].iloc[0])
                b1 = float(bench_series["Benchmark"].iloc[-1])
                if abs(b0) > 1e-12:
                    bench_return = (b1 / b0) - 1.0

            # ---------------------------------
            # SIMPLIFIED BENCHMARK SECTOR WEIGHTS
            # ---------------------------------
            # If you don't have real benchmark weights, assume equal or proportional
            n = len(sector)
            sector["Benchmark Weight"] = 1.0 / n if n > 0 else 0.0

            # ---------------------------------
            # ALLOCATION EFFECT
            # ---------------------------------
            sector["Allocation Effect"] = (
                    (sector["Weight"] - sector["Benchmark Weight"]) * bench_return
            )

            # ---------------------------------
            # SELECTION EFFECT
            # ---------------------------------
            sector["Selection Effect"] = (
                    sector["Benchmark Weight"] *
                    (sector["Portfolio Return Proxy"] - bench_return)
            )

            # ---------------------------------
            # INTERACTION (OPTIONAL)
            # ---------------------------------
            sector["Interaction Effect"] = (
                    (sector["Weight"] - sector["Benchmark Weight"]) *
                    (sector["Portfolio Return Proxy"] - bench_return)
            )

            # ---------------------------------
            # TOTAL EFFECT
            # ---------------------------------
            sector["Total Effect"] = (
                    sector["Allocation Effect"] +
                    sector["Selection Effect"] +
                    sector["Interaction Effect"]
            )

            # ---------------------------------
            # SORT
            # ---------------------------------
            sector = sector.sort_values("Total Effect", ascending=False)

            # ---------------------------------
            # SUMMARY
            # ---------------------------------
            summary = {
                "status": "ok",
                "benchmark_return": bench_return,
                "top_sector": sector.iloc[0]["Sector"] if not sector.empty else None,
                "bottom_sector": sector.iloc[-1]["Sector"] if not sector.empty else None
            }

            return {
                "summary": summary,
                "detail": sector
            }

        except Exception as e:
            print("🚨 ALLOCATION/SELECTION ERROR:", e)
            return {
                "summary": {"status": "error", "message": str(e)},
                "detail": pd.DataFrame()
            }

    def _get_benchmark_return(self, benchmark_symbol="SPY"):
        try:
            import yfinance as yf

            data = yf.download(benchmark_symbol, period="3mo", progress=False)

            if data is None or data.empty:
                return 0.0

            start = float(data["Close"].iloc[0])
            end = float(data["Close"].iloc[-1])

            if abs(start) > 1e-12:
                return (end / start) - 1.0

            return 0.0

        except Exception as e:
            print("⚠️ BENCHMARK FETCH ERROR:", e)
            return 0.0



