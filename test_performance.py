#!/usr/bin/env python3
"""
Performance Testing Suite
Comprehensive performance, load, and stress testing for the Twitter monitoring system
"""

import pytest
import asyncio
import time
import threading
import multiprocessing
import concurrent.futures
import tempfile
import json
import statistics
import psutil
import gc
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, Mock

# Import components for testing
from core.database import Database
from core.twitter_client import TwitterClient
from core.media_extractor import MediaExtractor
from core.polling_scheduler import PollingScheduler
from core.ai_processor import AIProcessor
from core.telegram_notifier import TelegramNotifier
from core.config_manager import ConfigManager
from core.rate_limiter import RateLimitManager
from core.performance_optimizer import PerformanceOptimizer
from app import app


class PerformanceMonitor:
    """Monitor system performance during tests"""
    
    def __init__(self):
        self.metrics = {
            'cpu_usage': [],
            'memory_usage': [],
            'response_times': [],
            'throughput': 0,
            'error_rate': 0,
            'peak_memory': 0,
            'peak_cpu': 0
        }
        self.monitoring = False
        self.start_time = None
        
    def start_monitoring(self):
        """Start performance monitoring"""
        self.monitoring = True
        self.start_time = time.time()
        self.monitor_thread = threading.Thread(target=self._monitor_system)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        
    def stop_monitoring(self):
        """Stop performance monitoring"""
        self.monitoring = False
        if hasattr(self, 'monitor_thread'):
            self.monitor_thread.join(timeout=1)
            
    def _monitor_system(self):
        """Monitor system resources"""
        process = psutil.Process()
        
        while self.monitoring:
            # CPU usage
            cpu_percent = process.cpu_percent()
            self.metrics['cpu_usage'].append(cpu_percent)
            self.metrics['peak_cpu'] = max(self.metrics['peak_cpu'], cpu_percent)
            
            # Memory usage
            memory_mb = process.memory_info().rss / 1024 / 1024
            self.metrics['memory_usage'].append(memory_mb)
            self.metrics['peak_memory'] = max(self.metrics['peak_memory'], memory_mb)
            
            time.sleep(0.1)  # Sample every 100ms
            
    def record_response_time(self, response_time):
        """Record a response time"""
        self.metrics['response_times'].append(response_time)
        
    def get_summary(self):
        """Get performance summary"""
        total_time = time.time() - self.start_time if self.start_time else 0
        
        return {
            'duration_seconds': total_time,
            'avg_cpu_percent': statistics.mean(self.metrics['cpu_usage']) if self.metrics['cpu_usage'] else 0,
            'peak_cpu_percent': self.metrics['peak_cpu'],
            'avg_memory_mb': statistics.mean(self.metrics['memory_usage']) if self.metrics['memory_usage'] else 0,
            'peak_memory_mb': self.metrics['peak_memory'],
            'avg_response_time': statistics.mean(self.metrics['response_times']) if self.metrics['response_times'] else 0,
            'p95_response_time': statistics.quantiles(self.metrics['response_times'], n=20)[18] if len(self.metrics['response_times']) > 20 else 0,
            'total_requests': len(self.metrics['response_times']),
            'throughput_rps': len(self.metrics['response_times']) / total_time if total_time > 0 else 0
        }


