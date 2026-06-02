"""
modules/agent/agent_engine.py

Agentic Portfolio Manager Engine.

Claude autonomously:
  1. Reads the strategy instruction ("growth tech stocks under $200")
  2. Pulls candidate stocks from the user's analytics universe
  3. Ranks and scores them using existing AI ranking infrastructure
  4. Decides which to buy, hold, or sell — with explicit reasoning
  5. Executes via OrderService (paper trading)
  6. Logs every decision to AgentActivityLog (the activity feed)
  7. Respects the kill switch at every step

Architecture:
  - AgentEngine.run_cycle() — one full decision + execution cycle
  - Claude is called once per cycle with full context; returns structured decisions
  - Each decision is stored in AgentDecision before execution
  - Each action is logged to AgentActivityLog with full reasoning
  - Kill switch checked before every trade
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import streamlit as st

from modules.agent.models import AgentPortfolio, AgentActivityLog, AgentDecision
from modules.db.core import Base


# ─────────────────────────────────────────────────────────────
# Claude client
# ─────────────────────────────────────────────────────────────

def _get_client():
    import anthropic
    key = (
        os.getenv("ANTHROPIC_API_KEY")
        or st.secrets.get("ANTHROPIC_API_KEY", "")
    )
    if not key:
        raise EnvironmentError("ANTHROPIC_API_KEY not set.")
    return anthropic.Anthropic(api_key=key)


# ─────────────────────────────────────────────────────────────
# Tool schema — structured portfolio decisions
# ─────────────────────────────────────────────────────────────

AGENT_TOOL = {
    "name": "submit_portfolio_decisions",
    "description": (
        "Submit the agent's portfolio decisions for this cycle. "
        "Each decision specifies what to do with a stock and exactly why."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "cycle_summary": {
                "type": "string",
                "description": (
                    "2-3 sentence summary of what the agent decided this cycle "
                    "and the key reasoning. This appears at the top of the activity feed."
                ),
            },
            "market_assessment": {
                "type": "string",
                "description": "1-2 sentences on current market conditions and how they affect the strategy.",
            },
            "decisions": {
                "type": "array",
                "description": "List of portfolio decisions — one per symbol.",
                "items": {
                    "type": "object",
                    "properties": {
                        "symbol":        {"type": "string"},
                        "action":        {"type": "string",
                                          "enum": ["BUY", "SELL", "HOLD", "SKIP"]},
                        "target_weight": {"type": "number",
                                          "description": "Target portfolio weight 0-100%."},
                        "confidence":    {"type": "number",
                                          "description": "Confidence 0-100."},
                        "reasoning":     {"type": "string",
                                          "description": (
                                              "Specific reasoning for this decision. "
                                              "Reference actual data — RSI, momentum, "
                                              "sector, composite score, news. "
                                              "2-3 sentences."
                                          )},
                        "risk_note":     {"type": "string",
                                          "description": "Key risk for this position. 1 sentence."},
                    },
                    "required": ["symbol", "action", "confidence", "reasoning"],
                },
            },
            "cash_target_pct": {
                "type": "number",
                "description": "Target cash reserve as % of budget. e.g. 5.0 for 5% cash.",
            },
            "rebalance_needed": {
                "type": "boolean",
                "description": "True if the agent recommends executing trades this cycle.",
            },
        },
        "required": ["cycle_summary", "decisions", "rebalance_needed"],
    },
}


# ─────────────────────────────────────────────────────────────
# Agent Engine
# ─────────────────────────────────────────────────────────────

class AgentEngine:
    """
    Core agentic portfolio manager.
    One instance per AgentPortfolio — call run_cycle() to execute one cycle.
    """

    def __init__(self, db, agent: AgentPortfolio):
        self.db    = db
        self.agent = agent

    def _log(
        self,
        event_type: str,
        reasoning: str,
        symbol: str = None,
        action: str = None,
        qty: float = None,
        price: float = None,
        notional: float = None,
        success: bool = True,
        error_message: str = None,
    ):
        """Write to AgentActivityLog."""
        entry = AgentActivityLog(
            agent_id=self.agent.id,
            tenant_id=self.agent.tenant_id,
            event_type=event_type,
            symbol=symbol,
            action=action,
            qty=qty,
            price=price,
            notional=notional,
            reasoning=reasoning,
            success=success,
            error_message=error_message,
        )
        try:
            self.db.add(entry)
            self.db.commit()
        except Exception as e:
            try:
                self.db.rollback()
            except Exception:
                pass
        return entry

    def _is_killed(self) -> bool:
        """Reload agent state and check kill switch."""
        try:
            self.db.refresh(self.agent)
        except Exception:
            pass
        return bool(self.agent.killed)

    def _get_cash_balance(self) -> float:
        """Get available cash in the agent's linked portfolio."""
        if not self.agent.portfolio_id:
            return self.agent.budget
        try:
            from modules.portfolio.accounting_service import AccountingService
            acct = AccountingService(self.db)
            return acct.cash_balance(self.agent.portfolio_id)
        except Exception:
            return self.agent.budget

    def _get_current_positions(self) -> dict:
        """Returns {symbol: {"qty": float, "avg_cost": float, "market_value": float}}"""
        if not self.agent.portfolio_id:
            return {}
        try:
            from sqlalchemy import text
            rows = self.db.execute(text("""
                SELECT symbol, qty, avg_cost, market_value
                FROM portfolio_positions
                WHERE portfolio_id = :pid
            """), {"pid": self.agent.portfolio_id}).mappings().fetchall()
            return {
                str(r["symbol"]).upper(): {
                    "qty":          float(r["qty"] or 0),
                    "avg_cost":     float(r["avg_cost"] or 0),
                    "market_value": float(r["market_value"] or 0),
                }
                for r in rows
            }
        except Exception:
            return {}

    def _get_universe_candidates(self) -> list[dict]:
        """Pull top candidates from analytics snapshots for the agent's universe."""
        try:
            from modules.analytics.models import AnalyticsSnapshot
            rows = (
                self.db.query(AnalyticsSnapshot)
                .filter(AnalyticsSnapshot.tenant_id == self.agent.tenant_id)
                .order_by(AnalyticsSnapshot.composite_score.desc())
                .limit(50)
                .all()
            )
            return [
                {
                    "symbol":    r.symbol,
                    "sector":    r.sector or "Unknown",
                    "rating":    r.rating or "N/A",
                    "composite": round(float(r.composite_score or 0), 1),
                    "momentum":  round(float(r.momentum_score or 0), 1),
                    "quality":   round(float(r.quality_score or 0), 1),
                    "risk":      round(float(r.risk_score or 0), 1),
                    "rsi_14":    round(float(r.rsi_14 or 0), 1),
                    "trend":     r.trend or "",
                    "signal":    r.signal or "",
                    "pe_ttm":    round(float(r.pe_ttm or 0), 1) if r.pe_ttm else None,
                }
                for r in rows
            ]
        except Exception as e:
            self._log("ERROR", f"Failed to load universe: {e}", success=False)
            return []

    def _get_live_prices(self, symbols: list[str]) -> dict:
        """Get current prices for a list of symbols."""
        prices = {}
        from modules.market_data.service import get_price_history
        for sym in symbols[:20]:   # cap to avoid rate limits
            try:
                self.db.rollback()
            except Exception:
                pass
            try:
                df = get_price_history(self.db, sym, period="5d", interval="1d")
                if df is not None and not df.empty and "Close" in df.columns:
                    prices[sym] = float(df["Close"].iloc[-1])
            except Exception:
                pass
        return prices

    def _build_context(
        self,
        candidates: list[dict],
        positions: dict,
        cash: float,
        prices: dict,
    ) -> dict:
        """Build the full context dict for Claude."""
        total_value = cash + sum(p["market_value"] for p in positions.values())

        # Enrich candidates with current prices
        for c in candidates:
            sym = c["symbol"]
            if sym in prices:
                c["current_price"] = round(prices[sym], 2)
            if sym in positions:
                pos = positions[sym]
                c["current_qty"]   = pos["qty"]
                c["current_weight"] = round(
                    pos["market_value"] / total_value * 100, 1
                ) if total_value else 0

        return {
            "strategy_instruction": self.agent.strategy_instruction,
            "budget":               self.agent.budget,
            "cash_available":       round(cash, 2),
            "total_portfolio_value":round(total_value, 2),
            "max_positions":        self.agent.max_positions,
            "risk_level":           self.agent.risk_level,
            "current_positions":    [
                {
                    "symbol":         sym,
                    "qty":            pos["qty"],
                    "avg_cost":       pos["avg_cost"],
                    "market_value":   pos["market_value"],
                    "current_price":  prices.get(sym),
                    "weight_pct":     round(pos["market_value"] / total_value * 100, 1) if total_value else 0,
                }
                for sym, pos in positions.items()
            ],
            "universe_candidates":  candidates[:30],
            "date":                 datetime.now(timezone.utc).strftime("%B %d, %Y"),
        }

    def run_cycle(self) -> dict:
        """
        Execute one full agent cycle:
          1. Check kill switch
          2. Load universe + positions + cash
          3. Call Claude for decisions
          4. Execute approved trades via OrderService
          5. Log everything

        Returns dict with cycle results.
        """
        cycle_id = str(uuid.uuid4())[:8]

        # ── Kill switch check ─────────────────────────────────
        if self._is_killed():
            self._log("KILL_SWITCH", "Agent is halted. Cycle aborted.")
            return {"status": "killed", "trades": 0}

        self._log(
            "CYCLE_START",
            f"Starting agent cycle #{self.agent.run_count + 1}. "
            f"Strategy: '{self.agent.strategy_instruction}'. "
            f"Budget: ${self.agent.budget:,.0f}."
        )

        # ── Load data ─────────────────────────────────────────
        candidates = self._get_universe_candidates()
        if not candidates:
            self._log("INFO", "No universe candidates found. Skipping cycle.",
                      success=False)
            return {"status": "no_data", "trades": 0}

        positions = self._get_current_positions()
        cash      = self._get_cash_balance()

        # Get prices for current positions + top candidates
        syms_needed = list(positions.keys()) + [c["symbol"] for c in candidates[:15]]
        prices      = self._get_live_prices(list(set(syms_needed)))

        self._log(
            "ANALYSIS",
            f"Loaded {len(candidates)} universe candidates, "
            f"{len(positions)} current positions, "
            f"${cash:,.2f} cash available. "
            f"Calling Claude for portfolio decisions."
        )

        # ── Claude decision call ───────────────────────────────
        ctx = self._build_context(candidates, positions, cash, prices)

        try:
            client = _get_client()
        except Exception as e:
            self._log("ERROR", f"Anthropic API unavailable: {e}", success=False)
            return {"status": "api_error", "trades": 0}

        system = (
            "You are an autonomous portfolio manager AI. "
            "Your job is to construct and manage a portfolio within the given budget "
            "according to the strategy instruction. "
            "Be specific in your reasoning — reference actual scores, prices, and data. "
            "Be disciplined: don't overtrade, maintain diversification, "
            "respect position sizing, and always keep some cash reserve. "
            "You must call submit_portfolio_decisions with your analysis."
        )

        user_msg = (
            f"Manage this portfolio for one cycle.\n\n"
            f"Strategy: \"{self.agent.strategy_instruction}\"\n"
            f"Risk level: {self.agent.risk_level}\n"
            f"Max positions: {self.agent.max_positions}\n\n"
            f"Full context:\n{json.dumps(ctx, indent=2, default=str)}\n\n"
            f"Instructions:\n"
            f"- Review current positions and top universe candidates\n"
            f"- Decide which positions to BUY, SELL, HOLD, or SKIP\n"
            f"- Target weights should sum to ~{100 - 5:.0f}% (keep ~5% cash)\n"
            f"- Only recommend trades that fit the strategy instruction\n"
            f"- Provide specific reasoning for each decision referencing the data\n"
            f"- Set rebalance_needed=true only if you recommend actual trades\n"
        )

        try:
            message = client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=2000,
                system=system,
                tools=[AGENT_TOOL],
                tool_choice={"type": "tool", "name": "submit_portfolio_decisions"},
                messages=[{"role": "user", "content": user_msg}],
            )
        except Exception as e:
            self._log("ERROR", f"Claude API call failed: {e}", success=False)
            return {"status": "api_error", "trades": 0}

        # Parse response
        agent_plan = None
        for block in message.content:
            if block.type == "tool_use" and block.name == "submit_portfolio_decisions":
                agent_plan = block.input
                break

        if not agent_plan:
            self._log("ERROR", "No decisions returned from Claude.", success=False)
            return {"status": "no_plan", "trades": 0}

        # Log the cycle summary
        self._log(
            "DECISION",
            agent_plan.get("cycle_summary", "Agent completed analysis."),
        )
        if agent_plan.get("market_assessment"):
            self._log("INFO", f"Market: {agent_plan['market_assessment']}")

        # ── Execute decisions ─────────────────────────────────
        if not agent_plan.get("rebalance_needed", False):
            self._log(
                "INFO",
                "Agent determined no trades needed this cycle. Portfolio is aligned with strategy."
            )
            self._update_agent_stats(0)
            return {"status": "no_trades_needed", "trades": 0, "decisions": agent_plan["decisions"]}

        trades_executed = 0
        decisions       = agent_plan.get("decisions", [])

        for decision in decisions:
            if self._is_killed():
                self._log("KILL_SWITCH", "Kill switch activated mid-cycle. Stopping execution.")
                break

            sym    = str(decision.get("symbol", "")).upper()
            action = str(decision.get("action", "HOLD")).upper()
            weight = float(decision.get("target_weight") or 0)
            conf   = float(decision.get("confidence") or 50)
            reason = str(decision.get("reasoning", ""))
            risk_n = str(decision.get("risk_note", ""))

            if not sym or action in ("HOLD", "SKIP"):
                self._log(
                    "TRADE_SKIPPED",
                    f"{sym}: {action} — {reason}",
                    symbol=sym, action=action,
                )
                continue

            # Store decision record
            total_val = float(ctx.get("total_portfolio_value") or self.agent.budget)
            target_notional = (weight / 100) * total_val
            price = prices.get(sym)
            target_qty = round(target_notional / price, 4) if price and price > 0 else 0

            current_qty = positions.get(sym, {}).get("qty", 0)
            trade_qty   = 0

            if action == "BUY":
                trade_qty = max(0, target_qty - current_qty)
            elif action == "SELL":
                trade_qty = min(current_qty, current_qty - target_qty)
                trade_qty = max(0, trade_qty)

            if trade_qty < 0.01:
                self._log(
                    "TRADE_SKIPPED",
                    f"{sym}: {action} — qty {trade_qty:.4f} too small to execute. {reason}",
                    symbol=sym, action=action,
                )
                continue

            # Save decision to DB
            dec_record = AgentDecision(
                agent_id=self.agent.id,
                cycle_id=cycle_id,
                symbol=sym,
                action=action,
                target_weight=weight,
                target_qty=target_qty,
                current_qty=current_qty,
                price=price,
                notional=round(trade_qty * (price or 0), 2),
                confidence=conf,
                reasoning=reason,
            )
            try:
                self.db.add(dec_record)
                self.db.commit()
            except Exception:
                try:
                    self.db.rollback()
                except Exception:
                    pass

            # Execute via OrderService
            if not self.agent.portfolio_id:
                self._log(
                    "TRADE_SKIPPED",
                    f"{sym}: No linked portfolio. Cannot execute.",
                    symbol=sym, action=action,
                )
                continue

            try:
                from modules.portfolio.order_service import OrderService
                svc = OrderService(self.db)
                order = svc.submit_order(
                    portfolio_id=self.agent.portfolio_id,
                    user_id=self.agent.user_id,
                    symbol=sym,
                    side=action.lower(),
                    qty=trade_qty,
                    order_type="market",
                )

                notional = round(trade_qty * (price or 0), 2)
                self._log(
                    "TRADE_EXECUTED",
                    f"{action} {trade_qty:.2f} shares of {sym} at ~${price:.2f} "
                    f"(${notional:,.2f}). {reason}"
                    + (f" Risk: {risk_n}" if risk_n else ""),
                    symbol=sym, action=action,
                    qty=trade_qty, price=price, notional=notional,
                )

                # Mark decision executed
                try:
                    dec_record.executed = True
                    self.db.commit()
                except Exception:
                    try:
                        self.db.rollback()
                    except Exception:
                        pass

                trades_executed += 1

            except Exception as e:
                self._log(
                    "TRADE_SKIPPED",
                    f"{sym}: Execution failed — {e}. {reason}",
                    symbol=sym, action=action,
                    success=False, error_message=str(e),
                )
                try:
                    dec_record.executed = False
                    dec_record.execution_error = str(e)
                    self.db.commit()
                except Exception:
                    try:
                        self.db.rollback()
                    except Exception:
                        pass

        self._update_agent_stats(trades_executed)

        self._log(
            "CYCLE_START",
            f"Cycle complete. {trades_executed} trade(s) executed.",
        )

        return {
            "status":    "completed",
            "trades":    trades_executed,
            "decisions": decisions,
            "summary":   agent_plan.get("cycle_summary", ""),
        }

    def _update_agent_stats(self, trades: int):
        try:
            self.agent.last_run     = datetime.now(timezone.utc)
            self.agent.run_count    = (self.agent.run_count or 0) + 1
            self.agent.total_trades = (self.agent.total_trades or 0) + trades
            self.db.commit()
        except Exception:
            try:
                self.db.rollback()
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────
# DB helpers
# ─────────────────────────────────────────────────────────────

