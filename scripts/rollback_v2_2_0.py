import shutil

shutil.copy(
    "versions/v2.2.0_portfolio_stable/stockapp.db",
    "stockapp.db"
)

print("Rollback to v2.2.0 complete")