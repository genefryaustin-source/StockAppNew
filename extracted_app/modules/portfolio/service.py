import uuid
from datetime import datetime, UTC
from sqlalchemy import text


def create_portfolio(db, tenant_id, name):

    db.execute(
        text("""
        INSERT INTO portfolios (
            id,
            tenant_id,
            name,
            description,
            benchmark,
            base_currency,
            starting_cash,
            is_active,
            created_at,
            updated_at
        )
        VALUES (
            :id,
            :tenant_id,
            :name,
            :description,
            :benchmark,
            :base_currency,
            :starting_cash,
            :is_active,
            :created_at,
            :updated_at
        )
        """),
        {
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "name": name.strip(),
            "description": "",
            "benchmark": "SPY",
            "base_currency": "USD",
            "starting_cash": 100000.0,
            "is_active": True,
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        },
    )

    db.commit()


def list_portfolios(db, tenant_id):

    rows = db.execute(
        text("""
        SELECT *
        FROM portfolios
        WHERE tenant_id = :tenant_id
        ORDER BY created_at DESC
        """),
        {"tenant_id": tenant_id},
    ).mappings().all()

    return rows





def add_position(db, tenant_id, portfolio_id, symbol, quantity, cost_basis):
    # NOTE: portfolio_positions has no tenant_id/created_at columns and uses
    # an autoincrement integer `id` -- tenant scoping happens one level up,
    # via portfolio_id -> portfolios.tenant_id. `tenant_id` is accepted here
    # only to keep the call signature stable for existing/future callers.
    #
    # market_price/market_value/unrealized_pnl/realized_pnl are NOT NULL on
    # this table with Python-side defaults -- those defaults only apply via
    # the ORM, not raw text() SQL, so they must be supplied explicitly here.
    db.execute(
        text("""
        INSERT INTO portfolio_positions
        (portfolio_id, symbol, qty, avg_cost,
         market_price, market_value, unrealized_pnl, realized_pnl, updated_at)
        VALUES (:portfolio_id, :symbol, :qty, :avg_cost,
                :market_price, :market_value, :unrealized_pnl, :realized_pnl, :updated_at)
        """),
        {
            "portfolio_id": portfolio_id,
            "symbol": symbol,
            "qty": quantity,
            "avg_cost": cost_basis,
            "market_price": 0.0,
            "market_value": 0.0,
            "unrealized_pnl": 0.0,
            "realized_pnl": 0.0,
            "updated_at": datetime.now(UTC),
        },
    )

    db.commit()



def list_positions(db, portfolio_id):

    rows = db.execute(
        text("""
        SELECT symbol, qty AS quantity, avg_cost AS cost_basis
        FROM portfolio_positions
        WHERE portfolio_id = :portfolio_id
        """),
        {"portfolio_id": portfolio_id},
    ).mappings().all()

    return rows


def remove_position(db, portfolio_id, symbol):

    db.execute(
        text("""
        DELETE FROM portfolio_positions
        WHERE portfolio_id = :portfolio_id
        AND symbol = :symbol
        """),
        {
            "portfolio_id": portfolio_id,
            "symbol": symbol.upper(),
        },
    )

    db.commit()


def record_trade(db, tenant_id, portfolio_id, symbol, side, quantity, price):

    db.execute(
        text("""
        INSERT INTO portfolio_trades
        (id, tenant_id, portfolio_id, symbol, side, quantity, price, trade_date)
        VALUES (:id, :tenant_id, :portfolio_id, :symbol, :side, :quantity, :price, :trade_date)
        """),
        {
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "portfolio_id": portfolio_id,
            "symbol": symbol.upper(),
            "side": side,
            "quantity": quantity,
            "price": price,
            "trade_date": datetime.now(UTC),
        },
    )

    db.commit()