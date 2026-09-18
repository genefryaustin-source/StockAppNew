"""
tools/api/smoke_test_tenant_export.py

End-to-end smoke test for GET /api/v1/tenant/portfolio/full
(api/routers/tenant_export.py) -- exercises real HTTP requests via
FastAPI's TestClient against the actual api.main:app (real routing, real
auth dependency, real module registry, real ORM queries), on a throwaway
file-based SQLite database seeded with positions across stocks and
crypto, plus stock/crypto order history.

Usage:
    cd <repo root>
    python3 tools/api/smoke_test_tenant_export.py
"""

import sys
import os
import uuid
import tempfile
from datetime import datetime, UTC

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

_db_path = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"
os.environ.setdefault("ENVIRONMENT", "development")

import modules.db.models          # noqa: F401
import models.trading             # noqa: F401
from models.base import Base
from modules.db.core import engine, new_db_session
from modules.db.models import Tenant, User
from models.trading import Portfolio, PortfolioPosition, TradeOrder

TENANT_ID = "tenant_default"   # matches api.auth.dependencies' development bypass
PORTFOLIO_ID = str(uuid.uuid4())

results = {"pass": 0, "fail": 0}


def check(label, fn):
    try:
        fn()
        print(f"PASS  {label}")
        results["pass"] += 1
    except Exception as e:
        print(f"FAIL  {label}: {type(e).__name__}: {e}")
        results["fail"] += 1


def main():
    Base.metadata.create_all(bind=engine)
    db = new_db_session()

    db.add(Tenant(id=TENANT_ID, name="Smoke Test Tenant", is_active=True, created_at=datetime.now(UTC)))
    db.add(User(id="u1", tenant_id=TENANT_ID, email="a@test.com", role="client",
                is_active=True, created_at=datetime.now(UTC)))
    db.add(Portfolio(id=PORTFOLIO_ID, tenant_id=TENANT_ID, name="Main", base_currency="USD",
                      starting_cash=100_000.0, is_active=True,
                      created_at=datetime.now(UTC), updated_at=datetime.now(UTC)))
    db.commit()

    db.add(PortfolioPosition(portfolio_id=PORTFOLIO_ID, symbol="AAPL", qty=10, avg_cost=150, market_price=190,
                              market_value=1900, unrealized_pnl=400, realized_pnl=0, updated_at=datetime.now(UTC)))
    db.add(PortfolioPosition(portfolio_id=PORTFOLIO_ID, symbol="BTC/USDT", qty=0.1, avg_cost=40000, market_price=60000,
                              market_value=6000, unrealized_pnl=2000, realized_pnl=0, updated_at=datetime.now(UTC)))
    db.add(TradeOrder(portfolio_id=PORTFOLIO_ID, symbol="AAPL", side="buy", order_type="market", tif="day",
                       qty=10, status="filled", avg_fill_price=150.0, filled_qty=10, created_at=datetime.now(UTC)))
    db.add(TradeOrder(portfolio_id=PORTFOLIO_ID, symbol="BTC/USDT", side="buy", order_type="market", tif="day",
                       qty=0.1, status="filled", avg_fill_price=59000.0, filled_qty=0.1, created_at=datetime.now(UTC)))
    db.commit()
    db.close()

    from fastapi.testclient import TestClient
    from api.main import app
    from api.auth.models import AuthenticatedUser
    from api.auth.current_user import get_current_user

    client = TestClient(app)

    def _check_app_imports_with_router_registered():
        # FastAPI's internal route-list shape varies by version (some wrap
        # entries in an opaque "_IncludedRouter" object with no public
        # .path), so prove registration functionally instead of
        # introspecting internals: a request to the new path must not
        # 404 with FastAPI's "not found" body.
        r = client.get("/api/v1/tenant/portfolio/full")
        assert r.status_code != 404, "new route isn't reachable -- router registration didn't take"

    check("New router is registered and reachable on the real api_router", _check_app_imports_with_router_registered)

    response_holder = {}

    def _check_dev_admin_gets_full_export():
        # The development-environment auth bypass authenticates as
        # super_admin -- exercise the endpoint through it rather than
        # constructing a real JWT/API key.
        r = client.get("/api/v1/tenant/portfolio/full")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["success"] is True
        data = body["data"]
        for key in ("tenant", "users", "portfolios", "positions", "equity_curve",
                    "snapshot_history", "orders"):
            assert key in data, f"missing key: {key}"
        response_holder["data"] = data

    check("GET /api/v1/tenant/portfolio/full returns 200 with every top-level section",
          _check_dev_admin_gets_full_export)

    def _check_positions_cover_multiple_asset_classes():
        data = response_holder["data"]
        positions = data["positions"]["positions"]
        symbols = {p["Symbol"] for p in positions}
        assert symbols == {"AAPL", "BTC/USDT"}, f"expected both assets, got {symbols}"
        classes = set(data["positions"]["by_asset_class"].keys())
        assert classes == {"equity", "crypto"}, f"expected 2 asset classes, got {classes}"

    check("Positions span multiple asset classes via the unified Risk Layer merge",
          _check_positions_cover_multiple_asset_classes)

    def _check_orders_split_correctly_by_asset_class():
        data = response_holder["data"]
        stock_crypto_orders = data["orders"]["stocks_crypto_tokenized_rwa"]
        assert len(stock_crypto_orders) == 2
        by_symbol = {o["symbol"]: o["asset_class"] for o in stock_crypto_orders}
        assert by_symbol["AAPL"] == "equity_or_rwa"
        assert by_symbol["BTC/USDT"] == "crypto"
        # No options/forex data seeded -- these must degrade to empty/available,
        # not raise or silently omit the key.
        assert "options" in data["orders"]
        assert "forex" in data["orders"]

    check("Stock and crypto orders share one table and are correctly tagged by asset class",
          _check_orders_split_correctly_by_asset_class)

    def _check_non_admin_gets_403():
        def _client_user():
            return AuthenticatedUser(
                authenticated=True, user_id="u2", username="client_user", tenant_id=TENANT_ID,
                email="client@test.com", roles=["client"], is_super_admin=False, token_type="Bearer",
            )
        app.dependency_overrides[get_current_user] = _client_user
        try:
            r = client.get("/api/v1/tenant/portfolio/full")
            assert r.status_code == 403, f"expected 403 for a non-admin caller, got {r.status_code}"
            assert r.json()["error"]["code"] == "forbidden"
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    check("Non-admin (client role) caller is rejected with 403, not a partial/empty 200",
          _check_non_admin_gets_403)

    def _check_admin_still_works_after_override_cleared():
        r = client.get("/api/v1/tenant/portfolio/full")
        assert r.status_code == 200, "dependency override cleanup should restore the dev admin bypass"

    check("Dependency override cleanup restores normal admin access", _check_admin_still_works_after_override_cleared)

    def _check_query_params_respected():
        r = client.get("/api/v1/tenant/portfolio/full", params={"include_all_users": "false"})
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["users"]["available"] is False

    check("include_all_users=false correctly suppresses the users section", _check_query_params_respected)

    print()
    print(f"{results['pass']} passed, {results['fail']} failed")
    return 1 if results["fail"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
