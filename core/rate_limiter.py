"""
Advanced Rate Limiting System
Provides intelligent rate limiting across all APIs with dynamic adjustment and backoff strategies.
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
import threading
import logging
from collections import deque, defaultdict
import math
import json
from pathlib import Path

class RateLimitStrategy(Enum):
    """Rate limiting strategies"""
    FIXED_WINDOW = "fixed_window"
    SLIDING_WINDOW = "sliding_window"
    TOKEN_BUCKET = "token_bucket"
    LEAKY_BUCKET = "leaky_bucket"
    ADAPTIVE = "adaptive"

class BackoffStrategy(Enum):
    """Backoff strategies for rate limit handling"""
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    FIBONACCI = "fibonacci"
    CUSTOM = "custom"

@dataclass
class RateLimitConfig:
    """Configuration for rate limiting"""
    max_requests: int
    time_window_seconds: int
    strategy: RateLimitStrategy = RateLimitStrategy.SLIDING_WINDOW
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    backoff_base: float = 2.0
    max_backoff_seconds: int = 300
    burst_allowance: int = 0
    adaptive_factor: float = 0.1
    quota_reset_hour: Optional[int] = None  # Daily quota reset hour (UTC)

@dataclass
class RateLimitStats:
    """Rate limiting statistics"""
    total_requests: int = 0
    successful_requests: int = 0
    rate_limited_requests: int = 0
    total_wait_time: float = 0.0
    average_wait_time: float = 0.0
    current_backoff_level: int = 0
    quota_remaining: Optional[int] = None
    quota_reset_time: Optional[datetime] = None
    last_request_time: Optional[datetime] = None

class RateLimitExceeded(Exception):
    """Exception raised when rate limit is exceeded"""
    def __init__(self, wait_time: float, retry_after: Optional[datetime] = None):
        self.wait_time = wait_time
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Wait {wait_time:.2f} seconds")

class RequestTracker:
    """Tracks requests for rate limiting"""
    
    def __init__(self, max_history: int = 10000):
        self.requests = deque(maxlen=max_history)
        self.lock = threading.Lock()
    
    def add_request(self, timestamp: float = None):
        """Add a request to the tracker"""
        if timestamp is None:
            timestamp = time.time()
        
        with self.lock:
            self.requests.append(timestamp)
    
    def get_requests_in_window(self, window_seconds: int) -> List[float]:
        """Get requests within the specified time window"""
        cutoff_time = time.time() - window_seconds
        
        with self.lock:
            return [ts for ts in self.requests if ts >= cutoff_time]
    
    def count_requests_in_window(self, window_seconds: int) -> int:
        """Count requests within the specified time window"""
        return len(self.get_requests_in_window(window_seconds))
    
    def clear_old_requests(self, max_age_seconds: int = 3600):
        """Clear requests older than max_age_seconds"""
        cutoff_time = time.time() - max_age_seconds
        
        with self.lock:
            while self.requests and self.requests[0] < cutoff_time:
                self.requests.popleft()

class TokenBucket:
    """Token bucket implementation for rate limiting"""
    
    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.refill_rate = refill_rate  # tokens per second
        self.tokens = capacity
        self.last_refill = time.time()
        self.lock = threading.Lock()
    
    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens from the bucket"""
        with self.lock:
            self._refill()
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                # Handle floating point precision issues
                if self.tokens < 1e-10:
                    self.tokens = 0.0
                return True
            return False
    
    def wait_time_for_tokens(self, tokens: int = 1) -> float:
        """Calculate wait time needed for the requested tokens"""
        with self.lock:
            self._refill()
            
            if self.tokens >= tokens:
                return 0.0
            
            needed_tokens = tokens - self.tokens
            wait_time = needed_tokens / self.refill_rate
            # Round to avoid floating point precision issues
            return round(wait_time, 6)
    
    def _refill(self):
        """Refill tokens based on elapsed time"""
        now = time.time()
        elapsed = now - self.last_refill
        tokens_to_add = elapsed * self.refill_rate
        
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now

