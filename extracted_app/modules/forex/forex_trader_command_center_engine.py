# modules/forex/forex_trader_command_center_engine.py

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_PAIRS = [
    "EUR/USD",
    "GBP/USD",
    "USD/JPY",
    "USD/CHF",
    "AUD/USD",
    "NZD/USD",
    "USD/CAD",
    "EUR/JPY",
    "GBP/JPY",
    "AUD/JPY",
    "EUR/GBP",
    "EUR/CHF",
]


MAJOR_CURRENCIES = [
    "USD",
    "EUR",
    "GBP",
    "JPY",
    "CHF",
    "AUD",
    "CAD",
    "NZD",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        result = float(value)
        if result != result:
            return default
        return result
    except Exception:
        return default


def _round(value: Any, places: int = 2) -> float:
    return round(_safe_float(value), places)


def _safe_dict(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "to_dict"):
        try:
            return value.to_dict()
        except Exception:
            pass
    try:
        return asdict(value)
    except Exception:
        return {}


def _safe_list(value: Any) -> List[Dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, list):
        return [_safe_dict(item) if not isinstance(item, dict) else item for item in value]
    if hasattr(value, "to_dict"):
        value = value.to_dict()
    if isinstance(value, dict):
        for key in (
            "recommendations",
            "snapshots",
            "signals",
            "allocations",
            "events",
            "positions",
            "orders",
            "history",
        ):
            if isinstance(value.get(key), list):
                return [_safe_dict(item) if not isinstance(item, dict) else item for item in value[key]]
    return []


def _import_optional(path: str, name: str):
    try:
        module = __import__(path, fromlist=[name])
        return getattr(module, name)
    except Exception:
        return None


def _split_pair(pair: str) -> Tuple[str, str]:
    text = str(pair or "").upper().replace("-", "/").replace("_", "/")
    if "/" in text:
        left, right = text.split("/", 1)
        return left[:3], right[:3]
    if len(text) >= 6:
        return text[:3], text[3:6]
    return text[:3], ""


class ForexTraderCommandCenterEngine:
    """
    Trader-facing Forex command center aggregator.

    This engine reuses the existing Forex subsystem:
    - ForexService
    - Currency Strength
    - Regime Detection
    - Macro Regime
    - Recommendations
    - Institutional Scanner
    - Carry Trade
    - Central Banks
    - Portfolio Optimizer

    It intentionally returns a UI-ready dictionary so the Streamlit dashboard can
    render even when a specific lower-level engine is unavailable.
    """

    def __init__(self) -> None:
        self.generated_at = _utc_now()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_dashboard(
        self,
        pairs: Optional[List[str]] = None,
        *,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        save: bool = False,
    ) -> Dict[str, Any]:
        selected_pairs = pairs or DEFAULT_PAIRS

        market = self.market_regime(selected_pairs, save=save)
        strength = self.currency_strength(selected_pairs, save=save)
        opportunities = self.top_opportunities(
            selected_pairs,
            account_id=account_id,
            save=save,
        )
        institutional = self.institutional_flow(selected_pairs, save=save)
        carry = self.carry_trades(selected_pairs, save=save)
        central_banks = self.central_banks(selected_pairs, save=save)
        events = self.upcoming_events()
        ai = self.ai_recommendation_engine(opportunities)
        portfolio = self.portfolio_snapshot(
            selected_pairs,
            portfolio_id=portfolio_id,
            save=save,
        )
        paper = self.paper_trading_snapshot()

        return {
            "status": "success",
            "generated_at": _utc_now(),
            "pairs": selected_pairs,
            "market_regime": market,
            "currency_strength": strength,
            "top_opportunities": opportunities,
            "institutional_flow": institutional,
            "carry_trades": carry,
            "central_banks": central_banks,
            "upcoming_events": events,
            "ai_recommendation": ai,
            "portfolio": portfolio,
            "paper_trading": paper,
            "warnings": self._collect_warnings(
                [
                    market,
                    strength,
                    {"rows": opportunities},
                    institutional,
                    carry,
                    central_banks,
                    events,
                    ai,
                    portfolio,
                    paper,
                ]
            ),
        }

    # ------------------------------------------------------------------
    # Sections
    # ------------------------------------------------------------------

    def market_regime(
        self,
        pairs: List[str],
        *,
        save: bool = False,
    ) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "risk_regime": "NEUTRAL",
            "risk_label": "Neutral",
            "usd_strength": 50.0,
            "volatility": "Medium",
            "liquidity": "Normal",
            "macro_score": 50.0,
            "confidence": 50.0,
            "rows": [],
            "source": "fallback",
        }

        macro_engine_cls = _import_optional(
            "modules.forex.forex_macro_regime_engine",
            "get_forex_macro_regime_engine",
        )
        regime_engine_cls = _import_optional(
            "modules.forex.forex_regime_detection_engine",
            "get_forex_regime_detection_engine",
        )

        rows: List[Dict[str, Any]] = []

        try:
            if macro_engine_cls is not None:
                scan = macro_engine_cls().scan_pairs(pairs=pairs, save=save)
                scan_dict = _safe_dict(scan)
                rows = _safe_list(scan_dict)
                result["macro_score"] = _round(scan_dict.get("average_regime_score", 50.0))
                result["confidence"] = _round(scan_dict.get("average_confidence", 50.0))
                result["source"] = "forex_macro_regime_engine"

                expansion = int(scan_dict.get("expansion_count", 0) or 0)
                contraction = int(scan_dict.get("contraction_count", 0) or 0)
                inflationary = int(scan_dict.get("inflationary_count", 0) or 0)

                if contraction > expansion:
                    result["risk_regime"] = "RISK_OFF"
                    result["risk_label"] = "Risk Off"
                elif expansion >= contraction and expansion > 0:
                    result["risk_regime"] = "RISK_ON"
                    result["risk_label"] = "Risk On"
                elif inflationary > 0:
                    result["risk_regime"] = "INFLATIONARY"
                    result["risk_label"] = "Inflationary"
        except Exception as exc:
            result["warning"] = f"Macro regime unavailable: {exc}"

        try:
            if regime_engine_cls is not None:
                scan = regime_engine_cls().scan_pairs(pairs=pairs, save=save)
                scan_dict = _safe_dict(scan)
                regime_rows = _safe_list(scan_dict)
                if not rows:
                    rows = regime_rows
                avg_conf = scan_dict.get("average_confidence")
                if avg_conf is not None:
                    result["confidence"] = _round(avg_conf)
                risk_off = int(scan_dict.get("risk_off_count", 0) or 0)
                trending = int(scan_dict.get("trending_count", 0) or 0)
                breakout = int(scan_dict.get("breakout_count", 0) or 0)
                if risk_off > 0 and risk_off >= trending:
                    result["risk_regime"] = "RISK_OFF"
                    result["risk_label"] = "Risk Off"
                elif trending + breakout > 0:
                    result["volatility"] = "Elevated" if breakout else "Medium"
        except Exception as exc:
            result.setdefault("warning", f"Regime detection unavailable: {exc}")

        result["rows"] = rows[:12]
        return result

    def currency_strength(
        self,
        pairs: List[str],
        *,
        save: bool = False,
    ) -> Dict[str, Any]:
        rows: List[Dict[str, Any]] = []
        warning = None

        getter = _import_optional(
            "modules.forex.forex_currency_strength_engine",
            "get_forex_currency_strength_engine",
        )

        try:
            if getter is not None:
                scan = getter().scan_currencies(currencies=MAJOR_CURRENCIES, pairs=pairs, save=save)
                scan_dict = _safe_dict(scan)
                rows = _safe_list(scan_dict)
        except TypeError:
            try:
                scan = getter().scan_currencies(save=save)
                rows = _safe_list(scan)
            except Exception as exc:
                warning = str(exc)
        except Exception as exc:
            warning = str(exc)

        if not rows:
            rows = self._fallback_currency_strength(pairs)

        normalized = []
        for row in rows:
            currency = row.get("currency") or row.get("base_currency") or row.get("symbol")
            if not currency:
                continue
            score = (
                row.get("composite_strength_score")
                or row.get("strength_score")
                or row.get("relative_strength_score")
                or row.get("score")
                or row.get("confidence_score")
                or 50.0
            )
            normalized.append(
                {
                    "currency": str(currency).upper()[:3],
                    "score": _round(score),
                    "trend": row.get("strength_regime") or row.get("signal") or row.get("trend") or "NEUTRAL",
                    "confidence": _round(row.get("confidence_score", score)),
                }
            )

        normalized = sorted(
            {row["currency"]: row for row in normalized}.values(),
            key=lambda item: item["score"],
            reverse=True,
        )

        return {
            "status": "success",
            "source": "forex_currency_strength_engine" if warning is None else "fallback",
            "warning": warning,
            "strongest": normalized[0] if normalized else None,
            "weakest": normalized[-1] if normalized else None,
            "rows": normalized,
        }

    def top_opportunities(
        self,
        pairs: List[str],
        *,
        account_id: Optional[str] = None,
        save: bool = False,
        limit: int = 8,
    ) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        getter = _import_optional(
            "modules.forex.forex_recommendation_engine",
            "get_forex_recommendation_engine",
        )

        try:
            if getter is not None:
                recs = getter().get_top_recommendations(
                    pairs=pairs,
                    account_id=account_id,
                    limit=limit,
                    save=save,
                )
                rows = _safe_list(recs)
        except Exception:
            rows = []

        if not rows:
            alpha_getter = _import_optional(
                "modules.forex.forex_alpha_model",
                "get_forex_alpha_model",
            )
            try:
                if alpha_getter is not None:
                    run = alpha_getter().run_alpha_model(pairs=pairs, save=save)
                    run_rows = _safe_list(_safe_dict(run))
                    for row in run_rows[:limit]:
                        pair = row.get("pair")
                        bias = str(row.get("position_bias", "WATCH")).upper()
                        score = _safe_float(row.get("alpha_score", row.get("conviction_score", 50.0)))
                        rows.append(
                            {
                                "pair": pair,
                                "recommendation": "BUY" if "LONG" in bias else "SELL" if "SHORT" in bias else "WATCH",
                                "signal": row.get("signal") or row.get("alpha_signal") or bias,
                                "conviction_score": score,
                                "confidence_score": row.get("confidence_score", score),
                                "risk_reward": row.get("risk_reward", 2.0),
                                "entry_price": row.get("entry_price", 0.0),
                                "stop_price": row.get("stop_price", 0.0),
                                "target_price": row.get("target_price", 0.0),
                                "rationale": row.get("rationale", ""),
                                "warnings": row.get("warnings", ""),
                            }
                        )
            except Exception:
                pass

        if not rows:
            rows = self._fallback_opportunities(pairs)

        normalized = []
        for row in rows:
            pair = row.get("pair") or row.get("symbol")
            if not pair:
                continue
            rec = str(row.get("recommendation") or row.get("signal") or "WATCH").upper()
            conviction = _round(row.get("conviction_score", row.get("composite_score", row.get("alpha_score", 50.0))))
            confidence = _round(row.get("confidence_score", conviction))
            rr = _round(row.get("risk_reward", 2.0))
            normalized.append(
                {
                    "pair": pair,
                    "recommendation": rec,
                    "signal": row.get("signal", rec),
                    "conviction_score": conviction,
                    "confidence_score": confidence,
                    "risk_reward": rr,
                    "entry_price": _round(row.get("entry_price", row.get("current_price", 0.0)), 5),
                    "stop_price": _round(row.get("stop_price", 0.0), 5),
                    "target_price": _round(row.get("target_price", 0.0), 5),
                    "rationale": row.get("rationale", ""),
                    "warnings": row.get("warnings", ""),
                    "status": row.get("status", "active"),
                }
            )

        return sorted(
            normalized,
            key=lambda item: (
                item.get("conviction_score", 0),
                item.get("confidence_score", 0),
                item.get("risk_reward", 0),
            ),
            reverse=True,
        )[:limit]

    def institutional_flow(
        self,
        pairs: List[str],
        *,
        save: bool = False,
    ) -> Dict[str, Any]:
        getter = _import_optional(
            "modules.forex.forex_institutional_scanner",
            "get_forex_institutional_scanner",
        )
        rows: List[Dict[str, Any]] = []
        warning = None

        try:
            if getter is not None:
                scan = getter().scan_pairs(pairs=pairs, save=save)
                rows = _safe_list(_safe_dict(scan))
                scan_dict = _safe_dict(scan)
                return {
                    "status": "success",
                    "source": "forex_institutional_scanner",
                    "smart_money_bias": scan_dict.get("top_signal", "WATCH"),
                    "top_pair": scan_dict.get("top_pair"),
                    "average_score": _round(scan_dict.get("average_institutional_score", 50.0)),
                    "average_confidence": _round(scan_dict.get("average_confidence", 50.0)),
                    "long_count": scan_dict.get("institutional_long_count", 0),
                    "short_count": scan_dict.get("institutional_short_count", 0),
                    "watch_count": scan_dict.get("watch_count", 0),
                    "rows": rows[:10],
                }
        except Exception as exc:
            warning = str(exc)

        return {
            "status": "fallback",
            "source": "fallback",
            "warning": warning,
            "smart_money_bias": "Neutral",
            "top_pair": pairs[0] if pairs else None,
            "average_score": 50.0,
            "average_confidence": 50.0,
            "long_count": 0,
            "short_count": 0,
            "watch_count": len(pairs),
            "rows": [],
        }

    def carry_trades(
        self,
        pairs: List[str],
        *,
        save: bool = False,
    ) -> Dict[str, Any]:
        getter = _import_optional(
            "modules.forex.forex_carry_trade_engine",
            "get_forex_carry_trade_engine",
        )
        rows: List[Dict[str, Any]] = []
        warning = None

        try:
            if getter is not None:
                scan = getter().scan_pairs(pairs=pairs, save=save)
                scan_dict = _safe_dict(scan)
                rows = _safe_list(scan_dict)
                rows = sorted(
                    rows,
                    key=lambda item: _safe_float(item.get("carry_score", item.get("expected_carry_return", 0.0))),
                    reverse=True,
                )
                highest = rows[0] if rows else {}
                lowest = rows[-1] if rows else {}
                return {
                    "status": "success",
                    "source": "forex_carry_trade_engine",
                    "highest_yield": highest.get("pair"),
                    "lowest_yield": lowest.get("pair"),
                    "funding_currency": _split_pair(lowest.get("pair", ""))[0] if lowest else None,
                    "expected_return": _round(highest.get("expected_carry_return", 0.0)),
                    "average_carry_score": _round(scan_dict.get("average_carry_score", 0.0)),
                    "attractive_count": scan_dict.get("attractive_count", 0),
                    "rows": rows[:10],
                }
        except Exception as exc:
            warning = str(exc)

        return {
            "status": "fallback",
            "source": "fallback",
            "warning": warning,
            "highest_yield": "GBP/JPY",
            "lowest_yield": "EUR/CHF",
            "funding_currency": "JPY",
            "expected_return": 0.0,
            "average_carry_score": 50.0,
            "attractive_count": 0,
            "rows": [],
        }

    def central_banks(
        self,
        pairs: List[str],
        *,
        save: bool = False,
    ) -> Dict[str, Any]:
        getter = _import_optional(
            "modules.forex.forex_central_bank_engine",
            "get_forex_central_bank_engine",
        )
        rows: List[Dict[str, Any]] = []
        warning = None

        try:
            if getter is not None:
                scan = getter().scan_pairs(pairs=pairs, save=save)
                scan_dict = _safe_dict(scan)
                rows = _safe_list(scan_dict)
        except Exception as exc:
            warning = str(exc)

        bank_map = {}
        for row in rows:
            for side in ("base", "quote"):
                currency = row.get(f"{side}_currency")
                bank = row.get(f"{side}_bank")
                rate = row.get(f"{side}_rate")
                hawkish = row.get(f"{side}_hawkish_score")
                if currency and currency not in bank_map:
                    bank_map[currency] = {
                        "currency": currency,
                        "bank": bank,
                        "rate": _round(rate),
                        "hawkish_score": _round(hawkish),
                    }

        if not bank_map:
            bank_map = {
                "USD": {"currency": "USD", "bank": "Federal Reserve", "rate": 5.25, "hawkish_score": 75.0},
                "EUR": {"currency": "EUR", "bank": "European Central Bank", "rate": 3.75, "hawkish_score": 55.0},
                "GBP": {"currency": "GBP", "bank": "Bank of England", "rate": 5.00, "hawkish_score": 70.0},
                "JPY": {"currency": "JPY", "bank": "Bank of Japan", "rate": 0.25, "hawkish_score": 20.0},
                "CHF": {"currency": "CHF", "bank": "Swiss National Bank", "rate": 1.50, "hawkish_score": 45.0},
                "AUD": {"currency": "AUD", "bank": "Reserve Bank of Australia", "rate": 4.35, "hawkish_score": 62.0},
                "CAD": {"currency": "CAD", "bank": "Bank of Canada", "rate": 4.75, "hawkish_score": 58.0},
                "NZD": {"currency": "NZD", "bank": "Reserve Bank of New Zealand", "rate": 5.50, "hawkish_score": 68.0},
            }

        return {
            "status": "success" if warning is None else "fallback",
            "source": "forex_central_bank_engine" if warning is None else "fallback",
            "warning": warning,
            "rows": list(bank_map.values()),
            "pair_rows": rows[:10],
        }

    def upcoming_events(self) -> Dict[str, Any]:
        events = [
            {"date": "Today", "event": "CPI", "currency": "USD", "impact": "High"},
            {"date": "Today", "event": "Fed Speaker", "currency": "USD", "impact": "Medium"},
            {"date": "Tomorrow", "event": "PMI", "currency": "EUR", "impact": "Medium"},
            {"date": "Tomorrow", "event": "GDP", "currency": "GBP", "impact": "Medium"},
            {"date": "Friday", "event": "NFP", "currency": "USD", "impact": "High"},
        ]
        return {
            "status": "success",
            "source": "economic_calendar_placeholder",
            "rows": events,
        }

    def ai_recommendation_engine(
        self,
        opportunities: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        best = opportunities[0] if opportunities else {}
        return {
            "status": "success" if best else "empty",
            "best_trade": best.get("pair"),
            "recommendation": best.get("recommendation"),
            "confidence": best.get("confidence_score", 0.0),
            "conviction": best.get("conviction_score", 0.0),
            "entry": best.get("entry_price", 0.0),
            "stop": best.get("stop_price", 0.0),
            "target": best.get("target_price", 0.0),
            "risk_reward": best.get("risk_reward", 0.0),
            "rationale": best.get("rationale", ""),
            "warnings": best.get("warnings", ""),
        }

    def portfolio_snapshot(
        self,
        pairs: List[str],
        *,
        portfolio_id: Optional[str] = None,
        save: bool = False,
    ) -> Dict[str, Any]:
        getter = _import_optional(
            "modules.forex.forex_portfolio_optimizer",
            "get_forex_portfolio_optimizer",
        )
        try:
            if getter is not None:
                run = getter().optimize_portfolio(pairs=pairs, save=save)
                run_dict = _safe_dict(run)
                return {
                    "status": run_dict.get("optimization_status", "success"),
                    "portfolio_id": portfolio_id,
                    "open_trades": 0,
                    "exposure": _round(run_dict.get("total_target_weight", 0.0)),
                    "pnl": 0.0,
                    "currency_allocation": run_dict.get("allocations", []),
                    "risk_score": _round(run_dict.get("portfolio_risk_score", 0.0)),
                    "diversification_score": _round(run_dict.get("diversification_score", 0.0)),
                    "rows": _safe_list(run_dict),
                }
        except Exception as exc:
            return {
                "status": "fallback",
                "warning": str(exc),
                "portfolio_id": portfolio_id,
                "open_trades": 0,
                "exposure": 0.0,
                "pnl": 0.0,
                "currency_allocation": [],
                "risk_score": 0.0,
                "diversification_score": 0.0,
                "rows": [],
            }

        return {
            "status": "fallback",
            "portfolio_id": portfolio_id,
            "open_trades": 0,
            "exposure": 0.0,
            "pnl": 0.0,
            "currency_allocation": [],
            "risk_score": 0.0,
            "diversification_score": 0.0,
            "rows": [],
        }

    def paper_trading_snapshot(self) -> Dict[str, Any]:
        return {
            "status": "ready",
            "orders": 0,
            "positions": 0,
            "history": 0,
            "performance": {
                "win_rate": 0.0,
                "daily_pnl": 0.0,
                "monthly_pnl": 0.0,
            },
            "message": "Wire this section to the Forex paper broker / portfolio trade_orders tables when ready.",
        }

    # ------------------------------------------------------------------
    # Internal fallbacks
    # ------------------------------------------------------------------

    def _fallback_currency_strength(self, pairs: List[str]) -> List[Dict[str, Any]]:
        scores = {currency: 50.0 for currency in MAJOR_CURRENCIES}
        for pair in pairs:
            base, quote = _split_pair(pair)
            if base in scores:
                scores[base] += 2.5
            if quote in scores:
                scores[quote] -= 1.5
        return [
            {
                "currency": currency,
                "strength_score": max(0.0, min(100.0, score)),
                "confidence_score": 50.0,
                "trend": "NEUTRAL",
            }
            for currency, score in scores.items()
        ]

    def _fallback_opportunities(self, pairs: List[str]) -> List[Dict[str, Any]]:
        rows = []
        for index, pair in enumerate(pairs[:8]):
            direction = "BUY" if index % 2 == 0 else "SELL"
            score = max(50.0, 82.0 - index * 3.0)
            rows.append(
                {
                    "pair": pair,
                    "recommendation": direction,
                    "signal": f"{direction}_SETUP",
                    "conviction_score": score,
                    "confidence_score": max(45.0, score - 4.0),
                    "risk_reward": max(1.2, 3.2 - index * 0.2),
                    "entry_price": 0.0,
                    "stop_price": 0.0,
                    "target_price": 0.0,
                    "rationale": "Fallback opportunity generated because recommendation engine was unavailable.",
                    "warnings": "Use only after live data/recommendation engine validation.",
                    "status": "fallback",
                }
            )
        return rows

    def _collect_warnings(self, sections: List[Dict[str, Any]]) -> List[str]:
        warnings: List[str] = []
        for section in sections:
            if not isinstance(section, dict):
                continue
            warning = section.get("warning")
            if warning:
                warnings.append(str(warning))
            for row in section.get("rows", []) or []:
                if isinstance(row, dict) and row.get("warning"):
                    warnings.append(str(row["warning"]))
        return warnings


_COMMAND_CENTER_ENGINE: Optional[ForexTraderCommandCenterEngine] = None


def get_forex_trader_command_center_engine() -> ForexTraderCommandCenterEngine:
    global _COMMAND_CENTER_ENGINE
    if _COMMAND_CENTER_ENGINE is None:
        _COMMAND_CENTER_ENGINE = ForexTraderCommandCenterEngine()
    return _COMMAND_CENTER_ENGINE
