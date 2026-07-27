from __future__ import annotations

from typing import Any

import pandas as pd
from sqlalchemy import text
from modules.market_data.service import get_latest_price_map


class AlphaEngine:
    def __init__(
        self,
        db=None,
        market_data_service=None,
    ):
        self.db = db
        self.market_data_service = market_data_service

    # ---------------------------------
    # Basic signal calculation
    # ---------------------------------
    def build_signal_frame(self, symbols: list[str]) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []

        clean_symbols = []
        for s in symbols or []:
            sym = str(s).upper().strip()
            if sym and sym not in clean_symbols:
                clean_symbols.append(sym)

        if not clean_symbols:
            return pd.DataFrame()

        price_map = get_latest_price_map(clean_symbols) or {}
        price_map = {
            str(k).upper().strip(): self._safe_num(v, default=0.0)
            for k, v in price_map.items()
            if str(k).strip()
        }

        previous_close_map: dict[str, float] = {}

        # Fill any missing prices before scoring. This is intentionally done
        # before the score loop so Alpha Scores do not get built from None.
        for symbol in clean_symbols:
            current_price = self._safe_num(
                price_map.get(symbol),
                default=0.0,
            )

            previous_close = 0.0

            if current_price <= 0:
                current_price, previous_close = self._lookup_price_pair(symbol)
            else:
                previous_close = self._lookup_previous_close(symbol)

            if current_price and current_price > 0:
                price_map[symbol] = float(current_price)

            if previous_close and previous_close > 0:
                previous_close_map[symbol] = float(previous_close)

        print("=" * 80)
        print("ALPHA PRICE MAP")
        print("COUNT:", len([v for v in price_map.values() if v and v > 0]))
        for symbol in clean_symbols[:10]:
            print(f"{symbol}: {price_map.get(symbol)}")
        print("=" * 80)

        for symbol in clean_symbols:
            current_price = self._safe_num(
                price_map.get(symbol),
                default=0.0,
            )

            previous_close = self._safe_num(
                previous_close_map.get(symbol),
                default=0.0,
            )
            print(
                f"ALPHA INPUT "
                f"{symbol} "
                f"price={current_price} "
                f"prev_close={previous_close}"
            )
            score = self._score_symbol(
                symbol,
                current_price=current_price if current_price > 0 else None,
                previous_close=previous_close if previous_close > 0 else None,
            )

            rows.append({
                "Symbol": symbol,
                "Current Price": current_price if current_price > 0 else None,
                "Previous Close": previous_close if previous_close > 0 else None,
                "Alpha Score": score["alpha_score"],
                "Momentum Score": score["momentum_score"],
                "Quality Score": score["quality_score"],
                "Value Score": score["value_score"],
                "Volatility Penalty": score["vol_penalty"],
                "Composite Score": score["composite_score"],
            })

        if not rows:
            return pd.DataFrame()

        return (
            pd.DataFrame(rows)
            .sort_values(
                "Composite Score",
                ascending=False,
            )
            .reset_index(drop=True)
        )

    # ---------------------------------
    # Lightweight scoring model
    # ---------------------------------
    def _score_symbol(
        self,
        symbol: str,
        current_price: float | None = None,
        previous_close: float | None = None,
    ) -> dict:
        momentum_score = 0.0
        quality_score = 0.0
        value_score = 0.0
        growth_score = 0.0
        vol_penalty = 0.0

        try:
            price = self._safe_num(current_price, default=0.0)
            prev_close = self._safe_num(previous_close, default=0.0)

            if price <= 0 and self.market_data_service is not None:
                price, prev_close = self._lookup_price_pair(symbol)
                print(
                    f"LOOKUP RESULT {symbol} "
                    f"price={price} "
                    f"prev_close={prev_close}"
                )

            if price > 0:
                if prev_close <= 0:
                    prev_close = price

                print(
                    f"SCORE INPUT {symbol} "
                    f"price={price} "
                    f"prev_close={prev_close}"
                )

                chg = (price / prev_close) - 1.0 if prev_close > 0 else 0.0

                momentum_score = max(
                    min(chg * 10.0, 1.0),
                    -1.0,
                )

        except Exception as e:
            print(f"ALPHA MOMENTUM SCORE ERROR {symbol}: {e}")

        # Optional profile/fundamental hooks if your service exposes them.
        try:
            if (
                self.market_data_service
                and hasattr(self.market_data_service, "get_company_profile")
            ):
                profile = self.market_data_service.get_company_profile(symbol) or {}
                quality_score += 0.1 if profile.get("ipo") else 0.0
        except Exception:
            pass

        try:
            snapshot = self._get_latest_snapshot(symbol)

            if snapshot:
                quality_score = (
                        self._safe_num(snapshot.get("quality_score"))
                        / 100.0
                )

                value_score = (
                        self._safe_num(snapshot.get("value_score"))
                        / 100.0
                )

                analytics_momentum = (
                        self._safe_num(snapshot.get("momentum_score"))
                        / 100.0
                )

                risk_score = (
                        self._safe_num(snapshot.get("risk_score"))
                        / 100.0
                )

                sentiment_score = (
                        self._safe_num(snapshot.get("sentiment_score"))
                        / 100.0
                )

                momentum_score = (
                        0.50 * momentum_score
                        + 0.50 * analytics_momentum
                )

                vol_penalty = risk_score

        except Exception as e:
            print(f"ALPHA SNAPSHOT ERROR {symbol}: {e}")

        alpha_score = (
                0.30 * momentum_score
                + 0.25 * quality_score
                + 0.20 * value_score
                + 0.15 * growth_score
                - 0.10 * vol_penalty
        )

        return {
            "alpha_score": float(alpha_score),
            "momentum_score": float(momentum_score),
            "quality_score": float(quality_score),
            "value_score": float(value_score),
            "growth_score": float(growth_score),
            "vol_penalty": float(vol_penalty),
            "composite_score": float(alpha_score),
        }

    # ---------------------------------
    # Target-weight conversion
    # ---------------------------------
    def scores_to_target_weights(
        self,
        score_df: pd.DataFrame | None = None,
        signal_df: pd.DataFrame | None = None,
        top_n: int | None = None,
        min_weight: float = 0.05,
        max_weight: float = 0.50,
        **kwargs,
    ) -> pd.DataFrame:
        if score_df is None:
            score_df = signal_df

        if score_df is None or score_df.empty:
            return pd.DataFrame(
                columns=[
                    "Symbol",
                    "Composite Score",
                    "Target Weight",
                ]
            )

        df = score_df.copy()

        if "Composite Score" not in df.columns:
            return pd.DataFrame(
                columns=[
                    "Symbol",
                    "Composite Score",
                    "Target Weight",
                ]
            )

        if top_n is not None and top_n > 0:
            df = (
                df.sort_values(
                    "Composite Score",
                    ascending=False,
                )
                .head(int(top_n))
                .reset_index(drop=True)
            )

        scores = pd.to_numeric(
            df["Composite Score"],
            errors="coerce",
        ).fillna(0.0)

        scores = scores.clip(lower=0.0)
        total_score = float(scores.sum())

        if total_score <= 0:
            equal_weight = 1.0 / len(df) if len(df) > 0 else 0.0
            df["Target Weight"] = equal_weight
        else:
            df["Target Weight"] = scores / total_score

        df["Target Weight"] = df["Target Weight"].clip(
            lower=min_weight,
            upper=max_weight,
        )

        weight_sum = float(df["Target Weight"].sum())

        if weight_sum > 0:
            df["Target Weight"] = df["Target Weight"] / weight_sum

        return (
            df[
                [
                    "Symbol",
                    "Composite Score",
                    "Target Weight",
                ]
            ]
            .sort_values(
                "Target Weight",
                ascending=False,
            )
            .reset_index(drop=True)
        )

    # ---------------------------------
    # Price helpers
    # ---------------------------------
    def _lookup_price_pair(self, symbol: str) -> tuple[float, float]:
        """
        Returns (latest_price, previous_close). This method is intentionally
        defensive because different market-data paths return quote dicts,
        scalar prices, or historical DataFrames.
        """
        sym = str(symbol).upper().strip()

        quote_price, quote_prev = self._lookup_from_market_data_service(sym)
        if quote_price > 0:
            return quote_price, quote_prev

        history_price, history_prev = self._lookup_from_history_providers(sym)
        if history_price > 0:
            return history_price, history_prev

        internal_price = self._lookup_from_service_internal(sym)
        if internal_price > 0:
            return internal_price, 0.0

        return 0.0, 0.0

    def _lookup_from_market_data_service(self, symbol: str) -> tuple[float, float]:
        if self.market_data_service is None:
            return 0.0, 0.0

        try:
            q = self.market_data_service.get_quote(symbol)

            if isinstance(q, dict):
                price = self._extract_price_from_dict(q)
                prev_close = self._safe_num(
                    q.get(
                        "previous_close",
                        q.get("prev_close", q.get("pc", q.get("previousClose"))),
                    ),
                    default=0.0,
                )
                return price, prev_close

            return self._safe_num(q, default=0.0), 0.0

        except Exception as e:
            print(f"ALPHA QUOTE FALLBACK ERROR {symbol}: {e}")
            return 0.0, 0.0

    def _lookup_previous_close(self, symbol: str) -> float:
        if self.market_data_service is None:
            return 0.0

        try:
            if hasattr(self.market_data_service, "get_previous_close"):
                return self._safe_num(
                    self.market_data_service.get_previous_close(symbol),
                    default=0.0,
                )
        except Exception:
            pass

        try:
            q = self.market_data_service.get_quote(symbol)
            if isinstance(q, dict):
                return self._safe_num(
                    q.get(
                        "previous_close",
                        q.get("prev_close", q.get("pc", q.get("previousClose"))),
                    ),
                    default=0.0,
                )
        except Exception:
            pass

        return 0.0

    def _lookup_from_history_providers(self, symbol: str) -> tuple[float, float]:
        """
        Uses short history only as an Alpha UI fallback. This avoids the earlier
        issue where a latest-price lookup downloaded six months of history.
        """
        provider_funcs = []

        try:
            from modules.market_data.service import marketdata_history

            provider_funcs.append(("MARKETDATA", marketdata_history))
        except Exception:
            pass

        try:
            from modules.market_data.service import alpha_history

            provider_funcs.append(("ALPHA_VANTAGE", alpha_history))
        except Exception:
            pass

        for provider_name, fn in provider_funcs:
            try:
                df = fn(symbol, period="5d", interval="1d")
                latest, previous = self._extract_latest_previous_from_df(df)

                if latest > 0:
                    print(
                        f"ALPHA HISTORY FALLBACK {provider_name} "
                        f"{symbol} price={latest} prev={previous}"
                    )
                    return latest, previous

            except Exception as e:
                print(f"ALPHA HISTORY FALLBACK ERROR {provider_name} {symbol}: {e}")

        return 0.0, 0.0

    def _lookup_from_service_internal(self, symbol: str) -> float:
        try:
            from modules.market_data.service import get_latest_price_internal

            for provider in ("MARKETDATA", "ALPHA_VANTAGE", "FINNHUB"):
                price = get_latest_price_internal(
                    symbol,
                    provider_override=provider,
                )
                price = self._safe_num(price, default=0.0)

                if price > 0:
                    return price

        except Exception as e:
            print(f"ALPHA SERVICE INTERNAL FALLBACK ERROR {symbol}: {e}")

        return 0.0

    @staticmethod
    def _extract_latest_previous_from_df(df) -> tuple[float, float]:
        if df is None:
            return 0.0, 0.0

        if not isinstance(df, pd.DataFrame) or df.empty:
            return 0.0, 0.0

        close_col = None
        for candidate in ("Close", "close", "c", "adj_close", "Adj Close"):
            if candidate in df.columns:
                close_col = candidate
                break

        if not close_col:
            return 0.0, 0.0

        closes = pd.to_numeric(
            df[close_col],
            errors="coerce",
        ).dropna()

        closes = closes[closes > 0]

        if closes.empty:
            return 0.0, 0.0

        latest = float(closes.iloc[-1])
        previous = float(closes.iloc[-2]) if len(closes) >= 2 else latest

        return latest, previous

    @staticmethod
    def _extract_price_from_dict(q: dict) -> float:
        for key in (
            "price",
            "c",
            "last",
            "close",
            "latest_price",
            "latestPrice",
            "regularMarketPrice",
            "current_price",
        ):
            if key in q:
                value = q.get(key)
                try:
                    if value is not None and float(value) > 0:
                        return float(value)
                except Exception:
                    continue

        return 0.0

    @staticmethod
    def _safe_num(x, default: float = 0.0) -> float:
        try:
            if x is None:
                return default
            return float(x)
        except Exception:
            return default



    def _get_latest_snapshot(self, symbol: str) -> dict:

        if self.db is None:
            return {}

        row = self.db.execute(
            text("""
                SELECT *
                FROM analytics_snapshots
                WHERE symbol = :symbol
                ORDER BY asof DESC
                LIMIT 1
            """),
            {"symbol": symbol.upper()}
        ).mappings().first()

        return dict(row) if row else {}