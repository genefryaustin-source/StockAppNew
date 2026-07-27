def serialize_order(order):

    return {

        "id": order.id,

        "symbol": order.symbol,

        "side": order.side,

        "order_type": order.order_type,

        "status": order.status,

        "qty": order.qty,

        "filled_qty": order.filled_qty,

        "avg_fill_price": order.avg_fill_price,

        "broker": order.broker,

        "broker_order_id": order.broker_order_id,

        "submitted_at": (
            order.submitted_at.isoformat()
            if order.submitted_at
            else None
        ),

        "filled_at": (
            order.filled_at.isoformat()
            if order.filled_at
            else None
        ),

        "updated_at": (
            order.updated_at.isoformat()
            if order.updated_at
            else None
        ),
    }


def serialize_orders(orders):

    return [
        serialize_order(order)
        for order in orders
    ]