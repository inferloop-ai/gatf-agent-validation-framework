"""
GATF Caching Utilities

This module provides caching functionality for the GATF framework,
including in-memory caching, distributed caching, and cache management.
"""

import time
import hashlib
import json
import pickle
from typing import Any, Optional, Union, Callable, Dict, List, Tuple
from datetime import datetime, timedelta
from functools import wraps
from collections import OrderedDict
import threading
import redis
from dataclasses import dataclass
from enum import Enum


class CacheBackend(Enum):
    """Supported cache backends"""
    MEMORY = "memory"
    REDIS = "redis"
    HYBRID = "hybrid"  # Memory + Redis


class CacheError(Exception):
    """Raised when cache operations fail"""
    pass


@dataclass
class CacheEntry:
    """Represents a cached entry"""
    key: str
    value: Any
    created_at: float
    ttl: Optional[int]
    access_count: int = 0
    last_accessed: Optional[float] = None
    
    @property
    def is_expired(self) -> bool:
        """Check if the cache entry has expired"""
        if self.ttl is None:
            return False
        return time.time() - self.created_at > self.ttl
    
    def touch(self):
        """Update access statistics"""
        self.access_count += 1
        self.last_accessed = time.time()


class MemoryCache:
    """Thread-safe in-memory cache implementation"""
    
    def __init__(self, max_size: int = 1000, eviction_policy: str = "lru"):
        """
        Initialize memory cache
        
        Args:
            max_size: Maximum number of entries
            eviction_policy: Eviction policy ("lru", "lfu", "fifo")
        """
        self.max_size = max_size
        self.eviction_policy = eviction_policy
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "sets": 0
        }
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                self._stats["misses"] += 1
                return None
            
            if entry.is_expired:
                self._cache.pop(key)
                self._stats["misses"] += 1
                return None
            
            entry.touch()
            self._stats["hits"] += 1
            
            # Move to end for LRU
            if self.eviction_policy == "lru":
                self._cache.move_to_end(key)
            
            return entry.value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set value in cache"""
        with self._lock:
            # Check if we need to evict
            if len(self._cache) >= self.max_size and key not in self._cache:
                self._evict()
            
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=time.time(),
                ttl=ttl
            )
            
            self._cache[key] = entry
            self._stats["sets"] += 1
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        with self._lock:
            if key in self._cache:
                self._cache.pop(key)
                return True
            return False
    
    def clear(self):
        """Clear all cache entries"""
        with self._lock:
            self._cache.clear()
    
    def _evict(self):
        """Evict entry based on eviction policy"""
        if not self._cache:
            return
        
        if self.eviction_policy == "lru":
            # Remove least recently used (first item)
            self._cache.popitem(last=False)
        elif self.eviction_policy == "lfu":
            # Remove least frequently used
            min_entry = min(self._cache.values(), key=lambda e: e.access_count)
            self._cache.pop(min_entry.key)
        elif self.eviction_policy == "fifo":
            # Remove oldest entry
            self._cache.popitem(last=False)
        
        self._stats["evictions"] += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            total_requests = self._stats["hits"] + self._stats["misses"]
            hit_rate = self._stats["hits"] / total_requests if total_requests > 0 else 0
            
            return {
                **self._stats,
                "size": len(self._cache),
                "hit_rate": hit_rate,
                "max_size": self.max_size
            }


class RedisCache:
    """Redis-based cache implementation"""
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        key_prefix: str = "gatf:",
        default_ttl: int = 3600
    ):
        """
        Initialize Redis cache
        
        Args:
            host: Redis host
            port: Redis port
            db: Redis database number
            password: Redis password
            key_prefix: Prefix for all keys
            default_ttl: Default TTL in seconds
        """
        self.key_prefix = key_prefix
        self.default_ttl = default_ttl
        
        try:
            self.client = redis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=False
            )
            # Test connection
            self.client.ping()
        except Exception as e:
            raise CacheError(f"Failed to connect to Redis: {str(e)}")
    
    def _make_key(self, key: str) -> str:
        """Create prefixed key"""
        return f"{self.key_prefix}{key}"
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            full_key = self._make_key(key)
            data = self.client.get(full_key)
            
            if data is None:
                return None
            
            return pickle.loads(data)
        except Exception as e:
            raise CacheError(f"Failed to get from cache: {str(e)}")
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set value in cache"""
        try:
            full_key = self._make_key(key)
            data = pickle.dumps(value)
            
            if ttl is None:
                ttl = self.default_ttl
            
            if ttl > 0:
                self.client.setex(full_key, ttl, data)
            else:
                self.client.set(full_key, data)
        except Exception as e:
            raise CacheError(f"Failed to set in cache: {str(e)}")
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        try:
            full_key = self._make_key(key)
            return bool(self.client.delete(full_key))
        except Exception as e:
            raise CacheError(f"Failed to delete from cache: {str(e)}")
    
    def clear(self, pattern: str = "*"):
        """Clear cache entries matching pattern"""
        try:
            full_pattern = self._make_key(pattern)
            keys = self.client.keys(full_pattern)
            if keys:
                self.client.delete(*keys)
        except Exception as e:
            raise CacheError(f"Failed to clear cache: {str(e)}")


