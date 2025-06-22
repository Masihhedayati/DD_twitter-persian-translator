import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio
import time
import tempfile
import shutil
from core.polling_scheduler import PollingScheduler
from core.database import Database


class TestPollingScheduler(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = f"{self.temp_dir}/test.db"
        self.media_path = f"{self.temp_dir}/media"
        
        # Initialize scheduler with test configuration
        self.config = {
            'TWITTER_API_KEY': 'test_key',
            'MONITORED_USERS': 'user1,user2,user3',
            'CHECK_INTERVAL': 5,  # 5 seconds for testing
            'MEDIA_STORAGE_PATH': self.media_path,
            'DATABASE_PATH': self.db_path
        }
        
        self.scheduler = PollingScheduler(self.config)
        
        # Mock tweet data
        self.mock_tweets = [
            {
                'id': '1234567890',
                'username': 'user1',
                'content': 'Test tweet with media',
                'created_at': '2024-12-28T12:00:00Z',
                'media': [
                    {'type': 'image', 'url': 'https://example.com/image.jpg'}
                ]
            },
            {
                'id': '1234567891',
                'username': 'user1',
                'content': 'Test tweet without media',
                'created_at': '2024-12-28T11:30:00Z',
                'media': []
            }
        ]
    
    def tearDown(self):
        """Clean up test files"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_init_creates_components(self):
        """Test scheduler initialization creates all required components"""
        self.assertIsNotNone(self.scheduler.twitter_client)
        self.assertIsNotNone(self.scheduler.media_extractor)
        self.assertIsNotNone(self.scheduler.db)
        self.assertEqual(self.scheduler.monitored_users, ['user1', 'user2', 'user3'])
        self.assertEqual(self.scheduler.check_interval, 5)
        self.assertFalse(self.scheduler.is_running)
    
    def test_parse_monitored_users(self):
        """Test parsing monitored users from config"""
        # Test comma-separated string
        users = self.scheduler._parse_monitored_users('user1,user2,user3')
        self.assertEqual(users, ['user1', 'user2', 'user3'])
        
        # Test with spaces
        users = self.scheduler._parse_monitored_users('user1, user2 , user3')
        self.assertEqual(users, ['user1', 'user2', 'user3'])
        
        # Test single user
        users = self.scheduler._parse_monitored_users('singleuser')
        self.assertEqual(users, ['singleuser'])
        
        # Test empty string
        users = self.scheduler._parse_monitored_users('')
        self.assertEqual(users, [])
    
    @patch('core.polling_scheduler.TwitterClient')
    def test_poll_user_tweets_new_tweets(self, mock_twitter_class):
        """Test polling for new tweets from a user"""
        # Mock Twitter client
        mock_twitter = MagicMock()
        mock_twitter.get_user_tweets.return_value = self.mock_tweets
        mock_twitter_class.return_value = mock_twitter
        
        # Run poll
        result = self.scheduler._poll_user_tweets('user1')
        
        # Verify Twitter client was called
        mock_twitter.get_user_tweets.assert_called_once_with('user1', count=20)
        
        # Verify results
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['id'], '1234567890')
        self.assertEqual(result[1]['id'], '1234567891')
    
    @patch('core.polling_scheduler.TwitterClient')
    def test_poll_user_tweets_error_handling(self, mock_twitter_class):
        """Test error handling during tweet polling"""
        # Mock Twitter client to raise exception
        mock_twitter = MagicMock()
        mock_twitter.get_user_tweets.side_effect = Exception("API Error")
        mock_twitter_class.return_value = mock_twitter
        
        # Run poll - should not raise exception
        result = self.scheduler._poll_user_tweets('user1')
        
        # Should return empty list on error
        self.assertEqual(result, [])
    
    def test_is_new_tweet(self):
        """Test checking if tweet is new (not in database)"""
        # Mock database check
        with patch.object(self.scheduler.db, 'tweet_exists') as mock_exists:
            # Test new tweet
            mock_exists.return_value = False
            self.assertTrue(self.scheduler._is_new_tweet('1234567890'))
            
            # Test existing tweet
            mock_exists.return_value = True
            self.assertFalse(self.scheduler._is_new_tweet('1234567890'))
    
    def test_save_tweet_to_database(self):
        """Test saving tweet to database"""
        with patch.object(self.scheduler.db, 'insert_tweet') as mock_insert:
            tweet = self.mock_tweets[0]
            
            result = self.scheduler._save_tweet_to_database(tweet)
            
            # Verify database insert was called
            mock_insert.assert_called_once()
            call_args = mock_insert.call_args[0][0]  # First argument
            
            self.assertEqual(call_args['id'], '1234567890')
            self.assertEqual(call_args['username'], 'user1')
            self.assertEqual(call_args['content'], 'Test tweet with media')
            self.assertTrue(result)
    
    def test_save_tweet_to_database_error(self):
        """Test error handling when saving tweet to database"""
        with patch.object(self.scheduler.db, 'insert_tweet') as mock_insert:
            mock_insert.side_effect = Exception("Database error")
            tweet = self.mock_tweets[0]
            
            result = self.scheduler._save_tweet_to_database(tweet)
            
            # Should return False on error
            self.assertFalse(result)
    
    @patch('core.polling_scheduler.MediaExtractor')
    def test_process_tweet_media_with_media(self, mock_extractor_class):
        """Test processing tweet media when media is present"""
        # Mock media extractor
        mock_extractor = MagicMock()
        mock_extractor.download_tweet_media.return_value = [
            {'status': 'completed', 'local_path': '/media/test.jpg'}
        ]
        mock_extractor_class.return_value = mock_extractor
        
        tweet = self.mock_tweets[0]  # Tweet with media
        
        result = self.scheduler._process_tweet_media(tweet)
        
        # Verify media extractor was called
        mock_extractor.download_tweet_media.assert_called_once_with(tweet)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['status'], 'completed')
    
    def test_process_tweet_media_without_media(self):
        """Test processing tweet when no media is present"""
        tweet = self.mock_tweets[1]  # Tweet without media
        
        result = self.scheduler._process_tweet_media(tweet)
        
        # Should return empty list
        self.assertEqual(result, [])
    
    @patch('core.polling_scheduler.MediaExtractor')
    def test_process_tweet_media_error(self, mock_extractor_class):
        """Test error handling during media processing"""
        # Mock media extractor to raise exception
        mock_extractor = MagicMock()
        mock_extractor.download_tweet_media.side_effect = Exception("Download error")
        mock_extractor_class.return_value = mock_extractor
        
        tweet = self.mock_tweets[0]
        
        result = self.scheduler._process_tweet_media(tweet)
        
        # Should return empty list on error
        self.assertEqual(result, [])
    
    def test_update_tweet_processing_status(self):
        """Test updating tweet processing status in database"""
        with patch.object(self.scheduler.db, 'update_tweet_processing_status') as mock_update:
            tweet_id = '1234567890'
            media_results = [{'status': 'completed'}]
            
            self.scheduler._update_tweet_processing_status(tweet_id, media_results)
            
            # Verify database update was called
            mock_update.assert_called_once_with(tweet_id, True, True)
    
    def test_poll_all_users(self):
        """Test polling all monitored users"""
        with patch.object(self.scheduler, '_poll_user_tweets') as mock_poll:
            mock_poll.return_value = self.mock_tweets
            
            with patch.object(self.scheduler, '_is_new_tweet') as mock_is_new:
                mock_is_new.return_value = True
                
                with patch.object(self.scheduler, '_save_tweet_to_database') as mock_save:
                    mock_save.return_value = True
                    
                    with patch.object(self.scheduler, '_process_tweet_media') as mock_process:
                        mock_process.return_value = []
                        
                        result = self.scheduler._poll_all_users()
                        
                        # Should poll all 3 users
                        self.assertEqual(mock_poll.call_count, 3)
                        
                        # Should process all tweets from all users
                        expected_total_tweets = len(self.mock_tweets) * 3  # 2 tweets * 3 users
                        self.assertEqual(mock_save.call_count, expected_total_tweets)
    
    def test_poll_all_users_duplicate_filtering(self):
        """Test that duplicate tweets are filtered out"""
        with patch.object(self.scheduler, '_poll_user_tweets') as mock_poll:
            mock_poll.return_value = self.mock_tweets
            
            with patch.object(self.scheduler, '_is_new_tweet') as mock_is_new:
                # First tweet is new, second is duplicate
                mock_is_new.side_effect = [True, False] * 3  # For all 3 users
                
                with patch.object(self.scheduler, '_save_tweet_to_database') as mock_save:
                    mock_save.return_value = True
                    
                    result = self.scheduler._poll_all_users()
                    
                    # Should only save new tweets (1 per user)
                    self.assertEqual(mock_save.call_count, 3)
    
    def test_start_scheduler(self):
        """Test starting the scheduler"""
        with patch('schedule.every') as mock_every:
            mock_job = MagicMock()
            mock_every.return_value.seconds.do.return_value = mock_job
            
            with patch.object(self.scheduler, '_run_scheduler_loop') as mock_loop:
                self.scheduler.start()
                
                # Verify schedule was configured
                mock_every.assert_called_once_with(5)  # Check interval
                mock_every.return_value.seconds.do.assert_called_once()
                
                # Verify scheduler is marked as running
                self.assertTrue(self.scheduler.is_running)
                
                # Verify loop was started
                mock_loop.assert_called_once()
    
    def test_stop_scheduler(self):
        """Test stopping the scheduler"""
        self.scheduler.is_running = True
        
        self.scheduler.stop()
        
        self.assertFalse(self.scheduler.is_running)
    
    def test_get_status(self):
        """Test getting scheduler status"""
        status = self.scheduler.get_status()
        
        self.assertIn('is_running', status)
        self.assertIn('monitored_users', status)
        self.assertIn('check_interval', status)
        self.assertIn('last_poll_time', status)
        self.assertIn('total_tweets_processed', status)
        self.assertIn('last_error', status)
        
        self.assertEqual(status['monitored_users'], ['user1', 'user2', 'user3'])
        self.assertEqual(status['check_interval'], 5)
    
    def test_get_recent_activity(self):
        """Test getting recent polling activity"""
        # Add some mock activity
        self.scheduler.recent_activity = [
            {'timestamp': '2024-12-28T12:00:00Z', 'user': 'user1', 'tweets_found': 2},
            {'timestamp': '2024-12-28T11:59:00Z', 'user': 'user2', 'tweets_found': 0}
        ]
        
        activity = self.scheduler.get_recent_activity(limit=10)
        
        self.assertEqual(len(activity), 2)
        self.assertEqual(activity[0]['user'], 'user1')
        self.assertEqual(activity[0]['tweets_found'], 2)
    
    @patch('time.sleep')
    @patch('schedule.run_pending')
    def test_run_scheduler_loop(self, mock_run_pending, mock_sleep):
        """Test the main scheduler loop"""
        # Mock to stop after 2 iterations
        self.scheduler.is_running = True
        call_count = 0
        
        def stop_after_calls():
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                self.scheduler.is_running = False
        
        mock_run_pending.side_effect = stop_after_calls
        
        self.scheduler._run_scheduler_loop()
        
        # Verify schedule.run_pending was called
        self.assertEqual(mock_run_pending.call_count, 2)
        self.assertEqual(mock_sleep.call_count, 2)


if __name__ == '__main__':
    unittest.main() 