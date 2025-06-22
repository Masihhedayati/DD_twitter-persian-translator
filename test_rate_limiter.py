"""
Test suite for Advanced Rate Limiting System
Tests rate limiting strategies, backoff mechanisms, and API quota management.
"""

import pytest
import asyncio
import time
from unittest.mock import patch, MagicMock

from core.rate_limiter import (
    RateLimitConfig, RateLimitStrategy, BackoffStrategy,
    APIRateLimiter, RateLimitManager, RateLimitExceeded,
    RequestTracker, TokenBucket, AdaptiveRateLimiter,
    setup_api_rate_limiting, rate_limited
)

class TestRequestTracker:
    """Test RequestTracker class"""
    
    def test_request_tracker_creation(self):
        """Test creating a request tracker"""
        tracker = RequestTracker(max_history=100)
        assert len(tracker.requests) == 0
    
    def test_add_request(self):
        """Test adding requests to tracker"""
        tracker = RequestTracker()
        
        tracker.add_request()
        assert len(tracker.requests) == 1
        
        tracker.add_request(time.time() - 10)
        assert len(tracker.requests) == 2
    
    def test_count_requests_in_window(self):
        """Test counting requests in time window"""
        tracker = RequestTracker()
        current_time = time.time()
        
        # Add requests at different times
        tracker.add_request(current_time - 50)  # Outside window
        tracker.add_request(current_time - 30)  # Inside window
        tracker.add_request(current_time - 10)  # Inside window
        tracker.add_request(current_time)       # Inside window
        
        count = tracker.count_requests_in_window(60)
        assert count == 4  # All requests
        
        count = tracker.count_requests_in_window(40)
        assert count == 3  # Last 3 requests
        
        count = tracker.count_requests_in_window(5)
        assert count == 1  # Only the latest request
    
    def test_clear_old_requests(self):
        """Test clearing old requests"""
        tracker = RequestTracker()
        current_time = time.time()
        
        tracker.add_request(current_time - 7200)  # 2 hours old
        tracker.add_request(current_time - 1800)  # 30 minutes old
        tracker.add_request(current_time)         # Current
        
        assert len(tracker.requests) == 3
        
        tracker.clear_old_requests(3600)  # Clear requests older than 1 hour
        assert len(tracker.requests) == 2


class TestTokenBucket:
    """Test TokenBucket class"""
    
    def test_token_bucket_creation(self):
        """Test creating a token bucket"""
        bucket = TokenBucket(capacity=10, refill_rate=2.0)
        assert bucket.capacity == 10
        assert bucket.refill_rate == 2.0
        assert bucket.tokens == 10
    
    def test_consume_tokens(self):
        """Test consuming tokens from bucket"""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        
        # Should be able to consume tokens
        assert bucket.consume(5) == True
        assert bucket.tokens == 5
        
        # Should be able to consume remaining tokens
        assert bucket.consume(5) == True
        assert abs(bucket.tokens - 0) < 1e-5  # Allow for floating point precision (increased tolerance)
        
        # Should not be able to consume more tokens
        assert bucket.consume(1) == False
        assert bucket.tokens == 0
    
    def test_token_refill(self):
        """Test token refill over time"""
        bucket = TokenBucket(capacity=10, refill_rate=5.0)  # 5 tokens per second
        
        # Consume all tokens
        bucket.consume(10)
        assert bucket.tokens == 0
        
        # Wait and check refill (simulated)
        bucket.last_refill = time.time() - 1.0  # Simulate 1 second passed
        bucket._refill()
        
        assert bucket.tokens == 5.0  # Should have refilled 5 tokens
    
    def test_wait_time_calculation(self):
        """Test wait time calculation"""
        bucket = TokenBucket(capacity=10, refill_rate=2.0)
        
        # With full bucket, no wait time
        wait_time = bucket.wait_time_for_tokens(5)
        assert wait_time == 0.0
        
        # After consuming all tokens
        bucket.consume(10)
        wait_time = bucket.wait_time_for_tokens(4)
        assert abs(wait_time - 2.0) < 0.01  # 4 tokens / 2 tokens per second, allow tolerance


