"""
Rate limiting implementation using token bucket algorithm.

Provides configurable rate limiting for API endpoints with
Redis backend support (optional).
"""
import time
from typing import Optional
from collections import defaultdict
from threading import Lock

from core.exceptions import RateLimitError


class TokenBucket:
    """Token bucket algorithm for rate limiting."""
    
    def __init__(self, capacity: int, refill_rate: float):
        """
        Initialize token bucket.
        
        Args:
            capacity: Maximum number of tokens
            refill_rate: Tokens added per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.time()
        self.lock = Lock()
    
    def consume(self, tokens: int = 1) -> bool:
        """
        Attempt to consume tokens.
        
        Args:
            tokens: Number of tokens to consume
            
        Returns:
            True if tokens consumed, False otherwise
        """
        with self.lock:
            self._refill()
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False
    
    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        
        # Add tokens based on elapsed time
        tokens_to_add = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now
    
    def time_until_available(self, tokens: int = 1) -> float:
        """
        Calculate time until tokens are available.
        
        Args:
            tokens: Number of tokens needed
            
        Returns:
            Seconds until tokens available
        """
        with self.lock:
            self._refill()
            
            if self.tokens >= tokens:
                return 0.0
            
            tokens_needed = tokens - self.tokens
            return tokens_needed / self.refill_rate


class RateLimiter:
    """
    In-memory rate limiter with token bucket algorithm.
    
    Note: This is a simple in-memory implementation. For production
    with multiple instances, consider using Redis-backed rate limiting.
    """
    
    def __init__(self):
        """Initialize rate limiter."""
        self.buckets: dict[str, TokenBucket] = {}
        self.bucket_configs: dict[str, tuple[int, float]] = {}
        self.lock = Lock()
    
    def configure(self, key: str, requests_per_minute: int) -> None:
        """
        Configure rate limit for a key pattern.
        
        Args:
            key: Rate limit key pattern
            requests_per_minute: Maximum requests per minute
        """
        capacity = requests_per_minute
        refill_rate = requests_per_minute / 60.0
        self.bucket_configs[key] = (capacity, refill_rate)
    
    def check_limit(
        self,
        identifier: str,
        limit_type: str = "default"
    ) -> None:
        """
        Check if request is within rate limit.
        
        Args:
            identifier: Unique identifier (session_id, IP, etc.)
            limit_type: Type of rate limit to apply
            
        Raises:
            RateLimitError: If rate limit exceeded
        """
        bucket_key = f"{limit_type}:{identifier}"
        
        # Get or create bucket
        with self.lock:
            if bucket_key not in self.buckets:
                config = self.bucket_configs.get(limit_type)
                if not config:
                    # No rate limit configured
                    return
                
                capacity, refill_rate = config
                self.buckets[bucket_key] = TokenBucket(capacity, refill_rate)
        
        bucket = self.buckets[bucket_key]
        
        # Try to consume token
        if not bucket.consume():
            retry_after = int(bucket.time_until_available() + 1)
            raise RateLimitError(
                message="Rate limit exceeded. Please try again later.",
                retry_after=retry_after
            )
    
    def get_remaining(
        self,
        identifier: str,
        limit_type: str = "default"
    ) -> Optional[int]:
        """
        Get remaining requests for identifier.
        
        Args:
            identifier: Unique identifier
            limit_type: Type of rate limit
            
        Returns:
            Remaining requests or None if not configured
        """
        bucket_key = f"{limit_type}:{identifier}"
        
        if bucket_key in self.buckets:
            bucket = self.buckets[bucket_key]
            with bucket.lock:
                bucket._refill()
                return int(bucket.tokens)
        
        # Return capacity if bucket doesn't exist yet
        config = self.bucket_configs.get(limit_type)
        if config:
            return config[0]  # capacity
        
        return None


# Global rate limiter instance
rate_limiter = RateLimiter()
