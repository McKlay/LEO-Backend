"""
Dependency injection container for service instances.

Provides factory functions for creating and managing service dependencies.
"""
from functools import lru_cache
from supabase import create_client, Client

from core import settings, get_logger
from services.auth import SessionService

logger = get_logger(__name__)


# Supabase client singleton
_supabase_client: Client = None


def get_supabase_client() -> Client:
    """
    Get or create Supabase client singleton.
    
    Returns:
        Initialized Supabase client
    """
    global _supabase_client
    
    if _supabase_client is None:
        logger.info("Initializing Supabase client")
        _supabase_client = create_client(
            supabase_url=settings.supabase_url,
            supabase_key=settings.supabase_key
        )
        logger.info("Supabase client initialized successfully")
    
    return _supabase_client


@lru_cache()
def get_session_service() -> SessionService:
    """
    Get or create SessionService singleton.
    
    Returns:
        Initialized SessionService instance
    """
    supabase_client = get_supabase_client()
    return SessionService(supabase_client, settings)


def cleanup_services():
    """
    Cleanup service instances and connections.
    
    Should be called during application shutdown.
    """
    global _supabase_client
    
    logger.info("Cleaning up service instances")
    
    # Clear LRU cache
    get_session_service.cache_clear()
    
    # Reset Supabase client
    _supabase_client = None
    
    logger.info("Service cleanup completed")