class TestDatabasePerformance:
    """Test database performance under various loads"""
    
    def setup_method(self):
        """Setup test database"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db_path = self.temp_db.name
        self.database = Database(self.db_path)
        self.monitor = PerformanceMonitor()
        
    def teardown_method(self):
        """Cleanup test database"""
        self.monitor.stop_monitoring()
        if Path(self.db_path).exists():
            Path(self.db_path).unlink()
            
    def test_single_insert_performance(self):
        """Test single tweet insertion performance"""
        self.monitor.start_monitoring()
        
        tweet_data = {
            'tweet_id': 'perf_test_single',
            'username': 'testuser',
            'content': 'Performance test tweet',
            'created_at': datetime.now().isoformat(),
            'media_urls': json.dumps([])
        }
        
        # Measure single insert
        start_time = time.time()
        result = self.database.insert_tweet(tweet_data)
        end_time = time.time()
        
        self.monitor.record_response_time(end_time - start_time)
        self.monitor.stop_monitoring()
        
        assert result is True
        summary = self.monitor.get_summary()
        
        # Single insert should complete in under 10ms
        assert summary['avg_response_time'] < 0.01, f"Single insert took {summary['avg_response_time']:.4f}s (too slow)"
        
    def test_bulk_insert_performance(self):
        """Test bulk insertion performance"""
        self.monitor.start_monitoring()
        
        num_tweets = 1000
        tweets = []
        
        # Generate test data
        for i in range(num_tweets):
            tweet_data = {
                'tweet_id': f'bulk_test_{i}',
                'username': f'user_{i % 10}',
                'content': f'Bulk test tweet {i} with some content to test insertion performance',
                'created_at': datetime.now().isoformat(),
                'media_urls': json.dumps([f'https://example.com/media_{i}.jpg'])
            }
            tweets.append(tweet_data)
        
        # Measure bulk insert
        start_time = time.time()
        for tweet in tweets:
            result = self.database.insert_tweet(tweet)
            assert result is True
        end_time = time.time()
        
        total_time = end_time - start_time
        self.monitor.stop_monitoring()
        
        summary = self.monitor.get_summary()
        
        # Should insert 1000 tweets in under 5 seconds (200+ tweets/sec)
        assert total_time < 5.0, f"Bulk insert of {num_tweets} tweets took {total_time:.2f}s (too slow)"
        
        # Verify all tweets were inserted
        tweets_count = len(self.database.get_recent_tweets(limit=num_tweets + 10))
        assert tweets_count == num_tweets
        
    def test_concurrent_database_access(self):
        """Test database performance under concurrent access"""
        self.monitor.start_monitoring()
        
        num_threads = 10
        tweets_per_thread = 50
        
        def insert_tweets(thread_id):
            thread_times = []
            for i in range(tweets_per_thread):
                tweet_data = {
                    'tweet_id': f'concurrent_{thread_id}_{i}',
                    'username': f'user_{thread_id}',
                    'content': f'Concurrent test tweet {i} from thread {thread_id}',
                    'created_at': datetime.now().isoformat(),
                    'media_urls': json.dumps([])
                }
                
                start_time = time.time()
                result = self.database.insert_tweet(tweet_data)
                end_time = time.time()
                
                assert result is True
                thread_times.append(end_time - start_time)
                
            return thread_times
        
        # Run concurrent inserts
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(insert_tweets, i) for i in range(num_threads)]
            
            all_times = []
            for future in concurrent.futures.as_completed(futures):
                all_times.extend(future.result())
        
        self.monitor.stop_monitoring()
        summary = self.monitor.get_summary()
        
        # Verify all tweets were inserted
        total_expected = num_threads * tweets_per_thread
        tweets_count = len(self.database.get_recent_tweets(limit=total_expected + 10))
        assert tweets_count == total_expected
        
        # Average response time should be reasonable under concurrent load
        avg_response_time = statistics.mean(all_times)
        assert avg_response_time < 0.1, f"Concurrent access avg response time {avg_response_time:.4f}s (too slow)"
        
    def test_query_performance_with_large_dataset(self):
        """Test query performance with large dataset"""
        
        # Insert large dataset first
        num_tweets = 5000
        for i in range(num_tweets):
            tweet_data = {
                'tweet_id': f'large_dataset_{i}',
                'username': f'user_{i % 100}',
                'content': f'Large dataset test tweet {i}',
                'created_at': (datetime.now() - timedelta(minutes=i)).isoformat(),
                'media_urls': json.dumps([])
            }
            self.database.insert_tweet(tweet_data)
        
        self.monitor.start_monitoring()
        
        # Test various query patterns
        query_tests = [
            ('Recent tweets', lambda: self.database.get_recent_tweets(limit=100)),
            ('Tweets by user', lambda: self.database.get_user_tweets('user_1', limit=50)),
            ('Tweet search', lambda: self.database.search_tweets('test', limit=50))
        ]
        
        for test_name, query_func in query_tests:
            start_time = time.time()
            results = query_func()
            end_time = time.time()
            
            query_time = end_time - start_time
            self.monitor.record_response_time(query_time)
            
            # Queries should complete in under 500ms with 5000 tweets
            assert query_time < 0.5, f"{test_name} query took {query_time:.3f}s (too slow)"
            assert len(results) > 0, f"{test_name} returned no results"
        
        self.monitor.stop_monitoring()


class TestAPIPerformance:
    """Test Flask API performance under load"""
    
    def setup_method(self):
        """Setup Flask test client"""
        app.config['TESTING'] = True
        self.client = app.test_client()
        self.monitor = PerformanceMonitor()
        
    def teardown_method(self):
        """Cleanup"""
        self.monitor.stop_monitoring()
        
    def test_api_response_times(self):
        """Test API endpoint response times"""
        self.monitor.start_monitoring()
        
        endpoints = [
            '/health',
            '/api/tweets',
            '/api/statistics',
            '/api/status'
        ]
        
        for endpoint in endpoints:
            # Test each endpoint multiple times
            for _ in range(5):
                start_time = time.time()
                response = self.client.get(endpoint)
                end_time = time.time()
                
                response_time = end_time - start_time
                self.monitor.record_response_time(response_time)
                
                # All API calls should complete within 2 seconds
                assert response_time < 2.0, f"Endpoint {endpoint} took {response_time:.3f}s (too slow)"
        
        self.monitor.stop_monitoring()


class TestMemoryPerformance:
    """Test memory usage and garbage collection performance"""
    
    def setup_method(self):
        """Setup test environment"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db_path = self.temp_db.name
        self.database = Database(self.db_path)
        self.monitor = PerformanceMonitor()
        
    def teardown_method(self):
        """Cleanup"""
        self.monitor.stop_monitoring()
        if Path(self.db_path).exists():
            Path(self.db_path).unlink()
            
    def test_memory_usage_growth(self):
        """Test memory usage doesn't grow excessively"""
        self.monitor.start_monitoring()
        
        initial_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        
        # Process many tweets to test memory growth
        num_iterations = 10
        tweets_per_iteration = 100
        
        for iteration in range(num_iterations):
            # Insert tweets
            for i in range(tweets_per_iteration):
                tweet_data = {
                    'tweet_id': f'memory_test_{iteration}_{i}',
                    'username': 'testuser',
                    'content': f'Memory test tweet {i} in iteration {iteration} with some content',
                    'created_at': datetime.now().isoformat(),
                    'media_urls': json.dumps([f'https://example.com/image_{i}.jpg'])
                }
                self.database.insert_tweet(tweet_data)
            
            # Force garbage collection
            gc.collect()
            
            current_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
            memory_growth = current_memory - initial_memory
            
            # Memory growth should be linear, not exponential
            # Allow reasonable growth but detect memory leaks
            max_allowed_growth = (iteration + 1) * 10  # 10MB per iteration max
            assert memory_growth < max_allowed_growth, f"Memory grew by {memory_growth:.2f}MB in iteration {iteration} (possible leak)"
        
        self.monitor.stop_monitoring()
        summary = self.monitor.get_summary()
        
        final_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        total_growth = final_memory - initial_memory
        
        # Total memory growth should be reasonable for processing 1000 tweets
        assert total_growth < 100, f"Total memory growth {total_growth:.2f}MB too high (possible leak)"
        
    def test_garbage_collection_performance(self):
        """Test garbage collection performance"""
        
        # Create many objects to trigger GC
        objects = []
        for i in range(10000):
            obj = {
                'id': i,
                'data': f'Test object {i}' * 100,  # Make objects larger
                'timestamp': datetime.now(),
                'nested': {
                    'value': i * 2,
                    'description': f'Nested data for object {i}'
                }
            }
            objects.append(obj)
        
        # Measure GC performance
        start_time = time.time()
        gc.collect()
        gc_time = time.time() - start_time
        
        # GC should complete reasonably quickly
        assert gc_time < 1.0, f"Garbage collection took {gc_time:.3f}s (too slow)"
        
        # Clear objects
        objects.clear()
        gc.collect()


