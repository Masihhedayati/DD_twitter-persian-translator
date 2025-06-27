import schedule
import time
import logging
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from core.twitter_client import TwitterClient
from core.media_extractor import MediaExtractor
from core.ai_processor import AIProcessor
from core.openai_client import OpenAIClient
from core.telegram_bot import TelegramNotifier, create_telegram_notifier


class PollingScheduler:
    """
    Background scheduler that polls Twitter for new tweets from monitored users
    Handles tweet collection, media download, and database storage
    """
    
    def __init__(self, config: Dict[str, Any], database=None):
        """
        Initialize polling scheduler
        
        Args:
            config: Configuration dictionary containing API keys and settings
            database: Database instance (optional, will use config path if not provided)
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.twitter_client = TwitterClient(config.get('TWITTER_API_KEY', ''))
        self.media_extractor = MediaExtractor(config.get('MEDIA_STORAGE_PATH', './media'))
        
        # Use provided database instance
        if database:
            self.db = database
        else:
            # Database is required - no fallback to old SQLite system
            raise ValueError("Database instance is required for PollingScheduler")
        
        # Initialize AI components if OpenAI API key is available
        openai_key = config.get('OPENAI_API_KEY', '')
        if openai_key:
            self.openai_client = OpenAIClient(
                openai_key, 
                model=config.get('OPENAI_MODEL', 'o1-mini'),
                max_tokens=config.get('OPENAI_MAX_TOKENS', 1000),
                database=self.db
            )
            self.ai_processor = AIProcessor(
                database=self.db,
                openai_client=self.openai_client,
                batch_size=int(config.get('AI_BATCH_SIZE', 5)),
                processing_interval=int(config.get('AI_PROCESSING_INTERVAL', 120))
            )
            self.ai_enabled = True
            self.logger.info("AI processing enabled")
        else:
            self.openai_client = None
            self.ai_processor = None
            self.ai_enabled = False
            self.logger.warning("AI processing disabled - no OpenAI API key provided")
        
        # Initialize Telegram notifier if bot token and chat ID are available
        telegram_token = config.get('TELEGRAM_BOT_TOKEN', '')
        telegram_chat_id = config.get('TELEGRAM_CHAT_ID', '')
        if telegram_token and telegram_chat_id:
            telegram_config = {
                'TELEGRAM_BOT_TOKEN': telegram_token,
                'TELEGRAM_CHAT_ID': telegram_chat_id
            }
            self.telegram_notifier = create_telegram_notifier(telegram_config, self.db)
            self.telegram_enabled = True
            self.logger.info("Telegram notifications enabled")
        else:
            self.telegram_notifier = None
            self.telegram_enabled = False
            self.logger.warning("Telegram notifications disabled - missing bot token or chat ID")
        
        # Notification configuration - handle both string and boolean values
        def parse_bool(value, default='false'):
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() == 'true'
            return default.lower() == 'true'
        
        self.notification_enabled = parse_bool(config.get('NOTIFICATION_ENABLED', 'true'), 'true')
        self.notify_all_tweets = parse_bool(config.get('NOTIFY_ALL_TWEETS', 'false'), 'false')
        self.notify_ai_processed_only = parse_bool(config.get('NOTIFY_AI_PROCESSED_ONLY', 'true'), 'true')
        self.notification_delay = int(config.get('NOTIFICATION_DELAY', 10))  # seconds to wait for AI processing
        
        # Load monitored users from database (persistent storage)
        self.monitored_users = self.db.get_monitored_users()
        self.check_interval = int(config.get('CHECK_INTERVAL', 60))  # seconds
        
        # Scheduler state
        self.is_running = False
        self.scheduler_thread = None
        self.last_poll_time = None
        self.total_tweets_processed = 0
        self.last_error = None
        self.recent_activity = []  # Keep track of recent polling activity
        
        # Configuration
        self.max_tweets_per_poll = 20  # Limit tweets per user per poll
        self.max_activity_history = 100  # Keep last 100 activities
        
        self.logger.info(f"Initialized PollingScheduler for {len(self.monitored_users)} users")
        self.logger.info(f"Check interval: {self.check_interval} seconds")
        self.logger.info(f"Monitored users: {', '.join(self.monitored_users)}")
        self.logger.info(f"Notifications enabled: {self.notification_enabled and self.telegram_enabled}")
        if self.notification_enabled and self.telegram_enabled:
            self.logger.info(f"Notification mode: {'AI processed only' if self.notify_ai_processed_only else 'All tweets'}")
            self.logger.info(f"Notification delay: {self.notification_delay} seconds")
    
    def _parse_monitored_users(self, users_str: str) -> List[str]:
        """
        Parse comma-separated list of usernames from config
        
        Args:
            users_str: Comma-separated usernames string
            
        Returns:
            List of cleaned usernames
        """
        if not users_str:
            return []
        
        users = [user.strip() for user in users_str.split(',')]
        users = [user for user in users if user]  # Remove empty strings
        
        return users
    
    def start(self):
        """Start the polling scheduler in a background thread"""
        if self.is_running:
            self.logger.warning("Scheduler is already running")
            return
        
        if not self.monitored_users:
            self.logger.error("No users to monitor. Check MONITORED_USERS configuration.")
            return
        
        if not self.twitter_client.validate_api_key():
            self.logger.error("Invalid Twitter API key. Check TWITTER_API_KEY configuration.")
            return
        
        self.logger.info("Starting polling scheduler...")
        
        # Schedule the polling job
        schedule.every(self.check_interval).seconds.do(self._poll_all_users)
        
        # Start scheduler thread
        self.is_running = True
        self.scheduler_thread = threading.Thread(target=self._run_scheduler_loop, daemon=True)
        self.scheduler_thread.start()
        
        # Start AI processing if enabled
        if self.ai_enabled and self.ai_processor:
            self.ai_processor.start_background_processing()
            self.logger.info("AI background processing started")
        
        # Start Telegram notifier if enabled
        if self.telegram_enabled and self.telegram_notifier:
            if self.telegram_notifier.start_worker():
                self.logger.info("Telegram notification service started")
            else:
                self.logger.error("Failed to start Telegram notification service")
        
        # Schedule initial poll to run soon but not immediately
        threading.Thread(target=self._initial_poll, daemon=True).start()
        
        self.logger.info("Polling scheduler started successfully")
    
    def stop(self):
        """Stop the polling scheduler"""
        if not self.is_running:
            self.logger.warning("Scheduler is not currently running")
            return
        
        self.logger.info("Stopping polling scheduler...")
        self.is_running = False
        
        # Stop AI processing if enabled
        if self.ai_enabled and self.ai_processor:
            self.ai_processor.stop_background_processing()
            self.logger.info("AI background processing stopped")
        
        # Stop Telegram notifier if enabled
        if self.telegram_enabled and self.telegram_notifier:
            self.telegram_notifier.stop_worker()
            self.logger.info("Telegram notification service stopped")
        
        # Clear scheduled jobs
        schedule.clear()
        
        # Wait for thread to finish
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=5)
        
        self.logger.info("Polling scheduler stopped")
    
    def _run_scheduler_loop(self):
        """Main scheduler loop that runs in background thread"""
        self.logger.info("Scheduler loop started")
        
        while self.is_running:
            try:
                schedule.run_pending()
                time.sleep(1)  # Check every second
            except Exception as e:
                self.logger.error(f"Error in scheduler loop: {e}")
                self.last_error = str(e)
                time.sleep(5)  # Wait longer on error
        
        self.logger.info("Scheduler loop ended")
    
    def _poll_all_users(self) -> Dict[str, Any]:
        """
        Poll all monitored users for new tweets
        
        Returns:
            Summary of polling results
        """
        start_time = datetime.now()
        self.logger.info(f"Starting poll for {len(self.monitored_users)} users")
        
        results = {
            'total_tweets_found': 0,
            'new_tweets_saved': 0,
            'media_downloads_started': 0,
            'ai_processing_triggered': 0,
            'notifications_queued': 0,
            'errors': [],
            'start_time': start_time.isoformat(),
            'users_polled': 0
        }
        
        for username in self.monitored_users:
            try:
                user_results = self._poll_single_user(username)
                results['total_tweets_found'] += user_results['tweets_found']
                results['new_tweets_saved'] += user_results['new_tweets']
                results['media_downloads_started'] += user_results['media_downloads']
                results['users_polled'] += 1
                
                # Trigger AI processing for new tweets if enabled
                if self.ai_enabled and user_results['new_tweets'] > 0:
                    try:
                        ai_triggered = self._trigger_ai_processing_for_new_tweets()
                        results['ai_processing_triggered'] += ai_triggered
                    except Exception as e:
                        error_msg = f"Error triggering AI processing: {e}"
                        self.logger.error(error_msg)
                        results['errors'].append(error_msg)
                
                # Trigger notifications for new tweets if enabled
                if self.notification_enabled and self.telegram_enabled and user_results['new_tweets'] > 0:
                    try:
                        notifications_queued = self._trigger_notifications_for_new_tweets(username)
                        results['notifications_queued'] += notifications_queued
                    except Exception as e:
                        error_msg = f"Error triggering notifications: {e}"
                        self.logger.error(error_msg)
                        results['errors'].append(error_msg)
                
                # Track activity
                self._track_activity(username, user_results['tweets_found'], user_results['new_tweets'])
                
            except Exception as e:
                error_msg = f"Error polling user {username}: {e}"
                self.logger.error(error_msg)
                results['errors'].append(error_msg)
        
        # Update poll time and statistics
        self.last_poll_time = start_time.isoformat()
        self.total_tweets_processed += results['new_tweets_saved']
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        results['end_time'] = end_time.isoformat()
        results['duration_seconds'] = duration
        
        self.logger.info(f"Poll completed in {duration:.2f}s: {results['new_tweets_saved']} new tweets from {results['users_polled']} users")
        
        return results
    
    def _poll_single_user(self, username: str) -> Dict[str, Any]:
        """
        Poll a single user for new tweets
        
        Args:
            username: Twitter username to poll
            
        Returns:
            Results dictionary
        """
        self.logger.debug(f"Polling user: {username}")
        
        results = {
            'tweets_found': 0,
            'new_tweets': 0,
            'media_downloads': 0
        }
        
        try:
            # Get recent tweets from user
            tweets = self._poll_user_tweets(username)
            results['tweets_found'] = len(tweets)
            
            if not tweets:
                self.logger.debug(f"No tweets found for user {username}")
                return results
            
            # Process each tweet
            for tweet in tweets:
                try:
                    # Check if tweet is new
                    if not self._is_new_tweet(tweet['id']):
                        self.logger.debug(f"Tweet {tweet['id']} already exists, skipping")
                        continue
                    
                    # Save tweet to database
                    if self._save_tweet_to_database(tweet):
                        results['new_tweets'] += 1
                        self.logger.debug(f"Saved new tweet: {tweet['id']}")
                        
                        # Process media if present
                        media_results = self._process_tweet_media(tweet)
                        if media_results:
                            results['media_downloads'] += len(media_results)
                            self.logger.debug(f"Started {len(media_results)} media downloads for tweet {tweet['id']}")
                        
                        # Update processing status
                        self._update_tweet_processing_status(tweet['id'], media_results)
                    
                except Exception as e:
                    self.logger.error(f"Error processing tweet {tweet.get('id', 'unknown')}: {e}")
                    continue
        
        except Exception as e:
            self.logger.error(f"Error in _poll_single_user for {username}: {e}")
            raise
        
        return results
    
    def _poll_user_tweets(self, username: str) -> List[Dict]:
        """
        Get recent tweets from a user using Twitter client
        
        Args:
            username: Twitter username
            
        Returns:
            List of tweet dictionaries
        """
        try:
            tweets = self.twitter_client.get_user_tweets(username, count=self.max_tweets_per_poll)
            return tweets
        except Exception as e:
            self.logger.error(f"Failed to get tweets for user {username}: {e}")
            return []
    
    def _is_new_tweet(self, tweet_id: str) -> bool:
        """
        Check if tweet is new (not already in database)
        
        Args:
            tweet_id: Tweet ID to check
            
        Returns:
            True if tweet is new
        """
        try:
            return not self.db.tweet_exists(tweet_id)
        except Exception as e:
            self.logger.error(f"Error checking if tweet {tweet_id} exists: {e}")
            return False  # Assume exists to avoid duplicates
    
    def _save_tweet_to_database(self, tweet: Dict) -> bool:
        """
        Save tweet to database
        
        Args:
            tweet: Tweet dictionary
            
        Returns:
            True if saved successfully
        """
        try:
            # Convert tweet to database format
            tweet_data = {
                'id': tweet['id'],
                'username': tweet['username'],
                'content': tweet['content'],
                'created_at': tweet['created_at'],
                'retweet_count': tweet.get('retweet_count', 0),
                'like_count': tweet.get('like_count', 0),
                'reply_count': tweet.get('reply_count', 0),
                'quote_count': tweet.get('quote_count', 0),
                'language': tweet.get('language', 'unknown'),
                'has_media': len(tweet.get('media', [])) > 0,
                'media_count': len(tweet.get('media', [])),
                'collected_at': datetime.now().isoformat()
            }
            
            self.db.insert_tweet(tweet_data)
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save tweet {tweet.get('id', 'unknown')}: {e}")
            return False
    
    def _process_tweet_media(self, tweet: Dict) -> List[Dict]:
        """
        Process and download media from tweet
        
        Args:
            tweet: Tweet dictionary
            
        Returns:
            List of media download results
        """
        if not tweet.get('media'):
            return []
        
        try:
            # Extract media from tweet
            media_items = self.media_extractor.extract_media_from_tweet(tweet)
            if not media_items:
                return []
            
            # Download media files
            downloaded_media = self.media_extractor.download_media(tweet['id'], media_items)
            
            # Store media information in database
            for media_data in downloaded_media:
                self.db.store_media(media_data)
            
            self.logger.info(f"Processed {len(downloaded_media)} media files for tweet {tweet['id']}")
            return downloaded_media
            
        except Exception as e:
            self.logger.error(f"Failed to process media for tweet {tweet.get('id', 'unknown')}: {e}")
            return []
    
    def _update_tweet_processing_status(self, tweet_id: str, media_results: List[Dict]):
        """
        Update tweet processing status in database
        
        Args:
            tweet_id: Tweet ID
            media_results: Results from media processing
        """
        try:
            # Determine if media was successfully downloaded
            media_downloaded = len(media_results) > 0 and all(
                result.get('status') == 'completed' for result in media_results
            )
            
            # Update database
            self.db.update_tweet_processing_status(
                tweet_id=tweet_id,
                media_downloaded=media_downloaded,
                ai_processed=False  # Will be updated later by AI processor
            )
            
        except Exception as e:
            self.logger.error(f"Failed to update processing status for tweet {tweet_id}: {e}")
    
    def _track_activity(self, username: str, tweets_found: int, new_tweets: int):
        """
        Track polling activity for monitoring
        
        Args:
            username: User that was polled
            tweets_found: Total tweets found
            new_tweets: New tweets saved
        """
        activity = {
            'timestamp': datetime.now().isoformat(),
            'user': username,
            'tweets_found': tweets_found,
            'new_tweets': new_tweets
        }
        
        self.recent_activity.append(activity)
        
        # Keep only recent activity
        if len(self.recent_activity) > self.max_activity_history:
            self.recent_activity = self.recent_activity[-self.max_activity_history:]
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current scheduler status
        
        Returns:
            Status dictionary
        """
        return {
            'is_running': self.is_running,
            'monitored_users': self.monitored_users,
            'check_interval': self.check_interval,
            'last_poll_time': self.last_poll_time,
            'total_tweets_processed': self.total_tweets_processed,
            'last_error': self.last_error,
            'scheduler_thread_alive': self.scheduler_thread.is_alive() if self.scheduler_thread else False
        }
    
    def get_recent_activity(self, limit: int = 20) -> List[Dict]:
        """
        Get recent polling activity
        
        Args:
            limit: Maximum number of activities to return
            
        Returns:
            List of recent activities
        """
        return self.recent_activity[-limit:] if self.recent_activity else []
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get detailed statistics about polling performance
        
        Returns:
            Statistics dictionary
        """
        try:
            # Get database statistics
            db_stats = self.db.get_stats()
            
            # Calculate polling statistics
            total_activities = len(self.recent_activity)
            total_tweets_found = sum(activity['tweets_found'] for activity in self.recent_activity)
            total_new_tweets = sum(activity['new_tweets'] for activity in self.recent_activity)
            
            # Calculate averages
            avg_tweets_per_poll = total_tweets_found / total_activities if total_activities > 0 else 0
            avg_new_tweets_per_poll = total_new_tweets / total_activities if total_activities > 0 else 0
            
            # Get Telegram stats if enabled
            telegram_stats = {}
            if self.telegram_enabled:
                try:
                    telegram_status = self.get_telegram_status()
                    telegram_stats = {
                        'enabled': True,
                        'messages_sent': telegram_status.get('messages_sent', 0),
                        'messages_failed': telegram_status.get('messages_failed', 0),
                        'success_rate': telegram_status.get('success_rate', 0.0),
                        'is_running': telegram_status.get('is_running', False)
                    }
                except Exception as e:
                    telegram_stats = {'enabled': True, 'error': str(e)}
            else:
                telegram_stats = {'enabled': False}

            return {
                'database_stats': db_stats,
                'polling_stats': {
                    'total_polls': total_activities,
                    'total_tweets_found': total_tweets_found,
                    'total_new_tweets': total_new_tweets,
                    'avg_tweets_per_poll': round(avg_tweets_per_poll, 2),
                    'avg_new_tweets_per_poll': round(avg_new_tweets_per_poll, 2)
                },
                'scheduler_stats': {
                    'is_running': self.is_running,
                    'monitored_users_count': len(self.monitored_users),
                    'check_interval': self.check_interval,
                    'total_tweets_processed_lifetime': self.total_tweets_processed
                },
                'telegram_stats': telegram_stats
            }
        except Exception as e:
            self.logger.error(f"Error getting statistics: {e}")
            return {'error': str(e)}
    
    def force_poll_now(self) -> Dict[str, Any]:
        """
        Force an immediate poll of all users (for testing/manual triggers)
        
        Returns:
            Poll results
        """
        self.logger.info("Manual poll triggered")
        return self._poll_all_users()
    
    def add_user(self, username: str) -> bool:
        """
        Add a user to monitoring list
        
        Args:
            username: Username to add
            
        Returns:
            True if added successfully
        """
        if username not in self.monitored_users:
            # Update in-memory list
            self.monitored_users.append(username)
            # Update database
            if self.db.add_monitored_user(username):
                self.logger.info(f"Added user {username} to monitoring list")
                return True
            else:
                # Rollback in-memory change if database update failed
                self.monitored_users.remove(username)
                self.logger.error(f"Failed to add user {username} to database")
                return False
        else:
            self.logger.warning(f"User {username} is already being monitored")
            return False
    
    def remove_user(self, username: str) -> bool:
        """
        Remove a user from monitoring list
        
        Args:
            username: Username to remove
            
        Returns:
            True if removed successfully
        """
        if username in self.monitored_users:
            # Update in-memory list
            self.monitored_users.remove(username)
            # Update database
            if self.db.remove_monitored_user(username):
                self.logger.info(f"Removed user {username} from monitoring list")
                return True
            else:
                # Rollback in-memory change if database update failed
                self.monitored_users.append(username)
                self.logger.error(f"Failed to remove user {username} from database")
                return False
        else:
            self.logger.warning(f"User {username} is not being monitored")
            return False
    
    def _trigger_ai_processing_for_new_tweets(self) -> int:
        """
        Trigger AI processing for recently added tweets
        
        Returns:
            Number of tweets queued for AI processing
        """
        if not self.ai_enabled:
            return 0
        
        try:
            # Get a small batch of unprocessed tweets for immediate processing
            unprocessed_tweets = self.db.get_unprocessed_tweets(limit=5)
            
            if not unprocessed_tweets:
                return 0
            
            # Process tweets immediately for rapid response
            processed_count = 0
            for tweet in unprocessed_tweets:
                try:
                    # Use AI processor to analyze the tweet
                    result = self.ai_processor.process_specific_tweet(tweet['id'])
                    if result.get('status') == 'completed':
                        processed_count += 1
                        self.logger.info(f"AI processed tweet {tweet['id']} immediately")
                    else:
                        self.logger.warning(f"AI processing failed for tweet {tweet['id']}: "
                                          f"{result.get('error_message', 'Unknown error')}")
                except Exception as e:
                    self.logger.error(f"Error processing tweet {tweet.get('id')} with AI: {e}")
            
            return processed_count
            
        except Exception as e:
            self.logger.error(f"Error triggering AI processing: {e}")
            return 0
    
    def get_ai_status(self) -> Dict[str, Any]:
        """
        Get AI processing status and statistics
        
        Returns:
            AI status information
        """
        if not self.ai_enabled:
            return {
                'enabled': False,
                'message': 'AI processing is disabled'
            }
        
        try:
            ai_stats = self.ai_processor.get_processing_statistics()
            queue_status = self.ai_processor.get_queue_status()
            health = self.ai_processor.health_check()
            
            return {
                'enabled': True,
                'is_running': ai_stats['is_running'],
                'is_healthy': health['is_healthy'],
                'processed_count': ai_stats['processed_count'],
                'error_count': ai_stats['error_count'],
                'success_rate': ai_stats['success_rate'],
                'queue_size': queue_status['unprocessed_count'],
                'total_cost': ai_stats.get('total_cost', 0.0),
                'total_tokens': ai_stats.get('total_tokens_used', 0),
                'uptime_seconds': ai_stats['uptime_seconds'],
                'last_activity': ai_stats['last_activity']
            }
            
        except Exception as e:
            self.logger.error(f"Error getting AI status: {e}")
            return {
                'enabled': True,
                'error': str(e)
            }
    
    def force_ai_processing(self, batch_size: int = 10) -> Dict[str, Any]:
        """
        Force immediate AI processing of unprocessed tweets
        
        Args:
            batch_size: Number of tweets to process
            
        Returns:
            Processing results
        """
        if not self.ai_enabled:
            return {
                'success': False,
                'message': 'AI processing is disabled'
            }
        
        try:
            self.logger.info(f"Forcing AI processing of {batch_size} tweets")
            results = self.ai_processor.process_batch()
            
            return {
                'success': True,
                'processed_count': len([r for r in results if r.get('status') == 'completed']),
                'error_count': len([r for r in results if r.get('status') == 'failed']),
                'total_tweets': len(results),
                'results': results
            }
            
        except Exception as e:
            self.logger.error(f"Error forcing AI processing: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def pause_ai_processing(self):
        """Pause AI processing temporarily"""
        if self.ai_enabled and self.ai_processor:
            self.ai_processor.pause_processing()
            self.logger.info("AI processing paused")
    
    def resume_ai_processing(self):
        """Resume AI processing"""
        if self.ai_enabled and self.ai_processor:
            self.ai_processor.resume_processing()
            self.logger.info("AI processing resumed")
    
    def is_ai_paused(self) -> bool:
        """Check if AI processing is paused"""
        if not self.ai_enabled:
            return False
        return self.ai_processor.is_paused()
    
    def _trigger_notifications_for_new_tweets(self, username: str) -> int:
        """
        Trigger Telegram notifications for new tweets from a specific user
        
        Args:
            username: Username to get notifications for
            
        Returns:
            Number of notifications queued
        """
        if not self.telegram_enabled:
            return 0
        
        try:
            # Get unsent notifications based on notification preferences
            if self.notify_ai_processed_only:
                # Wait briefly for AI processing to complete, then get AI-processed tweets
                time.sleep(self.notification_delay)
                unsent_tweets = self.db.get_unsent_notifications(
                    username=username, 
                    ai_processed_only=True, 
                    limit=10
                )
            else:
                # Get all new tweets immediately
                unsent_tweets = self.db.get_unsent_notifications(
                    username=username, 
                    ai_processed_only=False, 
                    limit=10
                )
            
            if not unsent_tweets:
                self.logger.debug(f"No unsent notifications for {username}")
                return 0
            
            # Queue tweets for notification
            notifications_queued = 0
            for tweet in unsent_tweets:
                try:
                    # Send notification through Telegram
                    success = self.telegram_notifier.send_tweet_notification(
                        tweet_id=tweet['id'],
                        username=tweet['username'],
                        content=tweet['content'],
                        created_at=tweet['created_at'],
                        likes_count=tweet.get('likes_count', 0),
                        retweets_count=tweet.get('retweets_count', 0),
                        replies_count=tweet.get('replies_count', 0)
                    )
                    
                    if success:
                        notifications_queued += 1
                        self.logger.info(f"Queued notification for tweet {tweet['id']} from @{username}")
                    else:
                        self.logger.warning(f"Failed to queue notification for tweet {tweet['id']}")
                        
                except Exception as e:
                    self.logger.error(f"Error sending notification for tweet {tweet['id']}: {e}")
            
            return notifications_queued
            
        except Exception as e:
            self.logger.error(f"Error triggering notifications for {username}: {e}")
            return 0
    
    def get_telegram_status(self) -> Dict[str, Any]:
        """
        Get Telegram notification status and statistics
        
        Returns:
            Telegram status information
        """
        if not self.telegram_enabled:
            return {
                'enabled': False,
                'message': 'Telegram notifications are disabled'
            }
        
        try:
            telegram_status = self.telegram_notifier.get_queue_status()
            telegram_stats = telegram_status.get('stats', {})
            
            return {
                'enabled': True,
                'is_running': telegram_status.get('is_running', False),
                'bot_username': getattr(self.telegram_notifier, 'bot_username', 'Unknown'),
                'messages_sent': telegram_stats.get('messages_sent', 0),
                'messages_failed': telegram_stats.get('messages_failed', 0),
                'media_sent': telegram_stats.get('media_sent', 0),
                'rate_limit_hits': telegram_stats.get('rate_limit_hits', 0),
                'last_activity': telegram_stats.get('last_sent'),
                'queue_size': telegram_status.get('queue_size', 0),
                'success_rate': telegram_stats.get('success_rate', 0.0)
            }
            
        except Exception as e:
            self.logger.error(f"Error getting Telegram status: {e}")
            return {
                'enabled': True,
                'error': str(e)
            }
    
    def force_telegram_notifications(self, username: str = None, limit: int = 5) -> Dict[str, Any]:
        """
        Force immediate sending of pending notifications
        
        Args:
            username: Specific username to send notifications for (optional)
            limit: Maximum number of notifications to send
            
        Returns:
            Notification results
        """
        if not self.telegram_enabled:
            return {
                'success': False,
                'message': 'Telegram notifications are disabled'
            }
        
        try:
            self.logger.info(f"Forcing Telegram notifications (username: {username}, limit: {limit})")
            
            # Get unsent notifications
            unsent_tweets = self.db.get_unsent_notifications(
                username=username,
                ai_processed_only=False,  # Send all pending regardless of AI processing
                limit=limit
            )
            
            if not unsent_tweets:
                return {
                    'success': True,
                    'message': 'No pending notifications to send',
                    'sent_count': 0
                }
            
            # Send notifications
            sent_count = 0
            failed_count = 0
            results = []
            
            for tweet in unsent_tweets:
                try:
                    success = self.telegram_notifier.send_tweet_notification(
                        tweet_id=tweet['id'],
                        username=tweet['username'],
                        content=tweet['content'],
                        created_at=tweet['created_at'],
                        likes_count=tweet.get('likes_count', 0),
                        retweets_count=tweet.get('retweets_count', 0),
                        replies_count=tweet.get('replies_count', 0)
                    )
                    
                    if success:
                        sent_count += 1
                        results.append({'tweet_id': tweet['id'], 'status': 'sent'})
                    else:
                        failed_count += 1
                        results.append({'tweet_id': tweet['id'], 'status': 'failed'})
                        
                except Exception as e:
                    failed_count += 1
                    results.append({'tweet_id': tweet['id'], 'status': 'error', 'error': str(e)})
                    self.logger.error(f"Error sending forced notification for tweet {tweet['id']}: {e}")
            
            return {
                'success': True,
                'sent_count': sent_count,
                'failed_count': failed_count,
                'total_attempted': len(unsent_tweets),
                'results': results
            }
            
        except Exception as e:
            self.logger.error(f"Error forcing Telegram notifications: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def pause_notifications(self):
        """Pause Telegram notifications temporarily"""
        if self.telegram_enabled:
            self.notification_enabled = False
            self.logger.info("Telegram notifications paused")
    
    def resume_notifications(self):
        """Resume Telegram notifications"""
        if self.telegram_enabled:
            self.notification_enabled = True
            self.logger.info("Telegram notifications resumed")
    
    def is_notifications_paused(self) -> bool:
        """Check if notifications are paused"""
        return not self.notification_enabled
    
    def _initial_poll(self):
        """Run initial poll in background to avoid blocking startup"""
        import time
        time.sleep(2)  # Wait a moment for everything to initialize
        
        # Check if we should do historical scraping
        hybrid_mode = self.config.get('HYBRID_MODE', True)
        historical_hours = self.config.get('HISTORICAL_HOURS', 2)
        
        if hybrid_mode:
            self.logger.info(f"Running initial historical scrape for last {historical_hours} hours")
            self._historical_scrape(historical_hours)
        else:
            self.logger.info("Running initial poll")
            self._poll_all_users()

    def _historical_scrape(self, hours: int = 2):
        """
        Perform initial historical scrape of tweets from the last N hours
        
        Args:
            hours: Number of hours to look back
        """
        try:
            self.logger.info(f"Starting historical scrape for {len(self.monitored_users)} users")
            
            # Use the Twitter client's historical tweet method
            historical_tweets = self.twitter_client.get_historical_tweets(
                usernames=self.monitored_users, 
                hours=hours
            )
            
            if not historical_tweets:
                self.logger.info("No historical tweets found in the specified time period")
                return
            
            # Process and save historical tweets
            new_tweets_count = 0
            for tweet in historical_tweets:
                if self._is_new_tweet(tweet['id']):
                    if self._save_tweet_to_database(tweet):
                        new_tweets_count += 1
                        
                        # Process media for the tweet
                        media_results = self._process_tweet_media(tweet)
                        if media_results:
                            self._update_tweet_processing_status(tweet['id'], media_results)
                        
                        # Trigger notifications if enabled
                        if self.notification_enabled and self.telegram_enabled:
                            self._trigger_notifications_for_new_tweets(tweet['username'])
            
            # Trigger AI processing for new tweets
            if self.ai_enabled and new_tweets_count > 0:
                ai_processed = self._trigger_ai_processing_for_new_tweets()
                self.logger.info(f"Triggered AI processing for {ai_processed} new tweets")
            
            self.logger.info(f"Historical scrape completed: {new_tweets_count} new tweets found and processed")
            self.total_tweets_processed += new_tweets_count
            
        except Exception as e:
            self.logger.error(f"Error during historical scrape: {e}")
            self.last_error = str(e)