class AdaptiveRateLimiter:
    """Adaptive rate limiter that adjusts based on API responses"""
    
    def __init__(self, initial_rate: float, min_rate: float = 0.1, max_rate: float = 100.0):
        self.current_rate = initial_rate
        self.min_rate = min_rate
        self.max_rate = max_rate
        self.success_count = 0
        self.error_count = 0
        self.lock = threading.Lock()
    
    def record_success(self):
        """Record a successful request"""
        with self.lock:
            self.success_count += 1
            self._adjust_rate()
    
    def record_error(self, is_rate_limit: bool = False):
        """Record an error (with special handling for rate limits)"""
        with self.lock:
            self.error_count += 1
            if is_rate_limit:
                # Aggressive backoff for rate limits
                self.current_rate *= 0.5
            else:
                # Gentle backoff for other errors
                self.current_rate *= 0.9
            
            self.current_rate = max(self.min_rate, self.current_rate)
    
    def _adjust_rate(self):
        """Adjust rate based on success/error ratio"""
        total_requests = self.success_count + self.error_count
        
        if total_requests >= 100:  # Adjust every 100 requests
            success_rate = self.success_count / total_requests
            
            if success_rate >= 0.95:
                # High success rate, increase rate
                self.current_rate *= 1.1
            elif success_rate < 0.9:
                # Lower success rate, decrease rate
                self.current_rate *= 0.9
            
            self.current_rate = max(self.min_rate, min(self.max_rate, self.current_rate))
            
            # Reset counters
            self.success_count = 0
            self.error_count = 0

