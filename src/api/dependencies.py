"""FastAPI dependencies for caching, rate limiting, etc."""

from functools import wraps
from typing import Optional, Callable, Any
import hashlib
import json
from datetime import datetime, timedelta
import asyncio
import structlog

from src.storage.redis_client_v2 import redis_client_v2

logger = structlog.get_logger(__name__)


class CacheManager:
    """Caching manager using Redis"""

    def __init__(self):
        self.client = redis_client_v2

    def _generate_cache_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate cache key from function arguments"""
        key_data = f"{prefix}:{json.dumps(args, sort_keys=True, default=str)}:{json.dumps(kwargs, sort_keys=True, default=str)}"
        key_hash = hashlib.md5(key_data.encode()).hexdigest()
        return f"cache:{prefix}:{key_hash}"

    async def get(self, key: str) -> Optional[Any]:
        """Get cached value"""
        try:
            data = await self.client.client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.warning("Cache get failed", key=key, error=str(e))
            return None

    async def set(self, key: str, value: Any, ttl: int) -> bool:
        """Set cached value with TTL"""
        try:
            await self.client.client.setex(
                key,
                ttl,
                json.dumps(value, default=str)
            )
            return True
        except Exception as e:
            logger.warning("Cache set failed", key=key, error=str(e))
            return False

    def cached(self, prefix: str, ttl: int):
        """Decorator for caching function results"""
        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Generate cache key
                cache_key = self._generate_cache_key(prefix, *args, **kwargs)

                # Try to get from cache
                cached_value = await self.get(cache_key)
                if cached_value is not None:
                    logger.debug("Cache hit", key=cache_key)
                    return cached_value

                # Execute function
                logger.debug("Cache miss", key=cache_key)
                result = await func(*args, **kwargs)

                # Cache result
                await self.set(cache_key, result, ttl)

                return result

            return wrapper
        return decorator


# Global cache manager instance
cache_manager = CacheManager()


def with_retry(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """
    Retry decorator with exponential backoff

    Args:
        max_retries: Maximum number of retries
        delay: Initial delay in seconds
        backoff: Backoff multiplier
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(
                            "Function failed, retrying",
                            function=func.__name__,
                            attempt=attempt + 1,
                            max_retries=max_retries,
                            error=str(e)
                        )
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(
                            "Function failed after max retries",
                            function=func.__name__,
                            max_retries=max_retries,
                            error=str(e)
                        )

            raise last_exception

        return wrapper
    return decorator


class RateLimiter:
    """Simple rate limiter using Redis"""

    def __init__(self, requests_per_minute: int = 60):
        self.client = redis_client_v2
        self.requests_per_minute = requests_per_minute

    async def check_rate_limit(self, identifier: str) -> bool:
        """
        Check if request is within rate limit

        Args:
            identifier: Unique identifier (IP, user ID, etc.)

        Returns:
            True if allowed, False if rate limited
        """
        try:
            key = f"ratelimit:{identifier}"
            current = await self.client.client.get(key)

            if current is None:
                # First request in this window
                await self.client.client.setex(key, 60, "1")
                return True

            count = int(current)
            if count >= self.requests_per_minute:
                logger.warning("Rate limit exceeded", identifier=identifier, count=count)
                return False

            # Increment counter
            await self.client.client.incr(key)
            return True

        except Exception as e:
            logger.error("Rate limit check failed", error=str(e))
            # Fail open - allow request if rate limit check fails
            return True


# Global rate limiter instance
rate_limiter = RateLimiter(requests_per_minute=60)
