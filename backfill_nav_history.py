# ---------------------------------
# BACKFILL NAV HISTORY (SAFE SCRIPT)
# ---------------------------------

from modules.db.core import SessionLocal
from modules.portfolio.nav_service import NavService
import modules.market_data.service as mds

# ---------------------------------
# INIT DB
# ---------------------------------
db = SessionLocal()

# ---------------------------------
# INIT MARKET DATA SERVICE
# ---------------------------------
# Your codebase uses module-level service pattern
market_data_service = mds

# ---------------------------------
# SET PORTFOLIO ID
# ---------------------------------
portfolio_id = "f2ac8872-2bf9-4fe5-bfa0-8adbc61a85bb"

# ---------------------------------
# RUN BACKFILL
# ---------------------------------
nav_service = NavService(db, market_data_service)

nav_service.backfill_nav_history(
    portfolio_id=portfolio_id,
    days=120
)

print("✅ NAV backfill complete")