class CacheManager:
    """Unified cache manager supporting multiple backends"""
    
    def __init__(
        self,
        backend: CacheBackend = CacheBackend.MEMORY,
        memory_config: Optional[Dict[str, Any]] = None,
        redis_config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize cache manager
        
        Args:
            backend: Cache backend to use
            memory_config: Configuration for memory cache
            redis_config: Configuration for Redis cache
        """
        self.backend = backend
        
        # Initialize memory cache
        if backend in [CacheBackend.MEMORY, CacheBackend.HYBRID]:
            memory_config = memory_config or {}
            self.memory_cache = MemoryCache(**memory_config)
        else:
            self.memory_cache = None
        
        # Initialize Redis cache
        if backend in [CacheBackend.REDIS, CacheBackend.HYBRID]:
            redis_config = redis_config or {}
            self.redis_cache = RedisCache(**redis_config)
        else:
            self.redis_cache = None
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if self.backend == CacheBackend.MEMORY:
            return self.memory_cache.get(key)
        
        elif self.backend == CacheBackend.REDIS:
            return self.redis_cache.get(key)
        
        elif self.backend == CacheBackend.HYBRID:
            # Try memory cache first
            value = self.memory_cache.get(key)
            if value is not None:
                return value
            
            # Try Redis cache
            value = self.redis_cache.get(key)
            if value is not None:
                # Populate memory cache
                self.memory_cache.set(key, value)
            
            return value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set value in cache"""
        if self.backend == CacheBackend.MEMORY:
            self.memory_cache.set(key, value, ttl)
        
        elif self.backend == CacheBackend.REDIS:
            self.redis_cache.set(key, value, ttl)
        
        elif self.backend == CacheBackend.HYBRID:
            # Set in both caches
            self.memory_cache.set(key, value, ttl)
            self.redis_cache.set(key, value, ttl)
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if self.backend == CacheBackend.MEMORY:
            return self.memory_cache.delete(key)
        
        elif self.backend == CacheBackend.REDIS:
            return self.redis_cache.delete(key)
        
        elif self.backend == CacheBackend.HYBRID:
            # Delete from both caches
            memory_result = self.memory_cache.delete(key)
            redis_result = self.redis_cache.delete(key)
            return memory_result or redis_result
    
    def clear(self):
        """Clear all cache entries"""
        if self.memory_cache:
            self.memory_cache.clear()
        
        if self.redis_cache:
            self.redis_cache.clear()


def cache_key(*args, **kwargs) -> str:
    """
    Generate cache key from arguments
    
    Args:
        *args: Positional arguments
        **kwargs: Keyword arguments
    
    Returns:
        Cache key string
    """
    # Create a string representation of arguments
    key_parts = []
    
    # Add positional arguments
    for arg in args:
        if isinstance(arg, (str, int, float, bool)):
            key_parts.append(str(arg))
        else:
            # Use hash for complex objects
            key_parts.append(hashlib.md5(str(arg).encode()).hexdigest()[:8])
    
    # Add keyword arguments (sorted for consistency)
    for k, v in sorted(kwargs.items()):
        if isinstance(v, (str, int, float, bool)):
            key_parts.append(f"{k}={v}")
        else:
            key_parts.append(f"{k}={hashlib.md5(str(v).encode()).hexdigest()[:8]}")
    
    return ":".join(key_parts)


def cached(
    cache_manager: Optional[CacheManager] = None,
    ttl: Optional[int] = None,
    key_prefix: Optional[str] = None,
    key_func: Optional[Callable] = None
):
    """
    Decorator for caching function results
    
    Args:
        cache_manager: Cache manager instance (uses global if not provided)
        ttl: Time to live in seconds
        key_prefix: Prefix for cache keys
        key_func: Custom key generation function
    
    Example:
        @cached(ttl=3600)
        def expensive_function(x, y):
            return x + y
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get cache manager
            nonlocal cache_manager
            if cache_manager is None:
                cache_manager = get_cache_manager()
            
            # Generate cache key
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                func_key = cache_key(func.__name__, *args, **kwargs)
                key = f"{key_prefix}:{func_key}" if key_prefix else func_key
            
            # Try to get from cache
            result = cache_manager.get(key)
            if result is not None:
                return result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache_manager.set(key, result, ttl)
            
            return result
        
        return wrapper
    return decorator


def invalidate_cache(
    cache_manager: Optional[CacheManager] = None,
    pattern: Optional[str] = None,
    keys: Optional[List[str]] = None
):
    """
    Invalidate cache entries
    
    Args:
        cache_manager: Cache manager instance
        pattern: Pattern to match keys (Redis only)
        keys: Specific keys to invalidate
    """
    if cache_manager is None:
        cache_manager = get_cache_manager()
    
    if keys:
        for key in keys:
            cache_manager.delete(key)
    elif pattern and hasattr(cache_manager, 'redis_cache'):
        cache_manager.redis_cache.clear(pattern)
    else:
        cache_manager.clear()


class CacheWarmer:
    """Utility for warming up cache with precomputed values"""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache_manager = cache_manager
        self.tasks: List[Tuple[Callable, Tuple, Dict, str, Optional[int]]] = []
    
    def add_task(
        self,
        func: Callable,
        args: Tuple = (),
        kwargs: Dict = None,
        key: Optional[str] = None,
        ttl: Optional[int] = None
    ):
        """Add a task to warm up"""
        kwargs = kwargs or {}
        if key is None:
            key = cache_key(func.__name__, *args, **kwargs)
        
        self.tasks.append((func, args, kwargs, key, ttl))
    
    def warm_up(self, parallel: bool = False):
        """Execute all warm-up tasks"""
        if parallel:
            import concurrent.futures
            
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = []
                for func, args, kwargs, key, ttl in self.tasks:
                    future = executor.submit(self._warm_single, func, args, kwargs, key, ttl)
                    futures.append(future)
                
                concurrent.futures.wait(futures)
        else:
            for func, args, kwargs, key, ttl in self.tasks:
                self._warm_single(func, args, kwargs, key, ttl)
    
    def _warm_single(self, func: Callable, args: Tuple, kwargs: Dict, key: str, ttl: Optional[int]):
        """Warm up a single cache entry"""
        try:
            result = func(*args, **kwargs)
            self.cache_manager.set(key, result, ttl)
        except Exception as e:
            # Log error but don't stop warm-up process
            pass


# Global cache manager instance
_cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """Get or create global cache manager"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager


def set_cache_manager(cache_manager: CacheManager):
    """Set global cache manager"""
    global _cache_manager
    _cache_manager = cache_manager