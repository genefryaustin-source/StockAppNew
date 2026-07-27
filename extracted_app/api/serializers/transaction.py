def serialize_transaction(tx):

    return {

        "id": tx.id,

        "portfolio_id": tx.portfolio_id,

        "entry_type": tx.entry_type,

        "amount": tx.amount,

        "trade_order_id": tx.trade_order_id,

        "notes": tx.notes,

        "created_at": (
            tx.created_at.isoformat()
            if tx.created_at
            else None
        ),
    }


def serialize_transactions(transactions):

    return [

        serialize_transaction(tx)

        for tx in transactions

    ]