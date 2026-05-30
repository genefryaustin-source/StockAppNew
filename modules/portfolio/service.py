import uuid
from datetime import datetime, UTC
from sqlalchemy import text


def create_portfolio(db, tenant_id, name):

    db.execute(
        text("""
        INSERT INTO portfolios (id, tenant_id, name, created_at)
        VALUES (:id, :tenant_id, :name, :created_at)
        """),
        {
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "name": name.strip(),
            "created_at": datetime.now(UTC),
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


from sqlalchemy import text
import uuid
from datetime import datetime


def add_position(db, tenant_id, portfolio_id, symbol, quantity, cost_basis):

    db.execute(
        text("""
        INSERT INTO portfolio_positions
        (id, tenant_id, portfolio_id, symbol, quantity, cost_basis, created_at)
        VALUES (:id, :tenant_id, :portfolio_id, :symbol, :quantity, :cost_basis, :created_at)
        """),
        {
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "portfolio_id": portfolio_id,
            "symbol": symbol,
            "quantity": quantity,
            "cost_basis": cost_basis,
            "created_at": datetime.now(UTC),
        },
    )

    db.commit()



def list_positions(db, portfolio_id):

    rows = db.execute(
        text("""
        SELECT symbol, quantity, cost_basis
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