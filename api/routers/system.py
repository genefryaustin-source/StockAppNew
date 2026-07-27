from datetime import datetime, UTC

from fastapi import APIRouter

router = APIRouter()


@router.get("/status")
async def status():

    return {

        "application": "StockApp Platform API",

        "status": "running",

        "time": datetime.now(
            UTC,
        ).isoformat(),

    }