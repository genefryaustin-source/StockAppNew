from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from datetime import datetime, UTC

from modules.db.core import Base


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

    symbol = Column(String, primary_key=True)
    tenant_id = Column(String, primary_key=True)

    # Optional fields — add more if your seed file includes them
    factor_score = Column(Integer, nullable=True)
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