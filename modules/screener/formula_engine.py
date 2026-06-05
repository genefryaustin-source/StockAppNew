"""
modules/screener/formula_engine.py

Custom Formula Builder — define screening metrics with math expressions.

Architecture:
  - User writes formulas like: FCF_Yield = fcf_margin / pe_ttm * 100
  - Engine parses, validates, and evaluates safely (no eval/exec on user input)
  - Computed columns are added to screener results
  - Users can filter, sort, and screen on custom metrics
  - Formulas are saved per-user and shared with team via screener presets

Safety: Uses AST-based expression evaluator — no exec/eval on raw user input.
Only math operations and whitelisted field names are permitted.

Available base fields (from analytics_snapshot + price_history):
  price, volume, market_cap (computed: price * shares approx)
  pe_ttm, ps_ttm, ev_ebitda
  gross_margin, operating_margin, fcf_margin, revenue_cagr
  composite, quality, growth, value, momentum, risk, confidence
  rsi_14, support, resistance
  sector (string — not usable in math formulas)
"""
from __future__ import annotations

import ast
import json
import math
import operator
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd

# ─────────────────────────────────────────────────────────────
# Safe expression evaluator (AST-based, no eval)
# ─────────────────────────────────────────────────────────────

_SAFE_OPS = {
    ast.Add:  operator.add,
    ast.Sub:  operator.sub,
    ast.Mult: operator.mul,
    ast.Div:  operator.truediv,
    ast.Pow:  operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
    ast.Mod:  operator.mod,
}

_SAFE_FUNCS = {
    "abs":   abs,
    "min":   min,
    "max":   max,
    "round": round,
    "sqrt":  math.sqrt,
    "log":   math.log,
    "log10": math.log10,
    "exp":   math.exp,
    "floor": math.floor,
    "ceil":  math.ceil,
    "sign":  lambda x: 1 if x > 0 else (-1 if x < 0 else 0),
}

# All numeric fields available from screener results + analytics snapshot
AVAILABLE_FIELDS = {
    # Prices & volume
    "price":          "Current stock price ($)",
    "volume":         "Average 20-day volume",
    # Valuation
    "pe_ttm":         "Price/Earnings TTM",
    "ps_ttm":         "Price/Sales TTM",
    "ev_ebitda":      "EV/EBITDA",
    # Margins
    "gross_margin":   "Gross margin (0–100 scale, stored as %)",
    "operating_margin":"Operating margin (0–100 scale)",
    "fcf_margin":     "Free cash flow margin (0–100 scale)",
    "revenue_cagr":   "Revenue CAGR % (3-year)",
    # Factor scores
    "composite":      "Composite factor score (0–100)",
    "quality":        "Quality score (0–100)",
    "growth":         "Growth score (0–100)",
    "value":          "Value score (0–100)",
    "momentum":       "Momentum score (0–100)",
    "risk":           "Risk score (0–100, lower = less risk)",
    "confidence":     "Model confidence (0–100)",
    # Technical
    "rsi_14":         "RSI 14-day (0–100)",
    "support":        "52-week support level ($)",
    "resistance":     "52-week resistance level ($)",
    # Derived useful helpers
    "upside_to_resistance": "% upside to resistance = (resistance-price)/price*100",
    "downside_to_support":  "% downside to support = (price-support)/price*100",
}

# Compound fields derived automatically
_DERIVED_FIELDS = {
    "upside_to_resistance": lambda r: (
        (r.get("resistance", 0) - r.get("price", 0)) / r.get("price", 1) * 100
        if r.get("resistance") and r.get("price") else None
    ),
    "downside_to_support": lambda r: (
        (r.get("price", 0) - r.get("support", 0)) / r.get("price", 1) * 100
        if r.get("support") and r.get("price") else None
    ),
}


class FormulaError(Exception):
    pass


