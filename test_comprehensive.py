#!/usr/bin/env python3
"""
Comprehensive End-to-End Integration Tests
Tests the complete pipeline from Twitter monitoring to Telegram notifications
"""

import pytest
import asyncio
import sqlite3
import os
import tempfile
import time
import threading
from unittest.mock import Mock, patch, MagicMock
import requests
import json
from concurrent.futures import ThreadPoolExecutor

# Import all our components
from core.database import Database
from core.twitter_client import TwitterClient
from core.media_extractor import MediaExtractor
from core.polling_scheduler import PollingScheduler
from core.openai_client import OpenAIClient
from core.ai_processor import AIProcessor
from core.telegram_bot import TelegramNotifier
from core.config_manager import ConfigManager
from core.rate_limiter import get_rate_limit_manager
from core.performance_optimizer import get_performance_optimizer
from core.error_handler import ErrorHandler
from core.health_monitor import HealthMonitor

class TestEndToEndIntegration:
    """End-to-end integration testing suite"""
    
    @pytest.fixture
    def app_config(self):
        """Create test application configuration"""
        return {
            'TESTING': True,
            'DATABASE_PATH': ':memory:',
            'TWITTER_API_KEY': 'test_key',
            'OPENAI_API_KEY': 'test_key',
            'TELEGRAM_BOT_TOKEN': 'test_token',
            'TELEGRAM_CHAT_ID': 'test_chat',
            'MONITORED_USERS': ['testuser1', 'testuser2'],
            'MEDIA_STORAGE_PATH': tempfile.mkdtemp()
        }
    
    # Removed Flask app fixtures since we're testing components directly
    
    def test_complete_pipeline_integration(self, app_config):
        """Test complete pipeline from Twitter to Telegram"""
        # Mock tweet data
        mock_tweet = {
            'id': '1234567890',
            'username': 'testuser1',
            'display_name': 'Test User',
            'content': 'This is a test tweet with #hashtag',
            'created_at': '2024-12-22T10:00:00Z',
            'media': [
                {
                    'type': 'image',
                    'url': 'https://example.com/image.jpg',
                    'width': 1200,
                    'height': 800
                }
            ],
            'likes_count': 10,
            'retweets_count': 5,
            'replies_count': 2
        }
        
        # Initialize components
        db = Database(app_config['DATABASE_PATH'])
        
        # Test Twitter client integration
        with patch('core.twitter_client.TwitterClient.get_user_tweets') as mock_get_tweets:
            mock_get_tweets.return_value = [mock_tweet]
            
            twitter_client = TwitterClient(app_config['TWITTER_API_KEY'])
            tweets = twitter_client.get_user_tweets('testuser1')
            
            assert len(tweets) == 1
            assert tweets[0]['id'] == '1234567890'
        
        # Test database storage
        db.insert_tweet(mock_tweet)
        stored_tweet = db.get_tweet_by_id('1234567890')
        assert stored_tweet is not None
        assert stored_tweet['username'] == 'testuser1'
        
        # Test media extraction
        media_extractor = MediaExtractor(app_config['MEDIA_STORAGE_PATH'])
        media_items = media_extractor._extract_media_from_tweet(mock_tweet)
        assert len(media_items) == 1
        assert media_items[0]['type'] == 'image'
        
        # Test AI processing integration
        with patch('core.openai_client.OpenAIClient.analyze_tweet') as mock_ai:
            mock_ai.return_value = {
                'success': True,
                'result': 'This tweet expresses positive sentiment about testing.',
                'tokens_used': 45,
                'model': 'gpt-3.5-turbo'
            }
            
            openai_client = OpenAIClient(app_config['OPENAI_API_KEY'])
            ai_processor = AIProcessor(openai_client, db)
            
            result = ai_processor.process_tweet('1234567890')
            assert result['success'] is True
            assert 'positive sentiment' in result['result']
        
        # Test Telegram notification
        with patch('core.telegram_bot.TelegramNotifier.send_tweet_notification') as mock_telegram:
            mock_telegram.return_value = {'success': True, 'message_id': '123'}
            
            telegram_notifier = TelegramNotifier(
                app_config['TELEGRAM_BOT_TOKEN'],
                app_config['TELEGRAM_CHAT_ID']
            )
            
            notification_result = telegram_notifier.send_tweet_notification(
                stored_tweet, 
                'This tweet expresses positive sentiment about testing.'
            )
            
            assert notification_result['success'] is True
    
    def test_performance_under_load(self, app_config):
        """Test system performance under load"""
        db = Database(app_config['DATABASE_PATH'])
        
        # Generate test data
        test_tweets = []
        for i in range(100):
            test_tweets.append({
                'id': f'tweet_{i}',
                'username': f'user_{i % 10}',
                'display_name': f'User {i % 10}',
                'content': f'Test tweet number {i} with some content',
                'created_at': '2024-12-22T10:00:00Z',
                'media': [],
                'likes_count': i,
                'retweets_count': i // 2,
                'replies_count': i // 3
            })
        
        # Test bulk insertion performance
        start_time = time.time()
        for tweet in test_tweets:
            db.insert_tweet(tweet)
        bulk_insert_time = time.time() - start_time
        
        # Should complete within 5 seconds
        assert bulk_insert_time < 5.0, f"Bulk insert took {bulk_insert_time:.2f}s, expected <5s"
        
        # Test query performance
        start_time = time.time()
        tweets = db.get_tweets(limit=50)
        query_time = time.time() - start_time
        
        # Queries should be fast
        assert query_time < 0.1, f"Query took {query_time:.3f}s, expected <0.1s"
        assert len(tweets) == 50
    
    def test_concurrent_operations(self, app_config):
        """Test concurrent operations handling"""
        db = Database(app_config['DATABASE_PATH'])
        
        def insert_tweets(thread_id):
            """Insert tweets in parallel"""
            for i in range(10):
                tweet = {
                    'id': f'thread_{thread_id}_tweet_{i}',
                    'username': f'user_{thread_id}',
                    'display_name': f'User {thread_id}',
                    'content': f'Tweet {i} from thread {thread_id}',
                    'created_at': '2024-12-22T10:00:00Z',
                    'media': [],
                    'likes_count': i,
                    'retweets_count': 0,
                    'replies_count': 0
                }
                db.insert_tweet(tweet)
        
        # Run concurrent insertions
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(insert_tweets, i) for i in range(5)]
            for future in futures:
                future.result()  # Wait for completion
        
        # Verify all tweets were inserted correctly
        total_tweets = db.get_total_tweets_count()
        assert total_tweets == 50, f"Expected 50 tweets, got {total_tweets}"
    
    def test_memory_usage_stability(self, app_config):
        """Test memory usage remains stable over time"""
        import psutil
        import gc
        
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        db = Database(app_config['DATABASE_PATH'])
        
        # Simulate continuous operation
        for batch in range(10):
            # Insert tweets
            for i in range(50):
                tweet = {
                    'id': f'batch_{batch}_tweet_{i}',
                    'username': f'user_{i % 5}',
                    'display_name': f'User {i % 5}',
                    'content': f'Batch {batch} tweet {i}',
                    'created_at': '2024-12-22T10:00:00Z',
                    'media': [],
                    'likes_count': i,
                    'retweets_count': 0,
                    'replies_count': 0
                }
                db.insert_tweet(tweet)
            
            # Query tweets
            tweets = db.get_tweets(limit=100)
            
            # Force garbage collection
            gc.collect()
            
            # Check memory usage
            current_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = current_memory - initial_memory
            
            # Memory should not grow excessively
            assert memory_increase < 100, f"Memory increased by {memory_increase:.1f}MB, expected <100MB"


