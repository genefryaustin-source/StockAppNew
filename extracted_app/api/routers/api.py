"""
Master API Router

Registers every feature router.
"""

from fastapi import APIRouter

from .health import router as health_router
from .version import router as version_router
from .system import router as system_router
from .auth import router as auth_router
from .api_keys import router as api_keys_router
from .admin_api_keys import router as admin_api_keys_router
from .admin_tenants import router as admin_tenants_router
from .portfolio import router as portfolio_router
from .orders import router as orders_router
from .market_data import router as market_data_router
from .analytics import router as analytics_router
from .alerts import router as alerts_router
from .ipo import router as ipo_router
from .preipo import router as preipo_router
from .options import router as options_router
from .forex import router as forex_router
from .executive import router as executive_router
from .ai import router as ai_router
from .crypto import router as crypto_router
from .market import router as market_router




api_router = APIRouter()

#
# Infrastructure
#

api_router.include_router(
    health_router,
    tags=["Health"],
)

api_router.include_router(
    version_router,
    tags=["Version"],
)

api_router.include_router(
    system_router,
    tags=["System"],
)

api_router.include_router(
    auth_router,
    tags=["Authentication"],
)

api_router.include_router(
    api_keys_router,
)

api_router.include_router(
    admin_api_keys_router,
)

api_router.include_router(
    admin_tenants_router,
)

api_router.include_router(
    portfolio_router,
)

api_router.include_router(
    orders_router,
)

api_router.include_router(
    market_data_router,
)

api_router.include_router(
    analytics_router,
)

api_router.include_router(
    alerts_router,
)

api_router.include_router(
    ipo_router,
)

api_router.include_router(
    preipo_router,
)

api_router.include_router(
    options_router,
)

api_router.include_router(
    forex_router,
)

api_router.include_router(
    executive_router,
)

api_router.include_router(
    ai_router,
)

api_router.include_router(
    crypto_router,
)

api_router.include_router(
    market_router,
)