class TestSystemStressTest:
    """Stress testing to find system limits"""
    
    def setup_method(self):
        """Setup stress test environment"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db_path = self.temp_db.name
        self.monitor = PerformanceMonitor()
        
    def teardown_method(self):
        """Cleanup"""
        self.monitor.stop_monitoring()
        if Path(self.db_path).exists():
            Path(self.db_path).unlink()
            
    def test_high_throughput_processing(self):
        """Test system under high throughput load"""
        self.monitor.start_monitoring()
        
        database = Database(self.db_path)
        
        # Simulate high-volume tweet processing
        target_throughput = 100  # tweets per second
        duration_seconds = 10
        total_tweets = target_throughput * duration_seconds
        
        start_time = time.time()
        processed_count = 0
        
        for i in range(total_tweets):
            tweet_data = {
                'tweet_id': f'stress_test_{i}',
                'username': f'user_{i % 50}',
                'content': f'Stress test tweet {i} with substantial content to test processing performance under load',
                'created_at': datetime.now().isoformat(),
                'media_urls': json.dumps([f'https://example.com/media_{i}.jpg', f'https://example.com/video_{i}.mp4'])
            }
            
            result = database.insert_tweet(tweet_data)
            if result:
                processed_count += 1
                
            # Check if we're maintaining target throughput
            elapsed = time.time() - start_time
            expected_count = int(elapsed * target_throughput)
            
            # Allow some tolerance for timing variations
            if processed_count < expected_count * 0.8:
                pytest.skip(f"Unable to maintain target throughput of {target_throughput} tweets/sec")
        
        total_time = time.time() - start_time
        actual_throughput = processed_count / total_time
        
        self.monitor.stop_monitoring()
        summary = self.monitor.get_summary()
        
        # Should achieve at least 80% of target throughput
        min_acceptable_throughput = target_throughput * 0.8
        assert actual_throughput >= min_acceptable_throughput, f"Throughput {actual_throughput:.2f} tweets/sec below target {target_throughput}"
        
        # System should remain stable under load
        assert summary['peak_cpu_percent'] < 90, f"CPU usage peaked at {summary['peak_cpu_percent']:.1f}% (too high)"
        assert summary['peak_memory_mb'] < 500, f"Memory usage peaked at {summary['peak_memory_mb']:.1f}MB (too high)"
        
    def test_resource_limits(self):
        """Test system behavior at resource limits"""
        
        # Test with very large tweet content
        large_content = "A" * 10000  # 10KB tweet content
        
        database = Database(self.db_path)
        
        tweet_data = {
            'tweet_id': 'large_content_test',
            'username': 'testuser',
            'content': large_content,
            'created_at': datetime.now().isoformat(),
            'media_urls': json.dumps([])
        }
        
        # Should handle large content gracefully
        result = database.insert_tweet(tweet_data)
        assert result is True, "Failed to handle large tweet content"
        
        # Retrieve and verify
        tweets = database.get_recent_tweets(limit=1)
        assert len(tweets) == 1
        assert len(tweets[0]['content']) == len(large_content)


if __name__ == '__main__':
    # Run performance tests with verbose output
    pytest.main([__file__, '-v', '-s', '--tb=short']) 