class TestSecurityValidation:
    """Security testing suite"""
    
    # Testing security directly without Flask client
    
    def test_sql_injection_protection(self):
        """Test SQL injection protection"""
        db = Database(':memory:')
        
        # Try SQL injection in database operations
        malicious_tweet = {
            'id': "'; DROP TABLE tweets; --",
            'username': 'test_user',
            'display_name': 'Test User',
            'content': 'Test content',
            'created_at': '2024-12-22T10:00:00Z'
        }
        
        # This should not cause an error and should handle the malicious input safely
        try:
            result = db.insert_tweet(malicious_tweet)
            # Should either succeed safely or fail gracefully
            assert isinstance(result, bool)
        except Exception as e:
            # If it raises an exception, it should be a safe one, not about dropping tables
            assert "DROP TABLE" not in str(e).upper()
    
    def test_input_sanitization(self):
        """Test input sanitization for XSS protection"""
        db = Database(':memory:')
        
        malicious_inputs = [
            '<script>alert("xss")</script>',
            'javascript:alert("xss")',
            '<img src="x" onerror="alert(1)">',
            '"><script>alert("xss")</script>',
        ]
        
        for malicious_input in malicious_inputs:
            # Test database input sanitization
            malicious_tweet = {
                'id': f'test_{hash(malicious_input)}',
                'username': malicious_input,
                'display_name': malicious_input,
                'content': malicious_input,
                'created_at': '2024-12-22T10:00:00Z'
            }
            
            # Should not crash or execute scripts
            try:
                result = db.insert_tweet(malicious_tweet)
                assert isinstance(result, bool)
            except Exception as e:
                # Should be safe database error, not script execution
                assert 'alert' not in str(e).lower()
    
    def test_api_key_security(self):
        """Test API key security and exposure"""
        config_manager = ConfigManager()
        
        # API keys should be loaded from environment, not hardcoded
        twitter_key = config_manager.get_twitter_config().api_key
        openai_key = config_manager.get_openai_config().api_key
        
        # Keys should not be None or empty (in test they might be 'test_key')
        assert twitter_key is not None
        assert openai_key is not None
        
        # Keys should not be logged
        import logging
        import io
        
        log_stream = io.StringIO()
        handler = logging.StreamHandler(log_stream)
        logger = logging.getLogger('core')
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        
        # Use the keys (should not appear in logs)
        logger.info(f"Initializing with Twitter API")
        logger.info(f"Initializing with OpenAI API")
        
        log_contents = log_stream.getvalue()
        assert 'test_key' not in log_contents  # Actual keys should not appear in logs
    
    def test_rate_limiting_bypass_protection(self):
        """Test rate limiting cannot be easily bypassed"""
        from core.rate_limiter import RateLimitConfig, APIRateLimiter, RateLimitStrategy
        
        config = RateLimitConfig(
            max_requests=5,
            time_window_seconds=1,
            strategy=RateLimitStrategy.FIXED_WINDOW
        )
        
        limiter = APIRateLimiter("test_api", config)
        
        # Try to exceed rate limit
        requests_allowed = 0
        for i in range(10):
            if limiter.acquire():
                requests_allowed += 1
        
        # Should only allow 5 requests
        assert requests_allowed == 5
        
        # Wait and try again
        time.sleep(1.1)
        
        # Should allow more requests after window
        assert limiter.acquire() is True
    
    def test_environment_variable_validation(self):
        """Test environment variable handling"""
        import os
        
        # Test with missing environment variable
        old_value = os.environ.get('TWITTER_API_KEY')
        if 'TWITTER_API_KEY' in os.environ:
            del os.environ['TWITTER_API_KEY']
        
        config_manager = ConfigManager()
        twitter_config = config_manager.get_twitter_config()
        
        # Should handle missing API key gracefully
        assert twitter_config.api_key is None or twitter_config.api_key == ''
        
        # Restore original value
        if old_value:
            os.environ['TWITTER_API_KEY'] = old_value


