"""
Health check endpoints for monitoring and readiness.

Provides basic health checks and readiness probes for
container orchestration platforms.
"""
from fastapi import APIRouter, status
from pydantic import BaseModel
from typing import Literal


router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response model."""
    
    status: Literal["healthy", "unhealthy"]
    version: str
    environment: str


class ReadinessResponse(BaseModel):
    """Readiness check response model."""
    
    ready: bool
    checks: dict[str, bool]


@router.get(
    "/healthz",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health Check",
    description="Basic health check endpoint"
)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.
    
    Returns basic application health status.
    """
    from core import settings
    
    return HealthResponse(
        status="healthy",
        version=settings.app_version,
        environment=settings.environment
    )


@router.get(
    "/readyz",
    response_model=ReadinessResponse,
    status_code=status.HTTP_200_OK,
    summary="Readiness Check",
    description="Readiness probe for container orchestration"
)
async def readiness_check() -> ReadinessResponse:
    """
    Readiness check endpoint.
    
    Verifies that the application is ready to accept traffic.
    In Phase 0, this is a simple check. Future phases will add
    dependency checks (database, external APIs, etc.).
    """
    # Phase 0: Basic readiness check
    # TODO: Add database connectivity check in Phase 1
    # TODO: Add external service checks in later phases
    
    checks = {
        "app": True,  # Application is running
        # Future checks will be added here:
        # "database": await check_database(),
        # "vector_store": await check_vector_store(),
        # "llm": await check_llm_connection(),
    }
    
    return ReadinessResponse(
        ready=all(checks.values()),
        checks=checks
    )
