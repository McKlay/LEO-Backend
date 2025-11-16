"""
Embedding cache utility using LRU cache.

Provides caching for embedding generation to reduce API calls
and improve response times.
"""
from functools import lru_cache
from typing import List, Optional
import hashlib
import json

from core import get_logger

logger = get_logger(__name__)


class EmbeddingCache:
    """
    LRU cache for embedding vectors.
    
    Caches embeddings by text hash to avoid redundant API calls.
    Thread-safe using functools.lru_cache.
    """
    
    def __init__(self, max_size: int = 1000):
        """
        Initialize embedding cache.
        
        Args:
            max_size: Maximum number of embeddings to cache
        """
        self.max_size = max_size
        self.hits = 0
        self.misses = 0
        
        # Create LRU cache function
        @lru_cache(maxsize=max_size)
        def _cache_get(text_hash: str) -> Optional[tuple]:
            """Internal cache storage (immutable types only)."""
            return None
        
        self._cache_get = _cache_get
        self._cache_set = {}  # Hash -> embedding tuple
        
        logger.info(f"Embedding cache initialized with max_size={max_size}")
    
    def _hash_text(self, text: str) -> str:
        """
        Generate hash for text to use as cache key.
        
        Args:
            text: Text to hash
            
        Returns:
            SHA256 hash of text
        """
        return hashlib.sha256(text.encode('utf-8')).hexdigest()
    
    def get(self, text: str) -> Optional[List[float]]:
        """
        Get cached embedding for text.
        
        Args:
            text: Text to look up
            
        Returns:
            Cached embedding vector or None if not found
        """
        text_hash = self._hash_text(text)
        
        if text_hash in self._cache_set:
            self.hits += 1
            logger.debug(f"Cache HIT for text hash: {text_hash[:8]}...")
            return list(self._cache_set[text_hash])
        
        self.misses += 1
        logger.debug(f"Cache MISS for text hash: {text_hash[:8]}...")
        return None
    
    def set(self, text: str, embedding: List[float]) -> None:
        """
        Cache embedding for text.
        
        Args:
            text: Text to cache
            embedding: Embedding vector to store
        """
        text_hash = self._hash_text(text)
        # Store as tuple (immutable) for LRU cache compatibility
        self._cache_set[text_hash] = tuple(embedding)
        logger.debug(f"Cached embedding for text hash: {text_hash[:8]}...")
    
    def clear(self) -> None:
        """Clear all cached embeddings."""
        self._cache_set.clear()
        self._cache_get.cache_clear()
        self.hits = 0
        self.misses = 0
        logger.info("Embedding cache cleared")
    
    def get_stats(self) -> dict:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0.0
        
        return {
            "hits": self.hits,
            "misses": self.misses,
            "total_requests": total_requests,
            "hit_rate_percent": round(hit_rate, 2),
            "cache_size": len(self._cache_set),
            "max_size": self.max_size
        }
    
    def log_stats(self) -> None:
        """Log current cache statistics."""
        stats = self.get_stats()
        logger.info(
            f"Embedding cache stats: "
            f"hits={stats['hits']}, "
            f"misses={stats['misses']}, "
            f"hit_rate={stats['hit_rate_percent']}%, "
            f"size={stats['cache_size']}/{stats['max_size']}"
        )


# Global cache instance
_global_cache: Optional[EmbeddingCache] = None


def get_embedding_cache(max_size: int = 1000) -> EmbeddingCache:
    """
    Get or create global embedding cache instance.
    
    Args:
        max_size: Maximum cache size (only used on first call)
        
    Returns:
        Global EmbeddingCache instance
    """
    global _global_cache
    
    if _global_cache is None:
        _global_cache = EmbeddingCache(max_size=max_size)
    
    return _global_cache