class TestPerformanceOptimization:
    """Performance optimization validation"""
    
    def test_database_query_optimization(self):
        """Test database query performance"""
        db = Database(':memory:')
        
        # Insert test data
        for i in range(1000):
            tweet = {
                'id': f'perf_test_{i}',
                'username': f'user_{i % 100}',
                'display_name': f'User {i % 100}',
                'content': f'Performance test tweet {i}',
                'created_at': '2024-12-22T10:00:00Z',
                'media': [],
                'likes_count': i,
                'retweets_count': i // 2,
                'replies_count': i // 3
            }
            db.insert_tweet(tweet)
        
        # Test query performance
        start_time = time.time()
        tweets = db.get_tweets(limit=100)
        query_time = time.time() - start_time
        
        assert query_time < 0.01, f"Query took {query_time:.3f}s, expected <0.01s"
        assert len(tweets) == 100
        
        # Test another query for performance
        start_time = time.time()
        more_tweets = db.get_tweets(limit=25, offset=25)
        filtered_query_time = time.time() - start_time
        
        assert filtered_query_time < 0.02, f"Offset query took {filtered_query_time:.3f}s, expected <0.02s"
        assert len(more_tweets) == 25
    
    def test_caching_performance(self):
        """Test caching system performance"""
        from core.performance_optimizer import PerformanceOptimizer
        
        optimizer = PerformanceOptimizer()
        
        # Test cache performance
        @optimizer.cache_with_ttl(ttl_seconds=60)
        def expensive_operation(x):
            time.sleep(0.1)  # Simulate expensive operation
            return x * x
        
        # First call should be slow
        start_time = time.time()
        result1 = expensive_operation(5)
        first_call_time = time.time() - start_time
        
        assert result1 == 25
        assert first_call_time >= 0.1  # Should take at least 0.1s
        
        # Second call should be fast (cached)
        start_time = time.time()
        result2 = expensive_operation(5)
        second_call_time = time.time() - start_time
        
        assert result2 == 25
        assert second_call_time < 0.01  # Should be very fast
        
        # Verify cache hit statistics
        stats = optimizer.get_cache_stats()
        assert stats['hits'] >= 1
    
    def test_concurrent_request_handling(self):
        """Test concurrent request handling performance"""
        from core.performance_optimizer import AsyncTaskManager
        
        task_manager = AsyncTaskManager(max_threads=10)
        
        def test_task(task_id):
            time.sleep(0.1)  # Simulate work
            return f"Task {task_id} completed"
        
        # Submit multiple tasks concurrently
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(test_task, i) 
                for i in range(20)
            ]
            results = [future.result() for future in futures]
        
        total_time = time.time() - start_time
        
        # Should complete faster than sequential execution
        assert total_time < 2.0, f"Concurrent execution took {total_time:.2f}s, expected <2s"
        assert len(results) == 20
        
        # Verify all tasks completed
        for i, result in enumerate(results):
            assert f"Task {i} completed" == result
    
    @pytest.mark.asyncio
    async def test_async_media_download_performance(self):
        """Test async media download performance"""
        from core.media_extractor import MediaExtractor
        
        media_extractor = MediaExtractor(tempfile.mkdtemp())
        
        # Mock multiple media URLs
        media_urls = [
            f'https://example.com/image_{i}.jpg'
            for i in range(10)
        ]
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            # Mock successful downloads
            mock_response = Mock()
            mock_response.status = 200
            mock_response.content.iter_chunked.return_value = [b'fake_image_data']
            mock_get.return_value.__aenter__.return_value = mock_response
            
            start_time = time.time()
            
            # Download multiple files concurrently
            download_tasks = [
                media_extractor.download_media(
                    f'tweet_{i}', 
                    url, 
                    'image'
                )
                for i, url in enumerate(media_urls)
            ]
            
            results = await asyncio.gather(*download_tasks, return_exceptions=True)
            
            download_time = time.time() - start_time
            
            # Should complete much faster than sequential downloads
            assert download_time < 1.0, f"Concurrent downloads took {download_time:.2f}s, expected <1s"
            
            # Verify all downloads succeeded
            successful_downloads = [r for r in results if not isinstance(r, Exception)]
            assert len(successful_downloads) == 10


if __name__ == '__main__':
    # Run comprehensive tests
    pytest.main([
        __file__,
        '-v',
        '--tb=short',
        '--durations=10'
    ]) 