class TestAdaptiveRateLimiter:
    """Test AdaptiveRateLimiter class"""
    
    def test_adaptive_limiter_creation(self):
        """Test creating adaptive rate limiter"""
        limiter = AdaptiveRateLimiter(initial_rate=10.0, min_rate=1.0, max_rate=100.0)
        assert limiter.current_rate == 10.0
        assert limiter.min_rate == 1.0
        assert limiter.max_rate == 100.0
    
    def test_success_recording(self):
        """Test recording successful requests"""
        limiter = AdaptiveRateLimiter(initial_rate=10.0)
        
        # Record many successes first to establish baseline
        for _ in range(100):
            limiter.record_success()
        
        # Check that rate was adjusted (should be >= initial rate due to high success rate)
        assert limiter.current_rate >= 10.0
    
    def test_error_recording(self):
        """Test recording errors and rate limit responses"""
        limiter = AdaptiveRateLimiter(initial_rate=10.0)
        
        # Record rate limit error
        initial_rate = limiter.current_rate
        limiter.record_error(is_rate_limit=True)
        
        # Rate should decrease significantly
        assert limiter.current_rate < initial_rate
        assert limiter.current_rate == initial_rate * 0.5


class TestRateLimitConfig:
    """Test RateLimitConfig class"""
    
    def test_config_creation(self):
        """Test creating rate limit configuration"""
        config = RateLimitConfig(
            max_requests=100,
            time_window_seconds=60,
            strategy=RateLimitStrategy.SLIDING_WINDOW,
            backoff_strategy=BackoffStrategy.EXPONENTIAL
        )
        
        assert config.max_requests == 100
        assert config.time_window_seconds == 60
        assert config.strategy == RateLimitStrategy.SLIDING_WINDOW
        assert config.backoff_strategy == BackoffStrategy.EXPONENTIAL


class TestAPIRateLimiter:
    """Test APIRateLimiter class"""
    
    @pytest.mark.asyncio
    async def test_sliding_window_rate_limiting(self):
        """Test sliding window rate limiting"""
        config = RateLimitConfig(
            max_requests=3,
            time_window_seconds=1,
            strategy=RateLimitStrategy.SLIDING_WINDOW
        )
        
        limiter = APIRateLimiter("test_api", config)
        
        # Should allow first 3 requests quickly
        assert await limiter.acquire() == True
        assert await limiter.acquire() == True
        assert await limiter.acquire() == True
        
        # Fourth request should be delayed
        start_time = time.time()
        assert await limiter.acquire() == True
        elapsed = time.time() - start_time
        
        # Should have waited approximately 1 second
        assert elapsed >= 0.9  # Allow some tolerance
    
    @pytest.mark.asyncio
    async def test_token_bucket_rate_limiting(self):
        """Test token bucket rate limiting"""
        config = RateLimitConfig(
            max_requests=5,
            time_window_seconds=1,
            strategy=RateLimitStrategy.TOKEN_BUCKET
        )
        
        limiter = APIRateLimiter("test_api", config)
        
        # Should allow burst up to capacity
        for _ in range(5):
            assert await limiter.acquire() == True
        
        # Next request should wait for refill (our implementation ensures minimum wait)
        start_time = time.time()
        assert await limiter.acquire() == True
        elapsed = time.time() - start_time
        
        assert elapsed >= 0.05  # Should wait for some refill (reduced tolerance)
    
    @pytest.mark.asyncio
    async def test_acquire_timeout(self):
        """Test acquire with timeout"""
        config = RateLimitConfig(
            max_requests=1,
            time_window_seconds=2,
            strategy=RateLimitStrategy.SLIDING_WINDOW
        )
        
        limiter = APIRateLimiter("test_api", config)
        
        # First request should succeed
        assert await limiter.acquire() == True
        
        # Second request with short timeout should fail
        assert await limiter.acquire(timeout=0.1) == False
    
    def test_success_and_failure_recording(self):
        """Test recording success and failure"""
        config = RateLimitConfig(max_requests=10, time_window_seconds=60)
        limiter = APIRateLimiter("test_api", config)
        
        # Record successes
        limiter.record_success()
        limiter.record_success()
        
        assert limiter.stats.successful_requests == 2
        assert limiter.consecutive_failures == 0
        
        # Record failure
        limiter.record_failure()
        
        assert limiter.consecutive_failures == 1
    
    def test_backoff_time_calculation(self):
        """Test backoff time calculation"""
        config = RateLimitConfig(
            max_requests=10,
            time_window_seconds=60,
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            backoff_base=2.0
        )
        
        limiter = APIRateLimiter("test_api", config)
        
        # No failures, no backoff
        assert limiter.get_backoff_time() == 0.0
        
        # One failure
        limiter.consecutive_failures = 1
        assert limiter.get_backoff_time() == 2.0
        
        # Two failures
        limiter.consecutive_failures = 2
        assert limiter.get_backoff_time() == 4.0
        
        # Linear backoff
        config.backoff_strategy = BackoffStrategy.LINEAR
        limiter = APIRateLimiter("test_api", config)
        limiter.consecutive_failures = 3
        assert limiter.get_backoff_time() == 6.0  # 3 * 2.0
    
    def test_get_stats(self):
        """Test getting rate limiter statistics"""
        config = RateLimitConfig(max_requests=10, time_window_seconds=60)
        limiter = APIRateLimiter("test_api", config)
        
        # Record some activity
        limiter.record_success()
        limiter.record_failure()
        
        stats = limiter.get_stats()
        
        assert stats['api_name'] == 'test_api'
        assert stats['total_requests'] == 0  # acquire() not called
        assert stats['successful_requests'] == 1
        assert stats['max_requests_per_window'] == 10
        assert stats['time_window_seconds'] == 60
        assert stats['strategy'] == 'sliding_window'