def ensure_tables(db):
    """Create agent tables if they don't exist."""
    try:
        from modules.db.core import engine as _engine
        AgentPortfolio.__table__.create(bind=_engine, checkfirst=True)
        AgentActivityLog.__table__.create(bind=_engine, checkfirst=True)
        AgentDecision.__table__.create(bind=_engine, checkfirst=True)
    except Exception as e:
        print(f"[agent] table create: {e}")


def list_agents(db, tenant_id: str) -> list[AgentPortfolio]:
    try:
        return (
            db.query(AgentPortfolio)
            .filter(AgentPortfolio.tenant_id == tenant_id)
            .order_by(AgentPortfolio.created_at.desc())
            .all()
        )
    except Exception:
        return []


def get_activity_log(
    db,
    agent_id: str,
    limit: int = 100,
) -> list[AgentActivityLog]:
    try:
        return (
            db.query(AgentActivityLog)
            .filter(AgentActivityLog.agent_id == agent_id)
            .order_by(AgentActivityLog.created_at.desc())
            .limit(limit)
            .all()
        )
    except Exception:
        return []


def create_agent_portfolio(
    db,
    tenant_id: str,
    user_id: str,
    name: str,
    strategy_instruction: str,
    budget: float,
    max_positions: int,
    risk_level: str,
    linked_portfolio_id: str = None,
) -> AgentPortfolio:
    agent = AgentPortfolio(
        tenant_id=tenant_id,
        user_id=user_id,
        name=name,
        strategy_instruction=strategy_instruction,
        budget=budget,
        max_positions=max_positions,
        risk_level=risk_level,
        portfolio_id=linked_portfolio_id,
        active=True,
        killed=False,
    )
    db.add(agent)
    db.commit()
    return agent


def kill_agent(db, agent_id: str, tenant_id: str, reason: str = "User activated kill switch"):
    try:
        agent = (
            db.query(AgentPortfolio)
            .filter(AgentPortfolio.id == agent_id,
                    AgentPortfolio.tenant_id == tenant_id)
            .first()
        )
        if agent:
            agent.killed      = True
            agent.active      = False
            agent.kill_reason = reason
            db.commit()

            log = AgentActivityLog(
                agent_id=agent_id,
                tenant_id=tenant_id,
                event_type="KILL_SWITCH",
                reasoning=f"🛑 KILL SWITCH ACTIVATED: {reason}",
                success=True,
            )
            db.add(log)
            db.commit()
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass


def revive_agent(db, agent_id: str, tenant_id: str):
    try:
        agent = (
            db.query(AgentPortfolio)
            .filter(AgentPortfolio.id == agent_id,
                    AgentPortfolio.tenant_id == tenant_id)
            .first()
        )
        if agent:
            agent.killed      = False
            agent.active      = True
            agent.kill_reason = None
            db.commit()
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass