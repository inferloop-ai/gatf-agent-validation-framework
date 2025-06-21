"""
GATF Rate Limiting Utilities

This module provides rate limiting functionality for the GATF framework,
including various rate limiting algorithms and distributed rate limiting.
"""

import time
import threading
from typing import Dict, Optional, Tuple, Union, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import wraps
from collections import deque
import redis
from enum import Enum


class RateLimitAlgorithm(Enum):
    """Supported rate limiting algorithms"""
    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"
    LEAKY_BUCKET = "leaky_bucket"


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded"""
    def __init__(self, message: str, retry_after: Optional[float] = None):
        super().__init__(message)
        self.retry_after = retry_after


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting"""
    max_requests: int
    time_window: int  # seconds
    algorithm: RateLimitAlgorithm = RateLimitAlgorithm.TOKEN_BUCKET
    burst_size: Optional[int] = None  # For token bucket
    strict: bool = True  # Whether to raise exception or just return False


class TokenBucket:
    """Token bucket rate limiter implementation"""
    
    def __init__(self, capacity: int, refill_rate: float, burst_size: Optional[int] = None):
        """
        Initialize token bucket
        
        Args:
            capacity: Maximum number of tokens
            refill_rate: Tokens per second
            burst_size: Maximum burst size (defaults to capacity)
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.burst_size = burst_size or capacity
        self.tokens = float(capacity)
        self.last_refill = time.time()
        self._lock = threading.Lock()
    
    def consume(self, tokens: int = 1) -> Tuple[bool, Optional[float]]:
        """
        Try to consume tokens
        
        Returns:
            Tuple of (success, retry_after_seconds)
        """
        with self._lock:
            self._refill()
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True, None
            
            # Calculate when enough tokens will be available
            tokens_needed = tokens - self.tokens
            retry_after = tokens_needed / self.refill_rate
            
            return False, retry_after
    
    def _refill(self):
        """Refill tokens based on elapsed time"""
        now = time.time()
        elapsed = now - self.last_refill
        
        tokens_to_add = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now


class SlidingWindow:
    """Sliding window rate limiter implementation"""
    
    def __init__(self, max_requests: int, time_window: int):
        """
        Initialize sliding window
        
        Args:
            max_requests: Maximum requests in window
            time_window: Window size in seconds
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests: deque = deque()
        self._lock = threading.Lock()
    
    def consume(self) -> Tuple[bool, Optional[float]]:
        """
        Try to consume a request slot
        
        Returns:
            Tuple of (success, retry_after_seconds)
        """
        with self._lock:
            now = time.time()
            cutoff = now - self.time_window
            
            # Remove old requests
            while self.requests and self.requests[0] < cutoff:
                self.requests.popleft()
            
            if len(self.requests) < self.max_requests:
                self.requests.append(now)
                return True, None
            
            # Calculate retry after
            oldest_request = self.requests[0]
            retry_after = oldest_request + self.time_window - now
            
            return False, retry_after


class FixedWindow:
    """Fixed window rate limiter implementation"""
    
    def __init__(self, max_requests: int, time_window: int):
        """
        Initialize fixed window
        
        Args:
            max_requests: Maximum requests per window
            time_window: Window size in seconds
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.window_start = time.time()
        self.request_count = 0
        self._lock = threading.Lock()
    
    def consume(self) -> Tuple[bool, Optional[float]]:
        """
        Try to consume a request slot
        
        Returns:
            Tuple of (success, retry_after_seconds)
        """
        with self._lock:
            now = time.time()
            
            # Check if we need to reset the window
            if now - self.window_start >= self.time_window:
                self.window_start = now
                self.request_count = 0
            
            if self.request_count < self.max_requests:
                self.request_count += 1
                return True, None
            
            # Calculate retry after
            retry_after = self.window_start + self.time_window - now
            
            return False, retry_after


class LeakyBucket:
    """Leaky bucket rate limiter implementation"""
    
    def __init__(self, capacity: int, leak_rate: float):
        """
        Initialize leaky bucket
        
        Args:
            capacity: Maximum bucket capacity
            leak_rate: Requests per second that leak out
        """
        self.capacity = capacity
        self.leak_rate = leak_rate
        self.water_level = 0.0
        self.last_leak = time.time()
        self._lock = threading.Lock()
    
    def consume(self, amount: float = 1.0) -> Tuple[bool, Optional[float]]:
        """
        Try to add water to bucket
        
        Returns:
            Tuple of (success, retry_after_seconds)
        """
        with self._lock:
            self._leak()
            
            if self.water_level + amount <= self.capacity:
                self.water_level += amount
                return True, None
            
            # Calculate when there will be enough capacity
            overflow = (self.water_level + amount) - self.capacity
            retry_after = overflow / self.leak_rate
            
            return False, retry_after
    
    def _leak(self):
        """Leak water based on elapsed time"""
        now = time.time()
        elapsed = now - self.last_leak
        
        leak_amount = elapsed * self.leak_rate
        self.water_level = max(0, self.water_level - leak_amount)
        self.last_leak = now


class RateLimiter:
    """Main rate limiter class supporting multiple algorithms"""
    
    def __init__(self, config: RateLimitConfig):
        """
        Initialize rate limiter
        
        Args:
            config: Rate limit configuration
        """
        self.config = config
        self._limiter = self._create_limiter()
    
    def _create_limiter(self) -> Union[TokenBucket, SlidingWindow, FixedWindow, LeakyBucket]:
        """Create the appropriate limiter based on algorithm"""
        if self.config.algorithm == RateLimitAlgorithm.TOKEN_BUCKET:
            refill_rate = self.config.max_requests / self.config.time_window
            return TokenBucket(
                capacity=self.config.max_requests,
                refill_rate=refill_rate,
                burst_size=self.config.burst_size
            )
        
        elif self.config.algorithm == RateLimitAlgorithm.SLIDING_WINDOW:
            return SlidingWindow(
                max_requests=self.config.max_requests,
                time_window=self.config.time_window
            )
        
        elif self.config.algorithm == RateLimitAlgorithm.FIXED_WINDOW:
            return FixedWindow(
                max_requests=self.config.max_requests,
                time_window=self.config.time_window
            )
        
        elif self.config.algorithm == RateLimitAlgorithm.LEAKY_BUCKET:
            leak_rate = self.config.max_requests / self.config.time_window
            return LeakyBucket(
                capacity=self.config.max_requests,
                leak_rate=leak_rate
            )
        
        else:
            raise ValueError(f"Unsupported algorithm: {self.config.algorithm}")
    
    def check_and_consume(self, tokens: int = 1) -> bool:
        """
        Check if request is allowed and consume tokens
        
        Args:
            tokens: Number of tokens to consume
        
        Returns:
            True if allowed, False otherwise
        
        Raises:
            RateLimitExceeded: If strict mode and limit exceeded
        """
        # Handle different limiter types
        if isinstance(self._limiter, TokenBucket):
            allowed, retry_after = self._limiter.consume(tokens)
        elif isinstance(self._limiter, LeakyBucket):
            allowed, retry_after = self._limiter.consume(float(tokens))
        else:
            allowed, retry_after = self._limiter.consume()
        
        if not allowed and self.config.strict:
            raise RateLimitExceeded(
                f"Rate limit exceeded: {self.config.max_requests} requests per {self.config.time_window}s",
                retry_after=retry_after
            )
        
        return allowed
    
    def get_remaining_tokens(self) -> Optional[int]:
        """Get remaining tokens (if applicable)"""
        if isinstance(self._limiter, TokenBucket):
            return int(self._limiter.tokens)
        elif isinstance(self._limiter, FixedWindow):
            return max(0, self.config.max_requests - self._limiter.request_count)
        return None


class RedisRateLimiter:
    """Distributed rate limiter using Redis"""
    
    def __init__(
        self,
        redis_client: redis.Redis,
        key_prefix: str = "gatf:ratelimit:",
        config: RateLimitConfig = None
    ):
        """
        Initialize Redis rate limiter
        
        Args:
            redis_client: Redis client instance
            key_prefix: Prefix for Redis keys
            config: Default rate limit configuration
        """
        self.redis = redis_client
        self.key_prefix = key_prefix
        self.default_config = config
    
    def check_and_consume(
        self,
        key: str,
        config: Optional[RateLimitConfig] = None,
        tokens: int = 1
    ) -> bool:
        """
        Check if request is allowed and consume tokens
        
        Args:
            key: Rate limit key (e.g., user ID, IP address)
            config: Rate limit configuration (uses default if not provided)
            tokens: Number of tokens to consume
        
        Returns:
            True if allowed, False otherwise
        """
        config = config or self.default_config
        if not config:
            raise ValueError("No rate limit configuration provided")
        
        if config.algorithm == RateLimitAlgorithm.SLIDING_WINDOW:
            return self._sliding_window_check(key, config, tokens)
        elif config.algorithm == RateLimitAlgorithm.FIXED_WINDOW:
            return self._fixed_window_check(key, config, tokens)
        else:
            # Token bucket implementation for Redis
            return self._token_bucket_check(key, config, tokens)
    
    def _sliding_window_check(self, key: str, config: RateLimitConfig, tokens: int) -> bool:
        """Sliding window implementation using Redis sorted sets"""
        redis_key = f"{self.key_prefix}sliding:{key}"
        now = time.time()
        window_start = now - config.time_window
        
        # Use Redis pipeline for atomic operations
        pipe = self.redis.pipeline()
        
        # Remove old entries
        pipe.zremrangebyscore(redis_key, 0, window_start)
        
        # Count current entries
        pipe.zcard(redis_key)
        
        # Execute pipeline
        _, current_count = pipe.execute()
        
        if current_count + tokens <= config.max_requests:
            # Add new entries
            pipe = self.redis.pipeline()
            for i in range(tokens):
                pipe.zadd(redis_key, {f"{now}:{i}": now})
            pipe.expire(redis_key, config.time_window + 60)  # Add buffer
            pipe.execute()
            return True
        
        if config.strict:
            raise RateLimitExceeded(
                f"Rate limit exceeded: {config.max_requests} requests per {config.time_window}s"
            )
        
        return False
    
    def _fixed_window_check(self, key: str, config: RateLimitConfig, tokens: int) -> bool:
        """Fixed window implementation using Redis"""
        # Calculate window key based on time
        window_id = int(time.time() / config.time_window)
        redis_key = f"{self.key_prefix}fixed:{key}:{window_id}"
        
        # Increment counter
        current = self.redis.incrby(redis_key, tokens)
        
        if current == tokens:
            # First request in this window, set expiry
            self.redis.expire(redis_key, config.time_window + 60)
        
        if current <= config.max_requests:
            return True
        
        # Rollback the increment
        self.redis.decrby(redis_key, tokens)
        
        if config.strict:
            raise RateLimitExceeded(
                f"Rate limit exceeded: {config.max_requests} requests per {config.time_window}s"
            )
        
        return False
    
    def _token_bucket_check(self, key: str, config: RateLimitConfig, tokens: int) -> bool:
        """Token bucket implementation using Redis"""
        redis_key = f"{self.key_prefix}token:{key}"
        refill_rate = config.max_requests / config.time_window
        
        # Lua script for atomic token bucket operations
        lua_script = """
        local key = KEYS[1]
        local capacity = tonumber(ARGV[1])
        local refill_rate = tonumber(ARGV[2])
        local tokens_requested = tonumber(ARGV[3])
        local now = tonumber(ARGV[4])
        
        local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
        local current_tokens = tonumber(bucket[1]) or capacity
        local last_refill = tonumber(bucket[2]) or now
        
        -- Refill tokens
        local elapsed = now - last_refill
        local tokens_to_add = elapsed * refill_rate
        current_tokens = math.min(capacity, current_tokens + tokens_to_add)
        
        -- Check if we can consume
        if current_tokens >= tokens_requested then
            current_tokens = current_tokens - tokens_requested
            redis.call('HMSET', key, 'tokens', current_tokens, 'last_refill', now)
            redis.call('EXPIRE', key, ARGV[5])
            return 1
        else
            -- Update refill time even if we can't consume
            redis.call('HMSET', key, 'tokens', current_tokens, 'last_refill', now)
            redis.call('EXPIRE', key, ARGV[5])
            return 0
        end
        """
        
        allowed = self.redis.eval(
            lua_script,
            1,
            redis_key,
            config.max_requests,
            refill_rate,
            tokens,
            time.time(),
            config.time_window + 60
        )
        
        if not allowed and config.strict:
            raise RateLimitExceeded(
                f"Rate limit exceeded: {config.max_requests} requests per {config.time_window}s"
            )
        
        return bool(allowed)


def rate_limit(
    max_requests: int,
    time_window: int,
    algorithm: Union[RateLimitAlgorithm, str] = RateLimitAlgorithm.TOKEN_BUCKET,
    key_func: Optional[Callable] = None,
    strict: bool = True
):
    """
    Decorator for rate limiting functions
    
    Args:
        max_requests: Maximum requests allowed
        time_window: Time window in seconds
        algorithm: Rate limiting algorithm
        key_func: Function to generate rate limit key
        strict: Whether to raise exception on rate limit
    
    Example:
        @rate_limit(max_requests=10, time_window=60)
        def api_endpoint(user_id):
            pass
    """
    if isinstance(algorithm, str):
        algorithm = RateLimitAlgorithm(algorithm)
    
    # Create rate limiter instances per key
    limiters: Dict[str, RateLimiter] = {}
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate key
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                key = "global"
            
            # Get or create limiter for this key
            if key not in limiters:
                config = RateLimitConfig(
                    max_requests=max_requests,
                    time_window=time_window,
                    algorithm=algorithm,
                    strict=strict
                )
                limiters[key] = RateLimiter(config)
            
            # Check rate limit
            limiters[key].check_and_consume()
            
            # Execute function
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


def check_rate_limit(
    key: str,
    max_requests: int,
    time_window: int,
    redis_client: Optional[redis.Redis] = None
) -> bool:
    """
    Check if a request is allowed under rate limit
    
    Args:
        key: Rate limit key
        max_requests: Maximum requests allowed
        time_window: Time window in seconds
        redis_client: Optional Redis client for distributed limiting
    
    Returns:
        True if allowed, False otherwise
    """
    config = RateLimitConfig(
        max_requests=max_requests,
        time_window=time_window,
        strict=False
    )
    
    if redis_client:
        limiter = RedisRateLimiter(redis_client, config=config)
        return limiter.check_and_consume(key)
    else:
        # Use in-memory limiter
        limiter = RateLimiter(config)
        return limiter.check_and_consume()


# Global rate limiter instances
_rate_limiters: Dict[str, RateLimiter] = {}
_redis_rate_limiter: Optional[RedisRateLimiter] = None


def get_rate_limiter(key: str, config: RateLimitConfig) -> RateLimiter:
    """Get or create a rate limiter for a key"""
    if key not in _rate_limiters:
        _rate_limiters[key] = RateLimiter(config)
    return _rate_limiters[key]


def set_redis_rate_limiter(redis_client: redis.Redis, key_prefix: str = "gatf:ratelimit:"):
    """Set up Redis rate limiter"""
    global _redis_rate_limiter
    _redis_rate_limiter = RedisRateLimiter(redis_client, key_prefix)