class APIRateLimiter:
    """Advanced rate limiter for a specific API"""
    
    def __init__(self, api_name: str, config: RateLimitConfig):
        self.api_name = api_name
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{api_name}")
        
        # Initialize tracking
        self.tracker = RequestTracker()
        self.stats = RateLimitStats()
        self.lock = threading.Lock()
        
        # Initialize strategy-specific components
        if config.strategy == RateLimitStrategy.TOKEN_BUCKET:
            self.token_bucket = TokenBucket(
                capacity=config.max_requests,
                refill_rate=config.max_requests / config.time_window_seconds
            )
        
        if config.strategy == RateLimitStrategy.ADAPTIVE:
            self.adaptive_limiter = AdaptiveRateLimiter(
                initial_rate=config.max_requests / config.time_window_seconds
            )
        
        # Backoff state
        self.consecutive_failures = 0
        self.last_backoff_time = 0
        
        # Quota tracking
        self.daily_quota_used = 0
        self.quota_reset_date = datetime.now().date()
    
    async def acquire(self, tokens: int = 1, timeout: Optional[float] = None) -> bool:
        """Acquire permission to make a request"""
        start_time = time.time()
        
        try:
            # Check daily quota first
            if not self._check_daily_quota(tokens):
                raise RateLimitExceeded(
                    wait_time=self._time_until_quota_reset(),
                    retry_after=self._next_quota_reset_time()
                )
            
            # Apply rate limiting strategy
            wait_time = self._calculate_wait_time(tokens)
            
            if wait_time > 0:
                if timeout is not None and wait_time > timeout:
                    return False
                
                self.logger.debug(f"Rate limiting {self.api_name}: waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
                
                # Update stats
                with self.lock:
                    self.stats.total_wait_time += wait_time
                    self.stats.rate_limited_requests += 1
            
            # Record the request
            self.tracker.add_request()
            
            with self.lock:
                self.stats.total_requests += 1
                self.stats.last_request_time = datetime.now()
                self.daily_quota_used += tokens
                
                # Update average wait time
                if self.stats.total_requests > 0:
                    self.stats.average_wait_time = self.stats.total_wait_time / self.stats.total_requests
            
            return True
            
        except RateLimitExceeded:
            with self.lock:
                self.stats.rate_limited_requests += 1
            raise
    
    def _calculate_wait_time(self, tokens: int) -> float:
        """Calculate wait time based on strategy"""
        if self.config.strategy == RateLimitStrategy.FIXED_WINDOW:
            return self._fixed_window_wait_time(tokens)
        elif self.config.strategy == RateLimitStrategy.SLIDING_WINDOW:
            return self._sliding_window_wait_time(tokens)
        elif self.config.strategy == RateLimitStrategy.TOKEN_BUCKET:
            return self._token_bucket_wait_time(tokens)
        elif self.config.strategy == RateLimitStrategy.LEAKY_BUCKET:
            return self._leaky_bucket_wait_time(tokens)
        elif self.config.strategy == RateLimitStrategy.ADAPTIVE:
            return self._adaptive_wait_time(tokens)
        else:
            return 0.0
    
    def _fixed_window_wait_time(self, tokens: int) -> float:
        """Calculate wait time for fixed window strategy"""
        current_window_start = int(time.time() / self.config.time_window_seconds) * self.config.time_window_seconds
        requests_in_window = len([
            ts for ts in self.tracker.requests 
            if ts >= current_window_start
        ])
        
        if requests_in_window + tokens > self.config.max_requests:
            next_window_start = current_window_start + self.config.time_window_seconds
            return next_window_start - time.time()
        
        return 0.0
    
    def _sliding_window_wait_time(self, tokens: int) -> float:
        """Calculate wait time for sliding window strategy"""
        current_requests = self.tracker.count_requests_in_window(self.config.time_window_seconds)
        
        if current_requests + tokens > self.config.max_requests + self.config.burst_allowance:
            # Calculate when oldest request will expire
            requests_in_window = self.tracker.get_requests_in_window(self.config.time_window_seconds)
            if requests_in_window:
                oldest_request = min(requests_in_window)
                wait_time = (oldest_request + self.config.time_window_seconds) - time.time()
                return max(0, wait_time)
        
        return 0.0
    
    def _token_bucket_wait_time(self, tokens: int) -> float:
        """Calculate wait time for token bucket strategy"""
        wait_time = self.token_bucket.wait_time_for_tokens(tokens)
        # For token bucket, ensure we wait at least a minimum time when tokens are exhausted
        if wait_time > 0 and wait_time < 0.1:
            wait_time = 0.1
        return wait_time
    
    def _leaky_bucket_wait_time(self, tokens: int) -> float:
        """Calculate wait time for leaky bucket strategy"""
        # Simplified leaky bucket implementation
        leak_rate = self.config.max_requests / self.config.time_window_seconds
        current_requests = self.tracker.count_requests_in_window(self.config.time_window_seconds)
        
        if current_requests + tokens > self.config.max_requests:
            excess_requests = (current_requests + tokens) - self.config.max_requests
            return excess_requests / leak_rate
        
        return 0.0
    
    def _adaptive_wait_time(self, tokens: int) -> float:
        """Calculate wait time for adaptive strategy"""
        if hasattr(self, 'adaptive_limiter'):
            current_rate = self.adaptive_limiter.current_rate
            min_interval = 1.0 / current_rate
            
            last_request_time = self.tracker.requests[-1] if self.tracker.requests else 0
            time_since_last = time.time() - last_request_time
            
            if time_since_last < min_interval:
                return min_interval - time_since_last
        
        return 0.0
    
    def record_success(self):
        """Record a successful API call"""
        with self.lock:
            self.stats.successful_requests += 1
            self.consecutive_failures = 0
            
            if hasattr(self, 'adaptive_limiter'):
                self.adaptive_limiter.record_success()
    
    def record_failure(self, is_rate_limit: bool = False):
        """Record a failed API call"""
        with self.lock:
            self.consecutive_failures += 1
            self.stats.current_backoff_level = min(10, self.consecutive_failures)
            
            if hasattr(self, 'adaptive_limiter'):
                self.adaptive_limiter.record_error(is_rate_limit)
    
    def get_backoff_time(self) -> float:
        """Calculate backoff time based on consecutive failures"""
        if self.consecutive_failures == 0:
            return 0.0
        
        if self.config.backoff_strategy == BackoffStrategy.LINEAR:
            backoff = self.consecutive_failures * self.config.backoff_base
        elif self.config.backoff_strategy == BackoffStrategy.EXPONENTIAL:
            backoff = self.config.backoff_base ** self.consecutive_failures
        elif self.config.backoff_strategy == BackoffStrategy.FIBONACCI:
            backoff = self._fibonacci_backoff(self.consecutive_failures)
        else:
            backoff = self.config.backoff_base
        
        return min(backoff, self.config.max_backoff_seconds)
    
    def _fibonacci_backoff(self, n: int) -> float:
        """Calculate Fibonacci-based backoff"""
        if n <= 1:
            return self.config.backoff_base
        
        a, b = 1, 1
        for _ in range(2, n + 1):
            a, b = b, a + b
        
        return b * self.config.backoff_base
    
    def _check_daily_quota(self, tokens: int) -> bool:
        """Check if daily quota allows the request"""
        # Reset quota if it's a new day
        today = datetime.now().date()
        if today != self.quota_reset_date:
            self.daily_quota_used = 0
            self.quota_reset_date = today
        
        # For APIs without quota limits, always allow
        if self.config.quota_reset_hour is None:
            return True
        
        # Check against daily quota (if configured)
        daily_limit = self.config.max_requests * 24  # Simple daily limit
        return self.daily_quota_used + tokens <= daily_limit
    
    def _time_until_quota_reset(self) -> float:
        """Calculate time until quota reset"""
        if self.config.quota_reset_hour is None:
            return 0.0
        
        now = datetime.now()
        next_reset = now.replace(
            hour=self.config.quota_reset_hour,
            minute=0,
            second=0,
            microsecond=0
        )
        
        if next_reset <= now:
            next_reset += timedelta(days=1)
        
        return (next_reset - now).total_seconds()
    
    def _next_quota_reset_time(self) -> datetime:
        """Get the next quota reset time"""
        if self.config.quota_reset_hour is None:
            return datetime.now() + timedelta(days=1)
        
        now = datetime.now()
        next_reset = now.replace(
            hour=self.config.quota_reset_hour,
            minute=0,
            second=0,
            microsecond=0
        )
        
        if next_reset <= now:
            next_reset += timedelta(days=1)
        
        return next_reset
    
    def get_stats(self) -> Dict[str, Any]:
        """Get rate limiting statistics"""
        with self.lock:
            stats_dict = {
                'api_name': self.api_name,
                'total_requests': self.stats.total_requests,
                'successful_requests': self.stats.successful_requests,
                'rate_limited_requests': self.stats.rate_limited_requests,
                'success_rate': self.stats.successful_requests / max(1, self.stats.total_requests),
                'total_wait_time': self.stats.total_wait_time,
                'average_wait_time': self.stats.average_wait_time,
                'current_backoff_level': self.stats.current_backoff_level,
                'consecutive_failures': self.consecutive_failures,
                'daily_quota_used': self.daily_quota_used,
                'quota_reset_time': self._next_quota_reset_time().isoformat(),
                'current_requests_in_window': self.tracker.count_requests_in_window(self.config.time_window_seconds),
                'max_requests_per_window': self.config.max_requests,
                'time_window_seconds': self.config.time_window_seconds,
                'strategy': self.config.strategy.value,
                'last_request_time': self.stats.last_request_time.isoformat() if self.stats.last_request_time else None
            }
            
            if hasattr(self, 'adaptive_limiter'):
                stats_dict['adaptive_current_rate'] = self.adaptive_limiter.current_rate
            
            return stats_dict

class RateLimitManager:
    """Manager for multiple API rate limiters"""
    
    def __init__(self):
        self.limiters: Dict[str, APIRateLimiter] = {}
        self.logger = logging.getLogger(__name__)
        self.lock = threading.Lock()
    
    def register_api(self, api_name: str, config: RateLimitConfig):
        """Register a new API with rate limiting"""
        with self.lock:
            self.limiters[api_name] = APIRateLimiter(api_name, config)
            self.logger.info(f"Registered rate limiter for {api_name}: {config.max_requests} req/{config.time_window_seconds}s")
    
    def get_limiter(self, api_name: str) -> Optional[APIRateLimiter]:
        """Get rate limiter for an API"""
        return self.limiters.get(api_name)
    
    async def acquire(self, api_name: str, tokens: int = 1, timeout: Optional[float] = None) -> bool:
        """Acquire permission for an API request"""
        limiter = self.limiters.get(api_name)
        if limiter is None:
            self.logger.warning(f"No rate limiter found for API: {api_name}")
            return True
        
        return await limiter.acquire(tokens, timeout)
    
    def record_success(self, api_name: str):
        """Record successful API call"""
        limiter = self.limiters.get(api_name)
        if limiter:
            limiter.record_success()
    
    def record_failure(self, api_name: str, is_rate_limit: bool = False):
        """Record failed API call"""
        limiter = self.limiters.get(api_name)
        if limiter:
            limiter.record_failure(is_rate_limit)
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all APIs"""
        stats = {}
        for api_name, limiter in self.limiters.items():
            stats[api_name] = limiter.get_stats()
        return stats
    
    def cleanup_old_data(self, max_age_hours: int = 24):
        """Clean up old request data"""
        max_age_seconds = max_age_hours * 3600
        for limiter in self.limiters.values():
            limiter.tracker.clear_old_requests(max_age_seconds)
    
    def export_stats(self, file_path: str):
        """Export statistics to JSON file"""
        try:
            stats = self.get_all_stats()
            with open(file_path, 'w') as f:
                json.dump(stats, f, indent=2, default=str)
            self.logger.info(f"Rate limiting statistics exported to {file_path}")
        except Exception as e:
            self.logger.error(f"Failed to export statistics: {e}")


# Global rate limit manager
_rate_limit_manager: Optional[RateLimitManager] = None

def get_rate_limit_manager() -> RateLimitManager:
    """Get global rate limit manager"""
    global _rate_limit_manager
    if _rate_limit_manager is None:
        _rate_limit_manager = RateLimitManager()
    return _rate_limit_manager

def setup_api_rate_limiting():
    """Setup rate limiting for all APIs"""
    manager = get_rate_limit_manager()
    
    # Twitter API rate limiting
    twitter_config = RateLimitConfig(
        max_requests=60,  # TwitterAPI.io limit
        time_window_seconds=60,
        strategy=RateLimitStrategy.SLIDING_WINDOW,
        backoff_strategy=BackoffStrategy.EXPONENTIAL,
        backoff_base=2.0,
        max_backoff_seconds=300,
        burst_allowance=5
    )
    manager.register_api('twitter', twitter_config)
    
    # OpenAI API rate limiting
    openai_config = RateLimitConfig(
        max_requests=20,  # Conservative limit
        time_window_seconds=60,
        strategy=RateLimitStrategy.TOKEN_BUCKET,
        backoff_strategy=BackoffStrategy.EXPONENTIAL,
        backoff_base=2.0,
        max_backoff_seconds=600,
        quota_reset_hour=0  # Daily quota resets at midnight UTC
    )
    manager.register_api('openai', openai_config)
    
    # Telegram API rate limiting
    telegram_config = RateLimitConfig(
        max_requests=30,  # Telegram bot limit
        time_window_seconds=60,
        strategy=RateLimitStrategy.SLIDING_WINDOW,
        backoff_strategy=BackoffStrategy.LINEAR,
        backoff_base=1.0,
        max_backoff_seconds=60,
        burst_allowance=10
    )
    manager.register_api('telegram', telegram_config)
    
    return manager

# Decorator for automatic rate limiting
def rate_limited(api_name: str, tokens: int = 1):
    """Decorator to apply rate limiting to functions"""
    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            async def async_wrapper(*args, **kwargs):
                manager = get_rate_limit_manager()
                try:
                    await manager.acquire(api_name, tokens)
                    result = await func(*args, **kwargs)
                    manager.record_success(api_name)
                    return result
                except RateLimitExceeded:
                    manager.record_failure(api_name, is_rate_limit=True)
                    raise
                except Exception as e:
                    manager.record_failure(api_name, is_rate_limit=False)
                    raise
            return async_wrapper
        else:
            def sync_wrapper(*args, **kwargs):
                # For sync functions, we need to run the rate limiting in an event loop
                async def rate_limited_call():
                    manager = get_rate_limit_manager()
                    try:
                        await manager.acquire(api_name, tokens)
                        result = func(*args, **kwargs)
                        manager.record_success(api_name)
                        return result
                    except RateLimitExceeded:
                        manager.record_failure(api_name, is_rate_limit=True)
                        raise
                    except Exception as e:
                        manager.record_failure(api_name, is_rate_limit=False)
                        raise
                
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                return loop.run_until_complete(rate_limited_call())
            return sync_wrapper
    return decorator 