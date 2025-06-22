import unittest
import asyncio
import json
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime
import time

# Import the modules we'll be testing
from core.ai_processor import AIProcessor
from core.database import Database
from core.openai_client import OpenAIClient


class TestAIProcessor(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock database
        self.mock_db = Mock(spec=Database)
        
        # Mock OpenAI client
        self.mock_openai = Mock(spec=OpenAIClient)
        
        # Initialize AI processor with mocks
        self.processor = AIProcessor(
            database=self.mock_db,
            openai_client=self.mock_openai,
            batch_size=5,
            processing_interval=60
        )
        
        # Mock tweet data
        self.mock_tweets = [
            {
                'id': '1234567890',
                'username': 'testuser1',
                'content': 'Just finished reading about AI developments. The future is bright! #AI #technology',
                'created_at': '2024-12-28T12:00:00Z',
                'ai_processed': False
            },
            {
                'id': '1234567891',
                'username': 'testuser2',
                'content': 'Not impressed with the latest tech announcements. Disappointing.',
                'created_at': '2024-12-28T13:00:00Z',
                'ai_processed': False
            },
            {
                'id': '1234567892',
                'username': 'testuser3',
                'content': 'Neutral thoughts on today\'s market movements.',
                'created_at': '2024-12-28T14:00:00Z',
                'ai_processed': False
            }
        ]
        
        # Mock AI analysis results
        self.mock_ai_results = [
            {
                'status': 'completed',
                'tweet_id': '1234567890',
                'ai_result': {
                    'sentiment': 'positive',
                    'topics': ['AI', 'technology'],
                    'summary': 'User is excited about AI developments',
                    'keywords': ['AI', 'technology', 'future'],
                    'confidence': 0.85
                },
                'tokens_used': 45,
                'model_used': 'gpt-3.5-turbo',
                'processing_time': 1.2
            },
            {
                'status': 'completed',
                'tweet_id': '1234567891',
                'ai_result': {
                    'sentiment': 'negative',
                    'topics': ['technology', 'announcements'],
                    'summary': 'User disappointed with tech announcements',
                    'keywords': ['tech', 'announcements', 'disappointing'],
                    'confidence': 0.78
                },
                'tokens_used': 38,
                'model_used': 'gpt-3.5-turbo',
                'processing_time': 0.9
            }
        ]
    
    def test_processor_initialization(self):
        """Test AI processor initialization"""
        self.assertEqual(self.processor.database, self.mock_db)
        self.assertEqual(self.processor.openai_client, self.mock_openai)
        self.assertEqual(self.processor.batch_size, 5)
        self.assertEqual(self.processor.processing_interval, 60)
        self.assertFalse(self.processor.is_running)
        self.assertEqual(self.processor.processed_count, 0)
        self.assertEqual(self.processor.error_count, 0)
    
    def test_get_unprocessed_tweets(self):
        """Test retrieving unprocessed tweets from database"""
        # Mock database response
        self.mock_db.get_unprocessed_tweets.return_value = self.mock_tweets[:2]
        
        tweets = self.processor.get_unprocessed_tweets(limit=2)
        
        self.assertEqual(len(tweets), 2)
        self.assertEqual(tweets[0]['id'], '1234567890')
        self.assertEqual(tweets[1]['id'], '1234567891')
        self.mock_db.get_unprocessed_tweets.assert_called_once_with(limit=2)
    
    def test_get_unprocessed_tweets_empty(self):
        """Test retrieving unprocessed tweets when none exist"""
        # Mock empty database response
        self.mock_db.get_unprocessed_tweets.return_value = []
        
        tweets = self.processor.get_unprocessed_tweets()
        
        self.assertEqual(len(tweets), 0)
        self.mock_db.get_unprocessed_tweets.assert_called_once()
    
    @patch('asyncio.run')
    def test_process_single_tweet_success(self, mock_asyncio_run):
        """Test processing a single tweet successfully"""
        # Mock AI client response
        mock_asyncio_run.return_value = self.mock_ai_results[0]
        
        result = self.processor.process_single_tweet(self.mock_tweets[0])
        
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['tweet_id'], '1234567890')
        self.assertIn('ai_result', result)
        mock_asyncio_run.assert_called_once()
    
    @patch('asyncio.run')
    def test_process_single_tweet_failure(self, mock_asyncio_run):
        """Test processing a single tweet with failure"""
        # Mock AI client failure
        mock_asyncio_run.return_value = {
            'status': 'failed',
            'tweet_id': '1234567890',
            'error_message': 'API rate limit exceeded'
        }
        
        result = self.processor.process_single_tweet(self.mock_tweets[0])
        
        self.assertEqual(result['status'], 'failed')
        self.assertIn('error_message', result)
    
    def test_store_ai_result_success(self):
        """Test storing AI analysis result successfully"""
        # Mock successful database insertion
        self.mock_db.store_ai_result.return_value = True
        
        success = self.processor.store_ai_result(self.mock_ai_results[0])
        
        self.assertTrue(success)
        self.mock_db.store_ai_result.assert_called_once()
    
    def test_store_ai_result_failure(self):
        """Test storing AI analysis result with database error"""
        # Mock database failure
        self.mock_db.store_ai_result.side_effect = Exception("Database error")
        
        success = self.processor.store_ai_result(self.mock_ai_results[0])
        
        self.assertFalse(success)
    
    def test_update_tweet_status_processed(self):
        """Test updating tweet status to processed"""
        # Mock successful database update
        self.mock_db.update_tweet_ai_status.return_value = True
        
        success = self.processor.update_tweet_status('1234567890', True)
        
        self.assertTrue(success)
        self.mock_db.update_tweet_ai_status.assert_called_once_with('1234567890', True)
    
    def test_update_tweet_status_failed(self):
        """Test updating tweet status with database error"""
        # Mock database failure
        self.mock_db.update_tweet_ai_status.side_effect = Exception("Update failed")
        
        success = self.processor.update_tweet_status('1234567890', True)
        
        self.assertFalse(success)
    
    @patch('time.sleep')
    def test_process_batch_success(self, mock_sleep):
        """Test processing a batch of tweets successfully"""
        # Mock dependencies
        self.mock_db.get_unprocessed_tweets.return_value = self.mock_tweets[:2]
        self.mock_db.store_ai_result.return_value = True
        self.mock_db.update_tweet_ai_status.return_value = True
        
        with patch.object(self.processor, 'process_single_tweet') as mock_process:
            mock_process.side_effect = self.mock_ai_results[:2]
            
            results = self.processor.process_batch()
            
            self.assertEqual(len(results), 2)
            self.assertEqual(results[0]['status'], 'completed')
            self.assertEqual(results[1]['status'], 'completed')
            self.assertEqual(mock_process.call_count, 2)
    
    def test_process_batch_empty(self):
        """Test processing batch when no tweets need processing"""
        # Mock empty database response
        self.mock_db.get_unprocessed_tweets.return_value = []
        
        results = self.processor.process_batch()
        
        self.assertEqual(len(results), 0)
    
    @patch('time.sleep')
    def test_process_batch_with_errors(self, mock_sleep):
        """Test processing batch with some errors"""
        # Mock dependencies with mixed results
        self.mock_db.get_unprocessed_tweets.return_value = self.mock_tweets[:2]
        self.mock_db.store_ai_result.return_value = True
        self.mock_db.update_tweet_ai_status.return_value = True
        
        # First tweet succeeds, second fails
        mock_results = [
            self.mock_ai_results[0],
            {'status': 'failed', 'tweet_id': '1234567891', 'error_message': 'Processing error'}
        ]
        
        with patch.object(self.processor, 'process_single_tweet') as mock_process:
            mock_process.side_effect = mock_results
            
            results = self.processor.process_batch()
            
            self.assertEqual(len(results), 2)
            self.assertEqual(results[0]['status'], 'completed')
            self.assertEqual(results[1]['status'], 'failed')
    
    def test_start_background_processing(self):
        """Test starting background processing"""
        with patch('threading.Thread') as mock_thread:
            mock_thread_instance = Mock()
            mock_thread.return_value = mock_thread_instance
            
            self.processor.start_background_processing()
            
            self.assertTrue(self.processor.is_running)
            mock_thread.assert_called_once()
            mock_thread_instance.start.assert_called_once()
    
    def test_stop_background_processing(self):
        """Test stopping background processing"""
        # Set up as if processing is running
        self.processor.is_running = True
        self.processor.processing_thread = Mock()
        
        self.processor.stop_background_processing()
        
        self.assertFalse(self.processor.is_running)
    
    @patch('time.sleep')
    def test_processing_loop_single_iteration(self, mock_sleep):
        """Test one iteration of the processing loop"""
        # Mock dependencies
        self.mock_db.get_unprocessed_tweets.return_value = self.mock_tweets[:1]
        self.mock_db.store_ai_result.return_value = True
        self.mock_db.update_tweet_ai_status.return_value = True
        
        with patch.object(self.processor, 'process_single_tweet') as mock_process:
            mock_process.return_value = self.mock_ai_results[0]
            
            # Set up for single iteration
            self.processor.is_running = True
            
            # Mock sleep to stop after first iteration
            def stop_after_sleep(*args):
                self.processor.is_running = False
            
            mock_sleep.side_effect = stop_after_sleep
            
            self.processor._processing_loop()
            
            self.assertEqual(self.processor.processed_count, 1)
            self.assertEqual(self.processor.error_count, 0)
    
    def test_get_processing_statistics(self):
        """Test getting processing statistics"""
        # Set up some statistics
        self.processor.processed_count = 10
        self.processor.error_count = 2
        self.processor.start_time = time.time() - 3600  # 1 hour ago
        
        stats = self.processor.get_processing_statistics()
        
        self.assertEqual(stats['processed_count'], 10)
        self.assertEqual(stats['error_count'], 2)
        self.assertAlmostEqual(stats['success_rate'], 0.833, places=2)  # 10/12
        self.assertGreater(stats['uptime_seconds'], 3500)  # Roughly 1 hour
        self.assertIn('tweets_per_minute', stats)
    
    def test_get_processing_statistics_no_processing(self):
        """Test getting statistics when no processing has occurred"""
        stats = self.processor.get_processing_statistics()
        
        self.assertEqual(stats['processed_count'], 0)
        self.assertEqual(stats['error_count'], 0)
        self.assertEqual(stats['success_rate'], 0.0)
        self.assertEqual(stats['tweets_per_minute'], 0.0)
    
    def test_reset_statistics(self):
        """Test resetting processing statistics"""
        # Set up some statistics
        self.processor.processed_count = 10
        self.processor.error_count = 2
        
        self.processor.reset_statistics()
        
        self.assertEqual(self.processor.processed_count, 0)
        self.assertEqual(self.processor.error_count, 0)
    
    def test_set_batch_size(self):
        """Test setting batch size"""
        self.processor.set_batch_size(10)
        self.assertEqual(self.processor.batch_size, 10)
    
    def test_set_batch_size_invalid(self):
        """Test setting invalid batch size"""
        with self.assertRaises(ValueError):
            self.processor.set_batch_size(0)
        
        with self.assertRaises(ValueError):
            self.processor.set_batch_size(-1)
    
    def test_set_processing_interval(self):
        """Test setting processing interval"""
        self.processor.set_processing_interval(120)
        self.assertEqual(self.processor.processing_interval, 120)
    
    def test_set_processing_interval_invalid(self):
        """Test setting invalid processing interval"""
        with self.assertRaises(ValueError):
            self.processor.set_processing_interval(0)
        
        with self.assertRaises(ValueError):
            self.processor.set_processing_interval(-10)
    
    def test_get_queue_status(self):
        """Test getting queue status"""
        # Mock database response
        self.mock_db.get_unprocessed_count.return_value = 15
        self.mock_db.get_total_tweets_count.return_value = 100
        
        status = self.processor.get_queue_status()
        
        self.assertEqual(status['unprocessed_count'], 15)
        self.assertEqual(status['total_count'], 100)
        self.assertEqual(status['processed_count'], 85)
        self.assertEqual(status['completion_percentage'], 85.0)
    
    def test_process_specific_tweet_by_id(self):
        """Test processing a specific tweet by ID"""
        # Mock database response
        self.mock_db.get_tweet_by_id.return_value = self.mock_tweets[0]
        self.mock_db.store_ai_result.return_value = True
        self.mock_db.update_tweet_ai_status.return_value = True
        
        with patch.object(self.processor, 'process_single_tweet') as mock_process:
            mock_process.return_value = self.mock_ai_results[0]
            
            result = self.processor.process_specific_tweet('1234567890')
            
            self.assertEqual(result['status'], 'completed')
            self.mock_db.get_tweet_by_id.assert_called_once_with('1234567890')
    
    def test_process_specific_tweet_not_found(self):
        """Test processing a specific tweet that doesn't exist"""
        # Mock database response
        self.mock_db.get_tweet_by_id.return_value = None
        
        result = self.processor.process_specific_tweet('nonexistent')
        
        self.assertEqual(result['status'], 'not_found')
        self.assertEqual(result['message'], 'Tweet not found')
    
    def test_reprocess_failed_tweets(self):
        """Test reprocessing previously failed tweets"""
        # Mock database response for failed tweets
        failed_tweets = [
            dict(self.mock_tweets[0], ai_processed=False, has_ai_error=True)
        ]
        self.mock_db.get_failed_ai_tweets.return_value = failed_tweets
        self.mock_db.store_ai_result.return_value = True
        self.mock_db.update_tweet_ai_status.return_value = True
        self.mock_db.clear_ai_error.return_value = True
        
        with patch.object(self.processor, 'process_single_tweet') as mock_process:
            mock_process.return_value = self.mock_ai_results[0]
            
            results = self.processor.reprocess_failed_tweets()
            
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]['status'], 'completed')
            self.mock_db.get_failed_ai_tweets.assert_called_once()
    
    def test_health_check(self):
        """Test health check functionality"""
        self.processor.is_running = True
        self.processor.last_activity = time.time()
        
        health = self.processor.health_check()
        
        self.assertTrue(health['is_healthy'])
        self.assertTrue(health['is_running'])
        self.assertIsNotNone(health['last_activity'])
        self.assertIn('uptime', health)
    
    def test_health_check_unhealthy(self):
        """Test health check when processor is unhealthy"""
        self.processor.is_running = False
        self.processor.last_activity = time.time() - 7200  # 2 hours ago
        
        health = self.processor.health_check()
        
        self.assertFalse(health['is_healthy'])
        self.assertFalse(health['is_running'])


if __name__ == '__main__':
    unittest.main() 