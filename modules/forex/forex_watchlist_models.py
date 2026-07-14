from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


# ==========================================================
# Watchlist Item
# ==========================================================

@dataclass
class ForexWatchlistItem:

    id: str

    watchlist_id: str

    pair: str

    display_order: int = 0

    ai_enabled: bool = True

    alerts_enabled: bool = True

    auto_trade_enabled: bool = False

    notes: str = ""

    created_at: Optional[datetime] = None

    updated_at: Optional[datetime] = None

    raw: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:

        return {

            "id": self.id,

            "watchlist_id": self.watchlist_id,

            "pair": self.pair,

            "display_order": self.display_order,

            "ai_enabled": self.ai_enabled,

            "alerts_enabled": self.alerts_enabled,

            "auto_trade_enabled": self.auto_trade_enabled,

            "notes": self.notes,

            "created_at": (
                self.created_at.isoformat()
                if self.created_at
                else None
            ),

            "updated_at": (
                self.updated_at.isoformat()
                if self.updated_at
                else None
            ),

            "raw": self.raw,

        }


# ==========================================================
# Watchlist
# ==========================================================

@dataclass
class ForexWatchlist:

    id: str

    tenant_id: str

    user_id: str

    portfolio_id: Optional[str]

    watchlist_name: str

    is_default: bool = False

    created_at: Optional[datetime] = None

    updated_at: Optional[datetime] = None

    items: List[ForexWatchlistItem] = field(default_factory=list)

    raw: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:

        return {

            "id": self.id,

            "tenant_id": self.tenant_id,

            "user_id": self.user_id,

            "portfolio_id": self.portfolio_id,

            "watchlist_name": self.watchlist_name,

            "is_default": self.is_default,

            "created_at": (
                self.created_at.isoformat()
                if self.created_at
                else None
            ),

            "updated_at": (
                self.updated_at.isoformat()
                if self.updated_at
                else None
            ),

            "items": [

                item.to_dict()

                for item in self.items

            ],

            "raw": self.raw,

        }