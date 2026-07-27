from fastapi import APIRouter

from api.version import API_VERSION

router = APIRouter()


@router.get("/version")
async def version():

    return {

        "version": API_VERSION,

    }