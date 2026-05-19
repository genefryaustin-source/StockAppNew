from sqlalchemy import Column, String, Integer, DateTime
from datetime import datetime, UTC
from modules.db.core import Base

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, default="default_tenant")

    email = Column(String, nullable=False, unique=True)
    role = Column(String, nullable=False, default="client")

    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    # REQUIRED — your table already has this column
    password_hash = Column(String, nullable=True)

    # REQUIRED — your migrations add this
    is_active = Column(Integer, nullable=False, default=1)


# =====================================================
# UNIVERSE TABLE
# =====================================================



class Universe(Base):
    __tablename__ = "universes"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)

    # ✅ REQUIRED
    tenant_id = Column(String, nullable=False, default="default_tenant")

    # ✅ REQUIRED (fix for your error)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC))
# =====================================================
# UNIVERSE SYMBOLS (CRITICAL)
# =====================================================

class UniverseSymbol(Base):
    __tablename__ = "universe_symbols"

    symbol = Column(String, primary_key=True)
    tenant_id = Column(String, primary_key=True)

    # 🔥 REQUIRED FOR YOUR SYSTEM
    universe_id = Column(String, nullable=True)

# =====================================================
# LEGACY COMPATIBILITY: UNIVERSE EQUITIES
# =====================================================

class UniverseEquity(Base):
    __tablename__ = "universe_equities"

    symbol = Column(String, primary_key=True)
    tenant_id = Column(String, primary_key=True)

    # Match UniverseSymbol structure for compatibility
    universe_id = Column(String, nullable=True)

# =====================================================
# LEGACY COMPATIBILITY: UNIVERSE ANALYTICS CACHE
# =====================================================

class UniverseAnalyticsCache(Base):
    __tablename__ = "universe_analytics_cache"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False)
    universe_id = Column(String, nullable=True)
    symbol = Column(String, nullable=False)

    analytics_snapshot_id = Column(String, nullable=True)
    analytics_asof = Column(String, nullable=True)

    sector = Column(String, nullable=True)
    rating = Column(String, nullable=True)

    composite_score = Column(Integer, nullable=True)
    confidence_score = Column(Integer, nullable=True)

    quality = Column(Integer, nullable=True)
    growth = Column(Integer, nullable=True)
    value = Column(Integer, nullable=True)
    momentum = Column(Integer, nullable=True)
    risk = Column(Integer, nullable=True)

    updated_at = Column(DateTime, default=lambda: datetime.now(UTC))



# =====================================================
# SECURITY MASTER (NEW PIPELINE)
# =====================================================

class SecurityMaster(Base):
    __tablename__ = "security_master"

    symbol = Column(String, primary_key=True, index=True)

    exchange = Column(String, nullable=True)
    is_etf = Column(Integer, nullable=False, default=0)

    sector = Column(String, nullable=True)
    industry = Column(String, nullable=True)

    source = Column(String, nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC))