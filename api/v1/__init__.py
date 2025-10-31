"""API v1 routes."""

from api.v1.routes_health import router as health_router
from api.v1.routes_auth import router as auth_router

__all__ = ["health_router", "auth_router"]