def _eval_expr(node: ast.AST, context: dict[str, float]) -> float:
    """Recursively evaluate a safe AST expression."""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return float(node.value)
        raise FormulaError(f"Unsupported constant type: {type(node.value)}")

    elif isinstance(node, ast.Name):
        name = node.id
        if name in context:
            val = context[name]
            if val is None:
                raise FormulaError(f"Field '{name}' has no value for this symbol")
            return float(val)
        if name in _SAFE_FUNCS:
            raise FormulaError(f"'{name}' is a function — call it: {name}(...)")
        raise FormulaError(f"Unknown field: '{name}'. Available: {', '.join(sorted(context.keys()))}")

    elif isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _SAFE_OPS:
            raise FormulaError(f"Unsupported operator: {type(node.op).__name__}")
        left  = _eval_expr(node.left, context)
        right = _eval_expr(node.right, context)
        if op_type == ast.Div and right == 0:
            raise FormulaError("Division by zero")
        return _SAFE_OPS[op_type](left, right)

    elif isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _SAFE_OPS:
            raise FormulaError(f"Unsupported unary: {type(node.op).__name__}")
        return _SAFE_OPS[op_type](_eval_expr(node.operand, context))

    elif isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise FormulaError("Function calls must be simple names")
        fn_name = node.func.id
        if fn_name not in _SAFE_FUNCS:
            raise FormulaError(f"Unknown function: '{fn_name}'. Available: {', '.join(_SAFE_FUNCS)}")
        args = [_eval_expr(a, context) for a in node.args]
        try:
            return float(_SAFE_FUNCS[fn_name](*args))
        except Exception as e:
            raise FormulaError(f"Error in {fn_name}(): {e}")

    elif isinstance(node, ast.Expression):
        return _eval_expr(node.body, context)

    else:
        raise FormulaError(f"Unsupported expression: {type(node).__name__}")


def evaluate_formula(expression: str, row: dict) -> Optional[float]:
    """
    Evaluate a formula expression for a single row of screener data.
    Returns float result or None if any required field is missing.
    """
    # Build context from row + derived fields
    context = {}
    for field_name in AVAILABLE_FIELDS:
        if field_name in _DERIVED_FIELDS:
            context[field_name] = _DERIVED_FIELDS[field_name](row)
        else:
            context[field_name] = row.get(field_name)

    try:
        tree = ast.parse(expression.strip(), mode="eval")
        result = _eval_expr(tree.body, context)
        return result if math.isfinite(result) else None
    except FormulaError:
        raise
    except Exception as e:
        raise FormulaError(f"Parse error: {e}")


def validate_formula(expression: str) -> tuple[bool, str]:
    """
    Validate a formula without executing it.
    Returns (is_valid, error_message).
    """
    if not expression or not expression.strip():
        return False, "Formula cannot be empty"

    # Check for dangerous patterns
    forbidden = ["import", "exec", "eval", "__", "open", "os.", "sys.",
                 "subprocess", "globals", "locals", "getattr", "setattr"]
    expr_lower = expression.lower()
    for f in forbidden:
        if f in expr_lower:
            return False, f"Forbidden keyword: '{f}'"

    # Try to parse
    try:
        ast.parse(expression.strip(), mode="eval")
    except SyntaxError as e:
        return False, f"Syntax error: {e}"

    # Test with dummy values
    dummy_row = {f: 50.0 for f in AVAILABLE_FIELDS if f not in _DERIVED_FIELDS}
    dummy_row.update({"price": 100.0, "pe_ttm": 20.0, "ps_ttm": 3.0,
                      "gross_margin": 60.0, "fcf_margin": 15.0,
                      "support": 95.0, "resistance": 110.0,
                      "volume": 1000000.0})
    try:
        result = evaluate_formula(expression, dummy_row)
        return True, f"✅ Valid — test result: {result:.4f}"
    except FormulaError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Evaluation error: {e}"


# ─────────────────────────────────────────────────────────────
# Formula dataclass
# ─────────────────────────────────────────────────────────────

