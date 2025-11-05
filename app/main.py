"""
FastAPI application factory and configuration.

Creates and configures the FastAPI application with middleware,
error handlers, and route registration.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from typing import AsyncGenerator

from core import (
    settings,
    setup_logging,
    get_logger,
    AppError,
    format_error_response,
    rate_limiter,
)
from api.v1 import health_router, auth_router
from api.v1.routes_chat import router as chat_router
from app.containers import cleanup_services


logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Application lifespan manager.
    
    Handles startup and shutdown events.
    """
    # Startup
    logger.info(
        f"Starting {settings.app_name} v{settings.app_version}",
        extra={
            "environment": settings.environment,
            "debug": settings.debug,
        }
    )
    
    # Configure rate limiter
    if settings.rate_limit_enabled:
        rate_limiter.configure("chat", settings.rate_limit_chat_per_minute)
        rate_limiter.configure("conversations", settings.rate_limit_conversations_per_minute)
        logger.info("Rate limiting enabled")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application")
    cleanup_services()


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application.
    
    Returns:
        Configured FastAPI application
    """
    # Setup logging
    setup_logging(
        level=settings.log_level,
        json_output=settings.environment == "production"
    )
    
    # Create FastAPI app
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Philippine Labor Law Chatbot API",
        docs_url="/api/docs" if settings.debug else None,
        redoc_url="/api/redoc" if settings.debug else None,
        lifespan=lifespan,
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.get_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Register error handlers
    register_error_handlers(app)
    
    # Register routes
    app.include_router(
        health_router,
        prefix="/api/v1",
        tags=["Health"]
    )
    
    app.include_router(
        auth_router,
        prefix="/api/v1",
        tags=["Authentication"]
    )
    
    app.include_router(
        chat_router,
        prefix="/api/v1",
        tags=["Chat"]
    )
    
    return app


def register_error_handlers(app: FastAPI) -> None:
    """
    Register global error handlers.
    
    Args:
        app: FastAPI application
    """
    
    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, 
        exc: RequestValidationError
    ) -> JSONResponse:
        """
        Handle Pydantic validation errors.
        
        Converts FastAPI's default 422 to 400 to match API specification.
        """
        errors = exc.errors()
        first_error = errors[0] if errors else {}
        
        # Extract field name and message
        field = ".".join(str(loc) for loc in first_error.get("loc", []))
        message = first_error.get("msg", "Validation error")
        
        logger.warning(
            f"Validation error: {message}",
            extra={
                "field": field,
                "path": request.url.path,
                "errors": errors
            }
        )
        
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": message,
                    "field": field,
                    "details": {"validation_errors": errors}
                }
            }
        )
    
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        """Handle application errors."""
        logger.error(
            f"Application error: {exc.message}",
            extra={
                "error_code": exc.error_code,
                "status_code": exc.status_code,
                "path": request.url.path,
            },
            exc_info=exc
        )
        
        return JSONResponse(
            status_code=exc.status_code,
            content=format_error_response(exc)
        )
    
    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle unexpected errors."""
        logger.exception(
            f"Unexpected error: {str(exc)}",
            extra={"path": request.url.path}
        )
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred"
                }
            }
        )


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
