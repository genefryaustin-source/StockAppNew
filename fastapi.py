from fastapi import FastAPI
from modules.api.portfolio_api import PortfolioAPI

app = FastAPI()

# NOTE: you will wire real DB + data pipeline here
api = PortfolioAPI(db_session=None)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/portfolio/{portfolio_id}")
def get_portfolio(portfolio_id: int):
    return {
        "message": "Wire real data pipeline here",
        "portfolio_id": portfolio_id,
    }