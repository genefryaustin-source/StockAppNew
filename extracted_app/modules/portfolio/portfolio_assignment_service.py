from sqlalchemy import text
from typing import List, Dict
import uuid


class PortfolioAssignmentService:

    def __init__(self, db):
        self.db = db

    # ---------------------------------
    # ASSIGN PORTFOLIO TO USER
    # ---------------------------------
    def assign_portfolio_to_user(self, portfolio_id: str, user_id: str, tenant_id: str) -> bool:
        try:
            self.db.execute(text("""
                INSERT OR IGNORE INTO portfolio_user_map (
                    id,
                    portfolio_id,
                    user_id,
                    role,
                    created_at
                )
                VALUES (
                    :id,
                    :pid,
                    :uid,
                    :role,
                    CURRENT_TIMESTAMP
                )
            """), {
                "id": str(uuid.uuid4()),
                "pid": portfolio_id,
                "uid": user_id,
                "role": "owner"   # default role
            })

            self.db.commit()
            return True

        except Exception as e:
            self.db.rollback()
            print("❌ ASSIGN ERROR:", e)
            return False

    # ---------------------------------
    # REMOVE PORTFOLIO FROM USER
    # ---------------------------------
    def remove_portfolio_from_user(self, portfolio_id: str, user_id: str) -> bool:
        try:
            self.db.execute(text("""
                DELETE FROM portfolio_user_map
                WHERE user_id = :uid
                AND portfolio_id = :pid
            """), {
                "uid": user_id,
                "pid": portfolio_id
            })

            self.db.commit()
            return True

        except Exception as e:
            self.db.rollback()
            print("❌ UNASSIGN ERROR:", e)
            return False

    # ---------------------------------
    # GET USER PORTFOLIOS (TENANT SAFE)
    # ---------------------------------
    def get_user_portfolios(self, tenant_id: str, user_id: str) -> List[Dict]:
        try:
            rows = self.db.execute(text("""
                SELECT
                    p.id,
                    p.name,
                    p.base_currency
                FROM portfolio_user_map pum
                JOIN portfolios p
                    ON p.id = pum.portfolio_id
                WHERE pum.user_id = :uid
                AND p.tenant_id = :tenant
                ORDER BY p.name
            """), {
                "uid": user_id,
                "tenant": tenant_id
            }).fetchall()

            print("DEBUG get_user_portfolios ROWS:", rows)

            return [
                {
                    "id": r[0],
                    "name": r[1],
                    "base_currency": r[2] if len(r) > 2 else "USD",
                    "benchmark": "SPY"
                }
                for r in rows
            ]

        except Exception as e:
            print("❌ GET USER PORTFOLIOS ERROR:", e)
            return []

    # ---------------------------------
    # GET USERS FOR A PORTFOLIO
    # ---------------------------------
    def get_portfolio_users(self, portfolio_id: str) -> List[str]:
        try:
            rows = self.db.execute(text("""
                SELECT user_id
                FROM portfolio_user_map
                WHERE portfolio_id = :pid
            """), {"pid": portfolio_id}).fetchall()

            return [r[0] for r in rows]

        except Exception as e:
            print("❌ GET PORTFOLIO USERS ERROR:", e)
            return []

    # ---------------------------------
    # LIST TENANT PORTFOLIOS
    # ---------------------------------
    def list_tenant_portfolios(self, tenant_id: str) -> List[Dict]:
        try:
            rows = self.db.execute(text("""
                SELECT id, name
                FROM portfolios
                WHERE tenant_id = :tenant
                ORDER BY name
            """), {"tenant": tenant_id}).fetchall()

            return [{"id": r[0], "name": r[1]} for r in rows]

        except Exception as e:
            print("❌ LIST TENANT PORTFOLIOS ERROR:", e)
            return []

    # ---------------------------------
    # ADMIN: VIEW ALL ASSIGNMENTS
    # ---------------------------------
    def get_all_assignments(self, tenant_id: str) -> List[Dict]:
        try:
            rows = self.db.execute(text("""
                SELECT 
                    u.email,
                    pum.user_id,
                    p.id as portfolio_id,
                    p.name as portfolio_name
                FROM portfolio_user_map pum
                JOIN users u ON u.id = pum.user_id
                JOIN portfolios p ON p.id = pum.portfolio_id
                WHERE p.tenant_id = :tenant
                ORDER BY u.email, p.name
            """), {"tenant": tenant_id}).fetchall()

            return [
                {
                    "email": r[0],
                    "user_id": r[1],
                    "portfolio_id": r[2],
                    "portfolio_name": r[3],
                }
                for r in rows
            ]

        except Exception as e:
            print("❌ GET ALL ASSIGNMENTS ERROR:", e)
            return []