"""
modules/auth/custom_plan_service.py

Tenant-level custom plan overrides — controlled by super_admin.

Architecture:
  tenant_plans table stores per-tenant module overrides.
  These OVERRIDE the default plan-based entitlements:
    - A tenant on "starter" can have "Options Trading" enabled
    - A tenant on "pro" can have "Team Collaboration" disabled
    - Individual modules can be toggled on/off per tenant

Tables:
  tenant_plans         — base plan assigned to a tenant
  tenant_module_access — per-module on/off overrides per tenant
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import text


ALL_MODULES = [
    # Student
    "Watchlists", "Help",
    # Starter
    "Screener", "Market Overview", "Earnings", "Stock Dashboard",
    "Rankings", "Analytics", "Universe",
    # Pro
    "Formula Builder", "Intraday Charts", "Options Flow", "Options Trading",
    "Crypto", "AI Forecast", "AI Scanner", "AI Agent", "AI Portfolio",
    "Analyst Consensus", "Social Sentiment", "Research Reports",
    "Export / Sheets", "Regime Engine", "Smart Money", "Indicator Builder",
    "Portfolio Deployment", "Portfolio", "Portfolio Construction",
    "AI Rankings", "Market Data", "Alerts",
    "IPO Intelligence", "Pre-IPO Intelligence",
    # Team
    "Team Collaboration",
]

MODULE_CATEGORIES = {
    "Core":           ["Watchlists", "Help", "Screener", "Market Overview",
                       "Earnings", "Stock Dashboard", "Rankings", "Analytics", "Universe"],
    "Research":       ["Analyst Consensus", "Social Sentiment", "Research Reports",
                       "Export / Sheets", "Formula Builder", "Indicator Builder"],
    "AI Suite":       ["AI Rankings", "AI Scanner", "AI Agent", "AI Forecast",
                       "AI Portfolio"],
    "Trading":        ["Options Flow", "Options Trading", "Portfolio",
                       "Portfolio Construction", "Portfolio Deployment",
                       "Smart Money", "Alerts"],
    "Markets":        ["Intraday Charts", "Crypto", "Market Data",
                       "Regime Engine", "IPO Intelligence", "Pre-IPO Intelligence"],
    "Collaboration":  ["Team Collaboration"],
}


def ensure_tables(db):
    """
    Create custom plan tables if they don't exist.
    Always rolls back any aborted PostgreSQL transaction first —
    NeonDB aborts the whole connection on any prior error and
    DDL (CREATE TABLE) cannot run on an aborted transaction.
    """
    try:
        db.rollback()
    except Exception:
        pass

    try:
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS tenant_plans (
                tenant_id   TEXT PRIMARY KEY,
                base_plan   TEXT NOT NULL DEFAULT 'starter',
                custom_name TEXT,
                notes       TEXT,
                updated_by  TEXT,
                updated_at  TEXT
            )
        """))
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS tenant_module_access (
                id              TEXT PRIMARY KEY,
                tenant_id       TEXT NOT NULL,
                module_name     TEXT NOT NULL,
                is_enabled      BOOLEAN NOT NULL DEFAULT true,
                override_reason TEXT,
                set_by          TEXT,
                set_at          TEXT,
                UNIQUE(tenant_id, module_name)
            )
        """))
        db.commit()
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        print(f"[custom_plan] ensure_tables error: {e}")


def get_tenant_plan(db, tenant_id: str) -> dict:
    """Get the base plan and any custom overrides for a tenant."""
    ensure_tables(db)
    try:
        row = db.execute(text("""
            SELECT base_plan, custom_name, notes
            FROM tenant_plans
            WHERE tenant_id = :tid
        """), {"tid": tenant_id}).fetchone()

        if row:
            return {
                "base_plan":   row[0] or "starter",
                "custom_name": row[1],
                "notes":       row[2],
            }
    except Exception:
        pass
    return {"base_plan": "starter", "custom_name": None, "notes": None}


def set_tenant_plan(db, tenant_id: str, base_plan: str,
                    custom_name: str = None, notes: str = None,
                    updated_by: str = None):
    """Set the base plan for a tenant."""
    ensure_tables(db)
    now = datetime.now(timezone.utc).isoformat()
    db.execute(text("""
        INSERT INTO tenant_plans (tenant_id, base_plan, custom_name, notes, updated_by, updated_at)
        VALUES (:tid, :plan, :name, :notes, :by, :now)
        ON CONFLICT (tenant_id) DO UPDATE SET
            base_plan   = EXCLUDED.base_plan,
            custom_name = EXCLUDED.custom_name,
            notes       = EXCLUDED.notes,
            updated_by  = EXCLUDED.updated_by,
            updated_at  = EXCLUDED.updated_at
    """), {"tid": tenant_id, "plan": base_plan, "name": custom_name,
           "notes": notes, "by": updated_by, "now": now})
    db.commit()


def get_module_overrides(db, tenant_id: str) -> dict[str, bool]:
    """Get all module overrides for a tenant. Returns {module_name: is_enabled}."""
    ensure_tables(db)
    try:
        rows = db.execute(text("""
            SELECT module_name, is_enabled
            FROM tenant_module_access
            WHERE tenant_id = :tid
        """), {"tid": tenant_id}).fetchall()
        return {row[0]: bool(row[1]) for row in rows}
    except Exception:
        return {}


def set_module_override(db, tenant_id: str, module_name: str,
                        is_enabled: bool, set_by: str = None,
                        reason: str = None):
    """Enable or disable a specific module for a tenant."""
    ensure_tables(db)
    now = datetime.now(timezone.utc).isoformat()
    db.execute(text("""
        INSERT INTO tenant_module_access
            (id, tenant_id, module_name, is_enabled, override_reason, set_by, set_at)
        VALUES (:id, :tid, :mod, :enabled, :reason, :by, :now)
        ON CONFLICT (tenant_id, module_name) DO UPDATE SET
            is_enabled      = EXCLUDED.is_enabled,
            override_reason = EXCLUDED.override_reason,
            set_by          = EXCLUDED.set_by,
            set_at          = EXCLUDED.set_at
    """), {"id": str(uuid.uuid4()), "tid": tenant_id, "mod": module_name,
           "enabled": is_enabled, "reason": reason, "by": set_by, "now": now})
    db.commit()


def set_bulk_module_overrides(db, tenant_id: str, overrides: dict[str, bool],
                               set_by: str = None):
    """Set multiple module overrides at once."""
    for module_name, is_enabled in overrides.items():
        set_module_override(db, tenant_id, module_name, is_enabled, set_by)


def clear_module_override(db, tenant_id: str, module_name: str):
    """Remove a specific override — reverts to plan default."""
    try:
        db.execute(text("""
            DELETE FROM tenant_module_access
            WHERE tenant_id = :tid AND module_name = :mod
        """), {"tid": tenant_id, "mod": module_name})
        db.commit()
    except Exception:
        pass


def clear_all_overrides(db, tenant_id: str):
    """Remove all overrides for a tenant — reverts to plan defaults."""
    try:
        db.execute(text("""
            DELETE FROM tenant_module_access WHERE tenant_id = :tid
        """), {"tid": tenant_id})
        db.commit()
    except Exception:
        pass


def check_module_access(db, tenant_id: str, module_name: str,
                         plan_allows: bool) -> bool:
    """
    Final access check combining plan entitlement + tenant override.

    Logic:
      1. If tenant has explicit override → use that (can grant OR revoke)
      2. Otherwise → use plan_allows from standard entitlements
    """
    overrides = get_module_overrides(db, tenant_id)
    if module_name in overrides:
        return overrides[module_name]
    return plan_allows


def get_all_tenants(db) -> list[dict]:
    """List all tenants with their plan info."""
    ensure_tables(db)
    try:
        rows = db.execute(text("""
            SELECT DISTINCT u.tenant_id,
                   COALESCE(tp.base_plan, 'starter') as base_plan,
                   COALESCE(tp.custom_name, '') as custom_name,
                   COUNT(u.id) as user_count,
                   tp.updated_at
            FROM users u
            LEFT JOIN tenant_plans tp ON u.tenant_id = tp.tenant_id
            WHERE u.tenant_id IS NOT NULL
            GROUP BY u.tenant_id, tp.base_plan, tp.custom_name, tp.updated_at
            ORDER BY u.tenant_id
        """)).fetchall()
        return [
            {"tenant_id":   row[0],
             "base_plan":   row[1],
             "custom_name": row[2],
             "user_count":  row[3],
             "updated_at":  str(row[4] or "")[:10]}
            for row in rows
        ]
    except Exception:
        return []