import pandas as pd

from modules.portfolio.construction_service import PortfolioConstructionService
from modules.market_data.service import get_latest_price_map
from modules.analytics.models import AnalyticsSnapshot
from models.trading import PortfolioPosition
from modules.portfolio.order_service import OrderService


def run_auto_rebalance(db, tenant_id, portfolio_id):

    print("🚀 AUTO REBALANCE START")

    snapshots = (
        db.query(AnalyticsSnapshot)
        .filter(AnalyticsSnapshot.tenant_id == tenant_id)
        .all()
    )

    if not snapshots:
        print("No snapshots found")
        return

    # -----------------------------------
    # SPLIT SIGNALS (FIX)
    # -----------------------------------
    buy_symbols = [s.symbol for s in snapshots if s.signal in ["Strong Buy", "Buy"]]
    sell_symbols = [s.symbol for s in snapshots if s.signal in ["Strong Sell", "Sell"]]

    print("DEBUG SIGNALS:", {
        "buy": buy_symbols,
        "sell": sell_symbols
    })

    if not buy_symbols and not sell_symbols:
        print("No actionable signals")
        return

    # -----------------------------------
    # LOAD POSITIONS
    # -----------------------------------
    positions = (
        db.query(PortfolioPosition)
        .filter(PortfolioPosition.portfolio_id == portfolio_id)
        .all()
    )

    # -----------------------------------
    # EXECUTE SELL SIGNALS FIRST (FIX)
    # -----------------------------------
    service = OrderService(db, broker=None, market_data_service=None)

    for p in positions:
        qty = float(getattr(p, "qty", 0) or 0)

        if p.symbol in sell_symbols and qty > 0:
            print("🔥 AUTO TRADE SELL:", p.symbol, qty)

            service.submit_order(
                portfolio_id=portfolio_id,
                user_id=None,
                symbol=p.symbol,
                side="sell",
                qty=qty,
                order_type="market",
                tif="day",
            )
    print("DEBUG POSITIONS:", [
        {"symbol": p.symbol, "qty": getattr(p, "qty", None)}
        for p in positions
    ])
    # -----------------------------------
    # BUILD TARGET FOR BUYS
    # -----------------------------------
    if not buy_symbols:
        print("No buy signals after sells")
        return

    weight = 1.0 / len(buy_symbols)

    target_df = pd.DataFrame({
        "Symbol": buy_symbols,
        "Target Weight": [weight] * len(buy_symbols),
    })

    positions_df = pd.DataFrame([{
        "Symbol": p.symbol,
        "Market Value": p.market_value
    } for p in positions])

    prices = get_latest_price_map(buy_symbols)

    portfolio_value = sum(float(p.market_value or 0) for p in positions) or 100000

    pcs = PortfolioConstructionService(positions_df)

    trades = pcs.generate_rebalance_trades(
        target_df=target_df,
        prices=prices,
        portfolio_value=portfolio_value
    )

    print("TRADES DF:", trades)

    if trades is None or trades.empty:
        print("No trades generated")
        return

    # -----------------------------------
    # EXECUTE BUY TRADES
    # -----------------------------------
    for _, t in trades.iterrows():
        print("🔥 AUTO TRADE:", t["Symbol"], t["Side"], t["Qty"])

        service.submit_order(
            portfolio_id=portfolio_id,
            user_id=None,
            symbol=t["Symbol"],
            side=t["Side"],
            qty=float(t["Qty"]),
            order_type="market",
            tif="day",
        )