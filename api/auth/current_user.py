"""
Backward compatibility.

Current user dependency.
"""

from api.auth.dependencies import get_current_user

__all__ = [
    "get_current_user",
]