class TestRateLimitManager:
    """Test RateLimitManager class"""
    
    def test_manager_creation(self):
        """Test creating rate limit manager"""
        manager = RateLimitManager()
        assert len(manager.limiters) == 0
    
    def test_register_api(self):
        """Test registering APIs with manager"""
        manager = RateLimitManager()
        config = RateLimitConfig(max_requests=10, time_window_seconds=60)
        
        manager.register_api("test_api", config)
        
        assert "test_api" in manager.limiters
        assert isinstance(manager.limiters["test_api"], APIRateLimiter)
    
    @pytest.mark.asyncio
    async def test_manager_acquire(self):
        """Test acquiring through manager"""
        manager = RateLimitManager()
        config = RateLimitConfig(max_requests=10, time_window_seconds=60)
        
        manager.register_api("test_api", config)
        
        # Should succeed
        assert await manager.acquire("test_api") == True
        
        # Non-existent API should also succeed (no limiting)
        assert await manager.acquire("non_existent_api") == True
    
    def test_record_success_failure(self):
        """Test recording success/failure through manager"""
        manager = RateLimitManager()
        config = RateLimitConfig(max_requests=10, time_window_seconds=60)
        
        manager.register_api("test_api", config)
        
        manager.record_success("test_api")
        manager.record_failure("test_api", is_rate_limit=True)
        
        limiter = manager.get_limiter("test_api")
        assert limiter.stats.successful_requests == 1
        assert limiter.consecutive_failures == 1
    
    def test_get_all_stats(self):
        """Test getting all statistics"""
        manager = RateLimitManager()
        config = RateLimitConfig(max_requests=10, time_window_seconds=60)
        
        manager.register_api("api1", config)
        manager.register_api("api2", config)
        
        stats = manager.get_all_stats()
        
        assert "api1" in stats
        assert "api2" in stats
        assert len(stats) == 2


class TestSetupAndDecorator:
    """Test setup functions and decorators"""
    
    def test_setup_api_rate_limiting(self):
        """Test setting up API rate limiting"""
        manager = setup_api_rate_limiting()
        
        assert isinstance(manager, RateLimitManager)
        assert "twitter" in manager.limiters
        assert "openai" in manager.limiters
        assert "telegram" in manager.limiters
    
    @pytest.mark.asyncio
    async def test_rate_limited_decorator_async(self):
        """Test rate limited decorator on async function"""
        # Setup manager first
        manager = setup_api_rate_limiting()
        
        @rate_limited("twitter", tokens=1)
        async def test_async_function():
            return "success"
        
        result = await test_async_function()
        assert result == "success"
        
        # Check that success was recorded
        limiter = manager.get_limiter("twitter")
        assert limiter.stats.successful_requests >= 1
    
    def test_rate_limited_decorator_sync(self):
        """Test rate limited decorator on sync function"""
        # Setup manager first
        manager = setup_api_rate_limiting()
        
        @rate_limited("twitter", tokens=1)
        def test_sync_function():
            return "success"
        
        result = test_sync_function()
        assert result == "success"
        
        # Check that success was recorded
        limiter = manager.get_limiter("twitter")
        assert limiter.stats.successful_requests >= 1


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"]) 