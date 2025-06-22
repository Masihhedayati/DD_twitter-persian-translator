"""
Test suite for notification pipeline integration
Tests the complete workflow from tweet detection to Telegram notification
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os
import json
import time
from datetime import datetime

# Import the components we're testing
from core.polling_scheduler import PollingScheduler
from core.database import Database
from core.telegram_bot import TelegramNotifier


class TestNotificationPipeline(unittest.TestCase):
    """Test the complete notification pipeline"""
    
    def setUp(self):
        """Set up test environment"""
        # Create temporary database
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        self.media_dir = tempfile.mkdtemp()
        
        # Create test configuration
        self.config = {
            'TWITTER_API_KEY': 'test-twitter-key',
            'OPENAI_API_KEY': 'test-openai-key',
            'TELEGRAM_BOT_TOKEN': 'test-telegram-token',
            'TELEGRAM_CHAT_ID': 'test-chat-id',
            'MONITORED_USERS': 'testuser1,testuser2',
            'CHECK_INTERVAL': 5,  # Short interval for testing
            'MEDIA_STORAGE_PATH': self.media_dir,
            'DATABASE_PATH': self.db_path,
            'AI_BATCH_SIZE': 2,
            'AI_PROCESSING_INTERVAL': 10,
            'NOTIFICATION_ENABLED': True,
            'NOTIFY_ALL_TWEETS': False,
            'NOTIFY_AI_PROCESSED_ONLY': True,
            'NOTIFICATION_DELAY': 1  # Short delay for testing
        }
        
        # Initialize database
        self.database = Database(self.db_path)
        
        # Mock external services
        self.twitter_patcher = patch('core.polling_scheduler.TwitterClient')
        self.openai_patcher = patch('core.polling_scheduler.OpenAIClient')
        self.telegram_patcher = patch('core.polling_scheduler.create_telegram_notifier')
        
        self.mock_twitter = self.twitter_patcher.start()
        self.mock_openai = self.openai_patcher.start()
        self.mock_telegram_factory = self.telegram_patcher.start()
        
        # Set up mock behaviors
        self.setup_mocks()
    
    def tearDown(self):
        """Clean up test environment"""
        # Stop patches
        self.twitter_patcher.stop()
        self.openai_patcher.stop()
        self.telegram_patcher.stop()
        
        # Clean up temporary files
        os.close(self.db_fd)
        os.unlink(self.db_path)
        
        # Clean up media directory
        if os.path.exists(self.media_dir):
            import shutil
            shutil.rmtree(self.media_dir)
    
    def setup_mocks(self):
        """Set up mock behaviors for external services"""
        # Mock Twitter client
        self.mock_twitter_instance = Mock()
        self.mock_twitter.return_value = self.mock_twitter_instance
        self.mock_twitter_instance.validate_api_key.return_value = True
        self.mock_twitter_instance.get_user_tweets.return_value = []
        
        # Mock OpenAI client
        self.mock_openai_instance = Mock()
        self.mock_openai.return_value = self.mock_openai_instance
        
        # Mock Telegram notifier
        self.mock_telegram_instance = Mock()
        self.mock_telegram_factory.return_value = self.mock_telegram_instance
        self.mock_telegram_instance.is_running.return_value = True
        self.mock_telegram_instance.send_tweet_notification.return_value = True
        self.mock_telegram_instance.get_statistics.return_value = {
            'messages_sent': 0,
            'messages_failed': 0,
            'media_sent': 0,
            'rate_limit_hits': 0,
            'success_rate': 100.0
        }
    
    def test_scheduler_initialization_with_telegram(self):
        """Test that scheduler initializes with Telegram notifications enabled"""
        scheduler = PollingScheduler(self.config)
        
        # Verify Telegram components are initialized
        self.assertTrue(scheduler.telegram_enabled)
        self.assertIsNotNone(scheduler.telegram_notifier)
        self.assertTrue(scheduler.notification_enabled)
        self.assertTrue(scheduler.notify_ai_processed_only)
        self.assertFalse(scheduler.notify_all_tweets)
        self.assertEqual(scheduler.notification_delay, 1)
    
    def test_scheduler_initialization_without_telegram(self):
        """Test scheduler initialization when Telegram is disabled"""
        config = self.config.copy()
        config['TELEGRAM_BOT_TOKEN'] = ''
        
        scheduler = PollingScheduler(config)
        
        # Verify Telegram is disabled
        self.assertFalse(scheduler.telegram_enabled)
        self.assertIsNone(scheduler.telegram_notifier)
    
    def test_notification_trigger_for_new_tweets(self):
        """Test that notifications are triggered for new tweets"""
        # Set up test data
        test_tweet = {
            'id': 'test-tweet-123',
            'username': 'testuser1',
            'content': 'Test tweet content',
            'created_at': datetime.now().isoformat(),
            'likes_count': 10,
            'retweets_count': 5,
            'replies_count': 2
        }
        
        # Mock Twitter API to return new tweet
        self.mock_twitter_instance.get_user_tweets.return_value = [test_tweet]
        
        # Create scheduler
        scheduler = PollingScheduler(self.config)
        
        # Mock database methods on the scheduler's database instance
        with patch.object(scheduler.db, 'get_unsent_notifications') as mock_unsent:
            mock_unsent.return_value = [test_tweet]
            
            # Manually trigger notification for testing
            result = scheduler._trigger_notifications_for_new_tweets('testuser1')
            
            # Verify notification was attempted
            self.assertGreater(result, 0)
            self.mock_telegram_instance.send_tweet_notification.assert_called_once()
    
    def test_notification_delay_for_ai_processing(self):
        """Test that notifications wait for AI processing when configured"""
        scheduler = PollingScheduler(self.config)
        
        # Mock database to return tweets
        test_tweet = {
            'id': 'test-tweet-123',
            'username': 'testuser1',
            'content': 'Test tweet content',
            'created_at': datetime.now().isoformat()
        }
        
        with patch.object(scheduler.db, 'get_unsent_notifications') as mock_unsent:
            mock_unsent.return_value = [test_tweet]
            
            # Record start time
            start_time = time.time()
            
            # Trigger notification (should wait for AI processing)
            result = scheduler._trigger_notifications_for_new_tweets('testuser1')
            
            # Verify delay occurred
            elapsed = time.time() - start_time
            self.assertGreaterEqual(elapsed, scheduler.notification_delay)
            
            # Verify correct database method was called
            mock_unsent.assert_called_with(
                username='testuser1',
                ai_processed_only=True,
                limit=10
            )
    
    def test_notification_immediate_when_all_tweets_enabled(self):
        """Test immediate notifications when notify_all_tweets is enabled"""
        config = self.config.copy()
        config['NOTIFY_ALL_TWEETS'] = True
        config['NOTIFY_AI_PROCESSED_ONLY'] = False
        
        scheduler = PollingScheduler(config)
        
        test_tweet = {
            'id': 'test-tweet-123',
            'username': 'testuser1',
            'content': 'Test tweet content',
            'created_at': datetime.now().isoformat()
        }
        
        with patch.object(scheduler.db, 'get_unsent_notifications') as mock_unsent:
            mock_unsent.return_value = [test_tweet]
            
            # Record start time
            start_time = time.time()
            
            # Trigger notification (should be immediate)
            result = scheduler._trigger_notifications_for_new_tweets('testuser1')
            
            # Verify no significant delay
            elapsed = time.time() - start_time
            self.assertLess(elapsed, 0.5)  # Should be very quick
            
            # Verify correct database method was called
            mock_unsent.assert_called_with(
                username='testuser1',
                ai_processed_only=False,
                limit=10
            )
    
    def test_telegram_status_integration(self):
        """Test Telegram status reporting"""
        scheduler = PollingScheduler(self.config)
        
        # Mock Telegram statistics
        self.mock_telegram_instance.get_statistics.return_value = {
            'messages_sent': 15,
            'messages_failed': 2,
            'media_sent': 8,
            'rate_limit_hits': 1,
            'success_rate': 88.2,
            'last_activity': datetime.now().isoformat()
        }
        
        # Get Telegram status
        status = scheduler.get_telegram_status()
        
        # Verify status structure
        self.assertTrue(status['enabled'])
        self.assertTrue(status['is_running'])
        self.assertEqual(status['messages_sent'], 15)
        self.assertEqual(status['messages_failed'], 2)
        self.assertEqual(status['success_rate'], 88.2)
    
    def test_force_telegram_notifications(self):
        """Test forcing Telegram notifications"""
        scheduler = PollingScheduler(self.config)
        
        # Mock database to return pending notifications
        test_tweets = [
            {'id': 'tweet-1', 'username': 'testuser1', 'content': 'Test 1', 'created_at': datetime.now().isoformat()},
            {'id': 'tweet-2', 'username': 'testuser1', 'content': 'Test 2', 'created_at': datetime.now().isoformat()}
        ]
        
        with patch.object(scheduler.db, 'get_unsent_notifications') as mock_unsent:
            mock_unsent.return_value = test_tweets
            
            # Force notifications
            result = scheduler.force_telegram_notifications(username='testuser1', limit=5)
            
            # Verify results
            self.assertTrue(result['success'])
            self.assertEqual(result['sent_count'], 2)
            self.assertEqual(result['failed_count'], 0)
            self.assertEqual(result['total_attempted'], 2)
            
            # Verify Telegram calls
            self.assertEqual(self.mock_telegram_instance.send_tweet_notification.call_count, 2)
    
    def test_notification_error_handling(self):
        """Test error handling in notification pipeline"""
        scheduler = PollingScheduler(self.config)
        
        # Mock Telegram to raise exception
        self.mock_telegram_instance.send_tweet_notification.side_effect = Exception("Telegram error")
        
        test_tweet = {
            'id': 'test-tweet-123',
            'username': 'testuser1',
            'content': 'Test tweet content',
            'created_at': datetime.now().isoformat()
        }
        
        with patch.object(scheduler.db, 'get_unsent_notifications') as mock_unsent:
            mock_unsent.return_value = [test_tweet]
            
            # Trigger notification (should handle error gracefully)
            result = scheduler._trigger_notifications_for_new_tweets('testuser1')
            
            # Should return 0 notifications queued due to error
            self.assertEqual(result, 0)
    
    def test_notification_pause_resume(self):
        """Test pausing and resuming notifications"""
        scheduler = PollingScheduler(self.config)
        
        # Initially enabled
        self.assertTrue(scheduler.notification_enabled)
        self.assertFalse(scheduler.is_notifications_paused())
        
        # Pause notifications
        scheduler.pause_notifications()
        self.assertFalse(scheduler.notification_enabled)
        self.assertTrue(scheduler.is_notifications_paused())
        
        # Resume notifications
        scheduler.resume_notifications()
        self.assertTrue(scheduler.notification_enabled)
        self.assertFalse(scheduler.is_notifications_paused())
    
    def test_statistics_include_telegram(self):
        """Test that system statistics include Telegram data"""
        scheduler = PollingScheduler(self.config)
        
        # Mock Telegram statistics
        self.mock_telegram_instance.get_statistics.return_value = {
            'messages_sent': 25,
            'messages_failed': 3,
            'media_sent': 10,
            'rate_limit_hits': 0,
            'success_rate': 89.3,
            'is_running': True,
            'last_activity': datetime.now().isoformat(),
            'queue_size': 0
        }
        
        # Get statistics
        stats = scheduler.get_statistics()
        
        # Verify Telegram stats are included
        self.assertIn('telegram_stats', stats)
        telegram_stats = stats['telegram_stats']
        
        self.assertTrue(telegram_stats['enabled'])
        self.assertEqual(telegram_stats['messages_sent'], 25)
        self.assertEqual(telegram_stats['messages_failed'], 3)
        self.assertEqual(telegram_stats['success_rate'], 89.3)
    
    def test_complete_notification_workflow(self):
        """Test the complete notification workflow from tweet to Telegram"""
        # This is an integration test that simulates the complete flow
        
        # Set up test tweet data
        test_tweet = {
            'id': 'workflow-test-123',
            'username': 'testuser1',
            'display_name': 'Test User',
            'content': 'This is a test tweet for workflow testing',
            'created_at': datetime.now().isoformat(),
            'likes_count': 15,
            'retweets_count': 8,
            'replies_count': 3,
            'tweet_type': 'tweet'
        }
        
        # Mock Twitter to return the test tweet
        self.mock_twitter_instance.get_user_tweets.return_value = [test_tweet]
        
        # Create scheduler
        scheduler = PollingScheduler(self.config)
        
        # Simulate the complete workflow
        with patch.object(scheduler, '_is_new_tweet', return_value=True):
            with patch.object(scheduler.db, 'get_unsent_notifications') as mock_unsent:
                mock_unsent.return_value = [test_tweet]
                
                # Add test user to monitoring list  
                scheduler.monitored_users = ['testuser1']
                
                # Trigger a complete poll (simulates the complete workflow)
                result = scheduler._poll_all_users()
                
                # Verify tweet was processed
                self.assertGreater(result['total_tweets_found'], 0)
                self.assertGreater(result['new_tweets_saved'], 0)
                
                # Verify notification was attempted
                self.assertGreater(result['notifications_queued'], 0)
                self.mock_telegram_instance.send_tweet_notification.assert_called()
                
                # Verify the notification call had correct parameters
                call_args = self.mock_telegram_instance.send_tweet_notification.call_args
                self.assertEqual(call_args[1]['tweet_id'], test_tweet['id'])
                self.assertEqual(call_args[1]['username'], test_tweet['username'])
                self.assertEqual(call_args[1]['content'], test_tweet['content'])


if __name__ == '__main__':
    unittest.main() 