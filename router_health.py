from fastapi import Request

from api.responses import ResponseBuilder


@router.get("/health")

async def health(
    request: Request,
):

    return ResponseBuilder.success(

        request=request,

        data={
            "status": "healthy",
        },
    )