@dataclass
class Formula:
    id:          str
    name:        str           # e.g. "FCF Yield"
    expression:  str           # e.g. "fcf_margin / pe_ttm * 100"
    description: str = ""
    higher_is_better: bool = True
    category:    str = "Custom"
    created_at:  str = ""
    is_shared:   bool = False

    def to_dict(self) -> dict:
        return {
            "id":               self.id,
            "name":             self.name,
            "expression":       self.expression,
            "description":      self.description,
            "higher_is_better": self.higher_is_better,
            "category":         self.category,
            "created_at":       self.created_at,
            "is_shared":        self.is_shared,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Formula":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ─────────────────────────────────────────────────────────────
# Built-in formula library
# ─────────────────────────────────────────────────────────────

BUILTIN_FORMULAS: list[Formula] = [
    Formula(
        id="builtin_fcf_yield",
        name="FCF Yield",
        expression="fcf_margin / pe_ttm * 100",
        description="FCF Margin ÷ P/E × 100. Higher = more cash generation per dollar paid. "
                    "Buffett favors stocks where this > 5.",
        higher_is_better=True,
        category="Valuation",
    ),
    Formula(
        id="builtin_earnings_yield",
        name="Earnings Yield",
        expression="100 / pe_ttm",
        description="Inverse of P/E — the earnings return per dollar invested. "
                    "Compare to bond yields for equity risk premium.",
        higher_is_better=True,
        category="Valuation",
    ),
    Formula(
        id="builtin_peg_approx",
        name="PEG Approximation",
        expression="pe_ttm / revenue_cagr",
        description="Price/Earnings divided by revenue growth rate. "
                    "PEG < 1 = potentially undervalued growth stock.",
        higher_is_better=False,
        category="Valuation",
    ),
    Formula(
        id="builtin_quality_value",
        name="Quality-Value Blend",
        expression="(quality + value) / 2",
        description="Average of Quality and Value factor scores. "
                    "Targets fundamentally sound stocks at reasonable prices.",
        higher_is_better=True,
        category="Factor Blend",
    ),
    Formula(
        id="builtin_garp",
        name="GARP Score",
        expression="(growth * 0.4) + (value * 0.3) + (quality * 0.3)",
        description="Growth At Reasonable Price — weighted blend of Growth, Value, Quality. "
                    "Classic GARP investing approach.",
        higher_is_better=True,
        category="Factor Blend",
    ),
    Formula(
        id="builtin_momentum_quality",
        name="Momentum-Quality Blend",
        expression="(momentum * 0.6) + (quality * 0.4)",
        description="High momentum with quality fundamentals. "
                    "Avoids momentum traps in low-quality names.",
        higher_is_better=True,
        category="Factor Blend",
    ),
    Formula(
        id="builtin_margin_efficiency",
        name="Margin Efficiency",
        expression="(gross_margin + operating_margin + fcf_margin) / 3",
        description="Average of gross, operating, and FCF margins. "
                    "Measures overall profitability quality.",
        higher_is_better=True,
        category="Profitability",
    ),
    Formula(
        id="builtin_rsi_value_combo",
        name="RSI-Value Signal",
        expression="value * (1 - rsi_14 / 100)",
        description="Value score adjusted for RSI. "
                    "Rewards oversold (low RSI) value stocks. "
                    "High score = undervalued and oversold.",
        higher_is_better=True,
        category="Technical-Fundamental",
    ),
    Formula(
        id="builtin_upside_momentum",
        name="Upside-Momentum Score",
        expression="upside_to_resistance * momentum / 100",
        description="% upside to resistance × momentum score ÷ 100. "
                    "Finds stocks with room to run and positive momentum.",
        higher_is_better=True,
        category="Technical",
    ),
    Formula(
        id="builtin_risk_adjusted_composite",
        name="Risk-Adjusted Composite",
        expression="composite * (1 - risk / 100)",
        description="Composite score penalized by risk. "
                    "Favors high-quality stocks with low risk scores.",
        higher_is_better=True,
        category="Risk-Adjusted",
    ),
    Formula(
        id="builtin_defensive_score",
        name="Defensive Score",
        expression="(quality * 0.5) + ((100 - risk) * 0.3) + (value * 0.2)",
        description="Prioritizes quality and low-risk over growth. "
                    "Good for defensive/recession-resistant screening.",
        higher_is_better=True,
        category="Factor Blend",
    ),
    Formula(
        id="builtin_ps_growth_adj",
        name="PS Growth-Adjusted",
        expression="ps_ttm / revenue_cagr",
        description="P/S divided by revenue growth — like PEG but using P/S. "
                    "Better for high-growth companies without positive earnings.",
        higher_is_better=False,
        category="Valuation",
    ),
]


# ─────────────────────────────────────────────────────────────
# Apply formulas to screener results
# ─────────────────────────────────────────────────────────────

def apply_formulas_to_results(
    results: list[dict],
    formulas: list[Formula],
) -> pd.DataFrame:
    """
    Apply a list of formulas to screener results.
    Returns a DataFrame with original columns + one column per formula.
    Each formula column is named by the formula's name.
    """
    if not results:
        return pd.DataFrame()

    # Add derived fields to every row first
    enriched = []
    for row in results:
        r = dict(row)
        for fname, fn in _DERIVED_FIELDS.items():
            try:
                r[fname] = fn(r)
            except Exception:
                r[fname] = None
        enriched.append(r)

    df = pd.DataFrame(enriched)

    # Evaluate each formula
    for formula in formulas:
        col_values = []
        for row in enriched:
            try:
                val = evaluate_formula(formula.expression, row)
                col_values.append(round(val, 4) if val is not None else None)
            except Exception:
                col_values.append(None)
        df[formula.name] = col_values

    return df


def filter_by_formula(
    df: pd.DataFrame,
    formula_name: str,
    min_val: Optional[float] = None,
    max_val: Optional[float] = None,
) -> pd.DataFrame:
    """Filter screener results by a formula column value."""
    if formula_name not in df.columns:
        return df
    mask = pd.Series([True] * len(df), index=df.index)
    col = df[formula_name].dropna()
    if min_val is not None:
        mask &= df[formula_name].fillna(-999999) >= min_val
    if max_val is not None:
        mask &= df[formula_name].fillna(999999) <= max_val
    return df[mask]


# ─────────────────────────────────────────────────────────────
# Formula persistence (session-based + optional DB)
# ─────────────────────────────────────────────────────────────

def save_formula_session(formula: Formula, session_key: str = "custom_formulas"):
    """Save formula to Streamlit session state."""
    import streamlit as st
    if session_key not in st.session_state:
        st.session_state[session_key] = {}
    st.session_state[session_key][formula.id] = formula.to_dict()


def load_formulas_session(session_key: str = "custom_formulas") -> list[Formula]:
    """Load user's custom formulas from session state."""
    import streamlit as st
    raw = st.session_state.get(session_key, {})
    formulas = []
    for d in raw.values():
        try:
            formulas.append(Formula.from_dict(d))
        except Exception:
            pass
    return formulas


def delete_formula_session(formula_id: str, session_key: str = "custom_formulas"):
    import streamlit as st
    raw = st.session_state.get(session_key, {})
    raw.pop(formula_id, None)
    st.session_state[session_key] = raw


def save_formula_db(db, formula: Formula, tenant_id: str, user_id: str):
    """Persist formula to DB via screener_presets table."""
    try:
        from modules.collab.collab_service import save_screener_preset
        save_screener_preset(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            user_email="",
            name=f"[Formula] {formula.name}",
            filters={"formula": formula.to_dict()},
            query_text=formula.expression,
            is_shared=formula.is_shared,
            description=formula.description,
        )
    except Exception as e:
        print(f"[formula_engine] DB save error: {e}")


def load_formulas_db(db, tenant_id: str, user_id: str) -> list[Formula]:
    """Load formulas from DB (saved via screener_presets)."""
    try:
        from modules.collab.collab_service import get_screener_presets
        presets = get_screener_presets(db, tenant_id, user_id)
        formulas = []
        for p in presets:
            filters = p.get("filters", {})
            if "formula" in filters:
                try:
                    formulas.append(Formula.from_dict(filters["formula"]))
                except Exception:
                    pass
        return formulas
    except Exception as e:
        print(f"[formula_engine] DB load error: {e}")
        return []