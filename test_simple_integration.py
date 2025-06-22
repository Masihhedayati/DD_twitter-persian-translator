#!/usr/bin/env python3
"""
Simple Integration Tests for Core Components
Tests individual components and basic integration
"""

import pytest
import tempfile
import time
import asyncio
from unittest.mock import Mock, patch

# Import core components
from core.database import Database
from core.twitter_client import TwitterClient
from core.media_extractor import MediaExtractor
from core.openai_client import OpenAIClient
from core.ai_processor import AIProcessor
from core.telegram_bot import TelegramNotifier
from core.config_manager import ConfigManager
from core.rate_limiter import APIRateLimiter, RateLimitConfig, RateLimitStrategy
from core.performance_optimizer import PerformanceOptimizer


class TestCoreIntegration:
    """Simple integration tests for core components"""
    
    def test_database_operations(self):
        """Test database basic operations"""
        # Use in-memory database
        db = Database(':memory:')
        
        # Test inserting a tweet
        test_tweet = {
            'id': 'test_123',
            'username': 'testuser',
            'display_name': 'Test User',
            'content': 'This is a test tweet',
            'created_at': '2024-12-22T10:00:00Z',
            'likes_count': 5,
            'retweets_count': 2,
            'replies_count': 1
        }
        
        # Insert tweet
        result = db.insert_tweet(test_tweet)
        assert result is True
        
        # Retrieve tweet
        retrieved_tweet = db.get_tweet_by_id('test_123')
        assert retrieved_tweet is not None
        assert retrieved_tweet['username'] == 'testuser'
        
        # Get all tweets
        all_tweets = db.get_tweets(limit=10)
        assert len(all_tweets) == 1
        assert all_tweets[0]['id'] == 'test_123'
    
    def test_config_manager(self):
        """Test configuration management"""
        config_manager = ConfigManager()
        
        # Test getting configurations
        twitter_config = config_manager.get_twitter_config()
        openai_config = config_manager.get_openai_config()
        telegram_config = config_manager.get_telegram_config()
        
        # Should return valid config objects
        assert hasattr(twitter_config, 'api_key')
        assert hasattr(openai_config, 'api_key')
        assert hasattr(telegram_config, 'bot_token')
    
    def test_rate_limiter(self):
        """Test rate limiting functionality"""
        config = RateLimitConfig(
            max_requests=3,
            time_window_seconds=1,
            strategy=RateLimitStrategy.FIXED_WINDOW
        )
        
        limiter = APIRateLimiter("test_api", config)
        
        # Should allow first 3 requests
        assert limiter.acquire() is True
        assert limiter.acquire() is True
        assert limiter.acquire() is True
        
        # Should block 4th request
        assert limiter.acquire() is False
        
        # Wait and try again
        time.sleep(1.1)
        assert limiter.acquire() is True
    
    def test_performance_optimizer(self):
        """Test performance optimization features"""
        optimizer = PerformanceOptimizer()
        
        # Test caching
        @optimizer.cache_with_ttl(ttl_seconds=60)
        def test_function(x):
            return x * 2
        
        # First call
        result1 = test_function(5)
        assert result1 == 10
        
        # Second call should be cached
        result2 = test_function(5)
        assert result2 == 10
        
        # Check cache stats
        stats = optimizer.get_cache_stats()
        assert stats['hits'] >= 1
    
    def test_twitter_client_mock(self):
        """Test Twitter client with mocked API"""
        with patch('core.twitter_client.TwitterClient.get_user_tweets') as mock_get_tweets:
            mock_tweet = {
                'id': 'mock_123',
                'username': 'mockuser',
                'display_name': 'Mock User',
                'content': 'Mock tweet content',
                'created_at': '2024-12-22T10:00:00Z',
                'media': []
            }
            mock_get_tweets.return_value = [mock_tweet]
            
            client = TwitterClient('test_api_key')
            tweets = client.get_user_tweets('mockuser')
            
            assert len(tweets) == 1
            assert tweets[0]['id'] == 'mock_123'
    
    def test_media_extractor_basic(self):
        """Test media extractor basic functionality"""
        temp_dir = tempfile.mkdtemp()
        extractor = MediaExtractor(temp_dir)
        
        # Test media URL extraction from tweet
        test_tweet = {
            'id': 'media_test_123',
            'media': [
                {
                    'type': 'image',
                    'url': 'https://example.com/image.jpg',
                    'width': 1200,
                    'height': 800
                }
            ]
        }
        
        media_items = extractor._extract_media_from_tweet(test_tweet)
        assert len(media_items) == 1
        assert media_items[0]['type'] == 'image'
        assert media_items[0]['url'] == 'https://example.com/image.jpg'
    
    def test_ai_client_mock(self):
        """Test OpenAI client with mocked API"""
        with patch('core.openai_client.OpenAIClient.analyze_tweet') as mock_analyze:
            mock_response = {
                'success': True,
                'result': 'This tweet has positive sentiment.',
                'tokens_used': 25,
                'model': 'gpt-3.5-turbo'
            }
            mock_analyze.return_value = mock_response
            
            client = OpenAIClient('test_openai_key')
            result = client.analyze_tweet('This is a test tweet')
            
            assert result['success'] is True
            assert 'positive sentiment' in result['result']
    
    def test_ai_processor_integration(self):
        """Test AI processor with database integration"""
        db = Database(':memory:')
        
        # Insert a test tweet
        test_tweet = {
            'id': 'ai_test_123',
            'username': 'testuser',
            'display_name': 'Test User',
            'content': 'This is a test tweet for AI processing',
            'created_at': '2024-12-22T10:00:00Z'
        }
        db.insert_tweet(test_tweet)
        
        # Mock OpenAI client
        with patch('core.openai_client.OpenAIClient.analyze_tweet') as mock_analyze:
            mock_analyze.return_value = {
                'success': True,
                'result': 'This tweet discusses testing and AI.',
                'tokens_used': 30,
                'model': 'gpt-3.5-turbo'
            }
            
            openai_client = OpenAIClient('test_key')
            ai_processor = AIProcessor(openai_client, db)
            
            # Process the tweet
            result = ai_processor.process_tweet('ai_test_123')
            
            assert result['success'] is True
            assert 'testing and AI' in result['result']
    
    def test_telegram_notifier_mock(self):
        """Test Telegram notifier with mocked API"""
        with patch('core.telegram_bot.TelegramNotifier.send_tweet_notification') as mock_send:
            mock_send.return_value = {'success': True, 'message_id': '456'}
            
            notifier = TelegramNotifier('test_bot_token', 'test_chat_id')
            
            test_tweet = {
                'id': 'telegram_test_123',
                'username': 'testuser',
                'content': 'Test notification tweet',
                'display_name': 'Test User'
            }
            
            result = notifier.send_tweet_notification(test_tweet, 'AI Analysis: Test result')
            
            assert result['success'] is True
            assert result['message_id'] == '456'
    
    def test_end_to_end_pipeline_mock(self):
        """Test complete pipeline with all mocked external services"""
        # Initialize database
        db = Database(':memory:')
        
        # Mock tweet data
        mock_tweet = {
            'id': 'pipeline_test_123',
            'username': 'pipelineuser',
            'display_name': 'Pipeline User',
            'content': 'This is an end-to-end test tweet',
            'created_at': '2024-12-22T10:00:00Z',
            'media': []
        }
        
        # Step 1: Store tweet in database (simulating Twitter API fetch)
        db.insert_tweet(mock_tweet)
        stored_tweet = db.get_tweet_by_id('pipeline_test_123')
        assert stored_tweet is not None
        
        # Step 2: AI Processing (mocked)
        with patch('core.openai_client.OpenAIClient.analyze_tweet') as mock_ai:
            mock_ai.return_value = {
                'success': True,
                'result': 'This tweet is about testing pipelines.',
                'tokens_used': 35,
                'model': 'gpt-3.5-turbo'
            }
            
            openai_client = OpenAIClient('test_key')
            ai_processor = AIProcessor(openai_client, db)
            ai_result = ai_processor.process_tweet('pipeline_test_123')
            
            assert ai_result['success'] is True
        
        # Step 3: Telegram Notification (mocked)
        with patch('core.telegram_bot.TelegramNotifier.send_tweet_notification') as mock_telegram:
            mock_telegram.return_value = {'success': True, 'message_id': '789'}
            
            notifier = TelegramNotifier('test_bot_token', 'test_chat_id')
            notification_result = notifier.send_tweet_notification(
                stored_tweet, 
                ai_result['result']
            )
            
            assert notification_result['success'] is True
        
        print("✅ End-to-end pipeline test completed successfully!")


if __name__ == '__main__':
    # Run the tests
    pytest.main([__file__, '-v', '--tb=short']) 