# Twitter Monitoring & Notification System - PostgreSQL Version
# Main Flask Application - Build 2024-12-28

from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import os
import sys
import logging
from datetime import datetime
import atexit
import threading
import time

# Import core components
from core.database_config import DatabaseConfig
from core.polling_scheduler import PollingScheduler
from core.error_handler import get_system_health, log_error
from core.webhook_handler import TwitterWebhookHandler
from core.rss_webhook_handler import RSSWebhookHandler
from core.twitter_client import TwitterClient
from core.ai_processor import AIProcessor
from core.background_worker import BackgroundWorker
from config import Config
from core.openai_client import OpenAIClient
from core.webhook_config import WebhookConfig

# Initialize Flask app
app = Flask(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load configuration
app.config.from_object('config.Config')

# Configure database using DatabaseConfig
db_config = DatabaseConfig.get_sqlalchemy_config()
app.config.update(db_config)

# Initialize SQLAlchemy
db = SQLAlchemy(app)

# Global variables for components
database = None
scheduler = None
webhook_handler = None
rss_webhook_handler = None
twitter_client = None
ai_processor = None
background_worker = None

# Define SQLAlchemy models
class Tweet(db.Model):
    __tablename__ = 'tweets'
    
    id = db.Column(db.String(50), primary_key=True)
    username = db.Column(db.String(50), nullable=False, index=True)
    display_name = db.Column(db.String(100))
    content = db.Column(db.Text, nullable=False)
    tweet_type = db.Column(db.String(20), default='tweet')
    created_at = db.Column(db.DateTime, nullable=False, index=True)
    detected_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime)
    ai_processed = db.Column(db.Boolean, default=False)
    media_processed = db.Column(db.Boolean, default=False)
    telegram_sent = db.Column(db.Boolean, default=False)
    likes_count = db.Column(db.Integer, default=0)
    retweets_count = db.Column(db.Integer, default=0)
    replies_count = db.Column(db.Integer, default=0)
    ai_analysis = db.Column(db.Text)

class Media(db.Model):
    __tablename__ = 'media'
    
    id = db.Column(db.Integer, primary_key=True)
    tweet_id = db.Column(db.String(50), db.ForeignKey('tweets.id'), nullable=False, index=True)
    media_type = db.Column(db.String(20), nullable=False)
    original_url = db.Column(db.Text, nullable=False)
    local_path = db.Column(db.Text)
    file_size = db.Column(db.Integer)
    width = db.Column(db.Integer)
    height = db.Column(db.Integer)
    duration = db.Column(db.Integer)
    download_status = db.Column(db.String(20), default='pending')
    downloaded_at = db.Column(db.DateTime)
    error_message = db.Column(db.Text)

class AIResult(db.Model):
    __tablename__ = 'ai_results'
    
    id = db.Column(db.Integer, primary_key=True)
    tweet_id = db.Column(db.String(50), db.ForeignKey('tweets.id'), nullable=False, index=True)
    prompt_used = db.Column(db.Text, nullable=False)
    result = db.Column(db.Text)
    model_used = db.Column(db.String(50))
    processing_time = db.Column(db.Float)
    tokens_used = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Setting(db.Model):
    __tablename__ = 'settings'
    
    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

def initialize_database():
    """Initialize database tables and default data"""
    try:
        logger.info(f"Using database: {DatabaseConfig.get_database_url()}")
        
        # Create tables using SQLAlchemy (let it handle the connection)
        with app.app_context():
            db.create_all()
            logger.info("Database tables created successfully")
            
            # Test a simple query to verify the connection works
            Setting.query.limit(1).all()
            logger.info("Database connection verified successfully")
            
            # Initialize default monitored users if none exist
            existing_users = Setting.query.filter_by(key='monitored_users').first()
            if not existing_users:
                default_users = os.environ.get('MONITORED_USERS', 'elonmusk,naval,paulg')
                new_setting = Setting(key='monitored_users', value=default_users)
                db.session.add(new_setting)
                db.session.commit()
                logger.info(f"Initialized default monitored users: {default_users}")
        
        return True
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return False

def initialize_components():
    """Initialize database, scheduler, and webhook components"""
    global database, scheduler, webhook_handler, rss_webhook_handler, twitter_client, ai_processor, background_worker
    
    try:
        # Initialize database first
        if not initialize_database():
            logger.error("Failed to initialize database")
            return False
        
        # Use a wrapper class for SQLAlchemy compatibility
        database = SQLAlchemyDatabaseWrapper(db)
        logger.info("Database initialized successfully")
        
        # Create configuration dictionary for scheduler
        config = {
            'TWITTER_API_KEY': app.config.get('TWITTER_API_KEY'),
            'OPENAI_API_KEY': app.config.get('OPENAI_API_KEY'),
            'TELEGRAM_BOT_TOKEN': app.config.get('TELEGRAM_BOT_TOKEN'),
            'TELEGRAM_CHAT_ID': app.config.get('TELEGRAM_CHAT_ID'),
            'MONITORED_USERS': ','.join(app.config.get('MONITORED_USERS', ['elonmusk', 'naval', 'paulg'])),
            'CHECK_INTERVAL': app.config.get('CHECK_INTERVAL', 60),
            'MEDIA_STORAGE_PATH': app.config.get('MEDIA_STORAGE_PATH', './media'),
            'DATABASE_PATH': app.config.get('DATABASE_PATH', './tweets.db'),
            'AI_BATCH_SIZE': app.config.get('AI_BATCH_SIZE', 5),
            'AI_PROCESSING_INTERVAL': app.config.get('AI_PROCESSING_INTERVAL', 120),
            'NOTIFICATION_ENABLED': app.config.get('NOTIFICATION_ENABLED', True),
            'NOTIFY_ALL_TWEETS': app.config.get('NOTIFY_ALL_TWEETS', False),
            'NOTIFY_AI_PROCESSED_ONLY': app.config.get('NOTIFY_AI_PROCESSED_ONLY', True),
            'NOTIFICATION_DELAY': app.config.get('NOTIFICATION_DELAY', 10),
            'WEBHOOK_ONLY_MODE': app.config.get('WEBHOOK_ONLY_MODE', False),
            'HYBRID_MODE': app.config.get('HYBRID_MODE', True),
            'HISTORICAL_HOURS': app.config.get('HISTORICAL_HOURS', 2)
        }
        
        # Initialize AI processor
        openai_client = OpenAIClient(
            config.get('OPENAI_API_KEY'), 
            model=config.get('OPENAI_MODEL', 'o1-mini'),
            max_tokens=config.get('OPENAI_MAX_TOKENS', 1000),
            database=database
        )
        ai_processor = AIProcessor(database, openai_client)
        logger.info("AI processor initialized successfully")
        
        # Initialize background worker for missing translations and media
        background_worker = BackgroundWorker(
            database=database,
            openai_client=openai_client,
            media_storage_path=config.get('MEDIA_STORAGE_PATH', './media')
        )
        background_worker.start()
        logger.info("Background worker started successfully")
        
        # Initialize Twitter client
        twitter_client = TwitterClient(config.get('TWITTER_API_KEY'))
        logger.info("Twitter client initialized successfully")
        
        # Initialize webhook handler
        webhook_handler = TwitterWebhookHandler(database, ai_processor, config)
        logger.info("Webhook handler initialized successfully")
        
        # Initialize RSS webhook handler
        rss_webhook_handler = RSSWebhookHandler(database, twitter_client, ai_processor, config)
        logger.info("RSS webhook handler initialized successfully")
        
        # Initialize scheduler based on mode - read from database first, fallback to config
        try:
            monitoring_mode = database.get_setting('monitoring_mode', 'hybrid')
        except Exception as e:
            logger.warning(f"Could not read monitoring_mode from database: {e}, using config fallback")
            # Fallback to environment variables if database not available
            webhook_only_mode = config.get('WEBHOOK_ONLY_MODE', False)
            monitoring_mode = 'webhook' if webhook_only_mode else 'hybrid'
        
        logger.info(f"Monitoring mode: {monitoring_mode}")
        
        if monitoring_mode != 'webhook':
            scheduler = PollingScheduler(config, database)
            logger.info("Polling scheduler initialized successfully")
            
            # Start scheduler
            scheduler.start()
            
            if monitoring_mode == 'hybrid':
                logger.info("Hybrid mode enabled - initial historical scrape + webhook monitoring")
            else:
                logger.info("Polling mode enabled - continuous polling")
        else:
            logger.info("Webhook-only mode enabled - polling scheduler disabled")
            scheduler = None
        
        return True
        
    except Exception as e:
        logger.error(f"Error initializing components: {e}")
        return False

# SQLAlchemy Database Wrapper to maintain compatibility with existing code
class SQLAlchemyDatabaseWrapper:
    """Wrapper class to maintain compatibility with the old Database interface"""
    
    def __init__(self, db_instance):
        self.db = db_instance
        # Store reference to Flask app for context
        self.app = app
    
    def _with_app_context(self, func):
        """Helper method to execute database operations with Flask application context"""
        from flask import has_app_context
        
        if has_app_context():
            # If we're already in app context, just run the function
            return func()
        else:
            # Create app context
            with self.app.app_context():
                return func()
        
    def get_monitored_users(self):
        """Get list of monitored users"""
        def _get_users():
            setting = Setting.query.filter_by(key='monitored_users').first()
            if setting and setting.value:
                return [user.strip() for user in setting.value.split(',') if user.strip()]
            return ['elonmusk', 'naval', 'paulg']  # Default users
        
        try:
            return self._with_app_context(_get_users)
        except Exception as e:
            logger.error(f"Error getting monitored users: {e}")
            return []
    
    def set_monitored_users(self, users):
        """Set monitored users"""
        def _set_users():
            users_str = ','.join(users)
            setting = Setting.query.filter_by(key='monitored_users').first()
            if setting:
                setting.value = users_str
                setting.updated_at = datetime.utcnow()
            else:
                setting = Setting(key='monitored_users', value=users_str)
                self.db.session.add(setting)
            
            self.db.session.commit()
            return True
        
        try:
            return self._with_app_context(_set_users)
        except Exception as e:
            logger.error(f"Error setting monitored users: {e}")
            try:
                self.db.session.rollback()
            except:
                pass
            return False
    
    def add_monitored_user(self, username):
        """Add a user to monitoring list"""
        try:
            current_users = self.get_monitored_users()
            if username not in current_users:
                current_users.append(username)
                return self.set_monitored_users(current_users)
            return True
        except Exception as e:
            logger.error(f"Error adding monitored user: {e}")
            return False
    
    def remove_monitored_user(self, username):
        """Remove a user from monitoring list"""
        try:
            current_users = self.get_monitored_users()
            if username in current_users:
                current_users.remove(username)
                return self.set_monitored_users(current_users)
            return True
        except Exception as e:
            logger.error(f"Error removing monitored user: {e}")
            return False
    
    def get_tweets(self, limit=50, offset=0):
        """Get tweets from database"""
        def _get_tweets():
            tweets = Tweet.query.order_by(Tweet.created_at.desc()).limit(limit).offset(offset).all()
            return [self._tweet_to_dict(tweet) for tweet in tweets]
        
        try:
            return self._with_app_context(_get_tweets)
        except Exception as e:
            logger.error(f"Error getting tweets: {e}")
            return []
    
    def insert_tweet(self, tweet_data):
        """Insert a new tweet"""
        def _insert():
            tweet = Tweet(
                id=tweet_data.get('id'),
                username=tweet_data.get('username'),
                display_name=tweet_data.get('display_name'),
                content=tweet_data.get('content'),
                tweet_type=tweet_data.get('tweet_type', 'tweet'),
                created_at=tweet_data.get('created_at'),
                likes_count=tweet_data.get('likes_count', 0),
                retweets_count=tweet_data.get('retweets_count', 0),
                replies_count=tweet_data.get('replies_count', 0)
            )
            
            self.db.session.merge(tweet)  # Use merge for upsert behavior
            self.db.session.commit()
            return True
        
        try:
            return self._with_app_context(_insert)
        except Exception as e:
            logger.error(f"Error inserting tweet: {e}")
            try:
                self.db.session.rollback()
            except:
                pass
            return False
    
    def _tweet_to_dict(self, tweet):
        """Convert Tweet model to dictionary"""
        return {
            'id': tweet.id,
            'username': tweet.username,
            'display_name': tweet.display_name,
            'content': tweet.content,
            'tweet_type': tweet.tweet_type,
            'created_at': tweet.created_at.isoformat() if tweet.created_at else None,
            'detected_at': tweet.detected_at.isoformat() if tweet.detected_at else None,
            'processed_at': tweet.processed_at.isoformat() if tweet.processed_at else None,
            'ai_processed': tweet.ai_processed,
            'media_processed': tweet.media_processed,
            'telegram_sent': tweet.telegram_sent,
            'likes_count': tweet.likes_count,
            'retweets_count': tweet.retweets_count,
            'replies_count': tweet.replies_count,
            'ai_analysis': tweet.ai_analysis
        }
    
    def get_stats(self):
        """Get database statistics"""
        def _get_stats():
            total_tweets = Tweet.query.count()
            ai_processed = Tweet.query.filter_by(ai_processed=True).count()
            telegram_sent = Tweet.query.filter_by(telegram_sent=True).count()
            
            return {
                'total_tweets': total_tweets,
                'ai_processed': ai_processed,
                'telegram_sent': telegram_sent,
                'unprocessed': total_tweets - ai_processed
            }
        
        try:
            return self._with_app_context(_get_stats)
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {'total_tweets': 0, 'ai_processed': 0, 'telegram_sent': 0, 'unprocessed': 0}
    
    def get_tweet_by_id(self, tweet_id):
        """Get a specific tweet by ID"""
        try:
            tweet = Tweet.query.filter_by(id=tweet_id).first()
            return self._tweet_to_dict(tweet) if tweet else None
        except Exception as e:
            logger.error(f"Error getting tweet by ID: {e}")
            return None
    
    def store_tweet(self, tweet_data):
        """Store a tweet and return its ID"""
        try:
            if self.insert_tweet(tweet_data):
                return tweet_data.get('id')
            return None
        except Exception as e:
            logger.error(f"Error storing tweet: {e}")
            return None
    
    def tweet_exists(self, tweet_id):
        """Check if a tweet exists"""
        def _check_exists():
            return Tweet.query.filter_by(id=tweet_id).first() is not None
        
        try:
            return self._with_app_context(_check_exists)
        except Exception as e:
            logger.error(f"Error checking tweet existence: {e}")
            return False
    
    def get_setting(self, key, default_value=None):
        """Get a setting value"""
        def _get_setting():
            setting = Setting.query.filter_by(key=key).first()
            return setting.value if setting else default_value
        
        try:
            return self._with_app_context(_get_setting)
        except Exception as e:
            logger.error(f"Error getting setting: {e}")
            return default_value
    
    def set_setting(self, key, value):
        """Set a setting value"""
        def _set_setting():
            setting = Setting.query.filter_by(key=key).first()
            if setting:
                setting.value = value
                setting.updated_at = datetime.utcnow()
            else:
                setting = Setting(key=key, value=value)
                self.db.session.add(setting)
            
            self.db.session.commit()
            return True
        
        try:
            return self._with_app_context(_set_setting)
        except Exception as e:
            logger.error(f"Error setting value: {e}")
            try:
                self.db.session.rollback()
            except:
                pass
            return False
    
    def get_unprocessed_tweets(self, limit=50):
        """Get tweets that haven't been processed by AI"""
        def _get_unprocessed():
            tweets = Tweet.query.filter_by(ai_processed=False).limit(limit).all()
            return [self._tweet_to_dict(tweet) for tweet in tweets]
        
        try:
            return self._with_app_context(_get_unprocessed)
        except Exception as e:
            logger.error(f"Error getting unprocessed tweets: {e}")
            return []
    
    def store_ai_result(self, result_data):
        """Store AI processing result"""
        try:
            ai_result = AIResult(
                tweet_id=result_data.get('tweet_id'),
                prompt_used=result_data.get('prompt_used', ''),
                result=result_data.get('result'),
                model_used=result_data.get('model_used'),
                processing_time=result_data.get('processing_time'),
                tokens_used=result_data.get('tokens_used')
            )
            
            self.db.session.add(ai_result)
            self.db.session.commit()
            return True
        except Exception as e:
            logger.error(f"Error storing AI result: {e}")
            self.db.session.rollback()
            return False
    
    def update_tweet_ai_status(self, tweet_id, processed):
        """Update tweet AI processing status"""
        try:
            tweet = Tweet.query.filter_by(id=tweet_id).first()
            if tweet:
                tweet.ai_processed = processed
                tweet.processed_at = datetime.utcnow() if processed else None
                self.db.session.commit()
                return True
            return False
        except Exception as e:
            logger.error(f"Error updating tweet AI status: {e}")
            self.db.session.rollback()
            return False
    
    def get_unprocessed_count(self):
        """Get count of unprocessed tweets"""
        try:
            return Tweet.query.filter_by(ai_processed=False).count()
        except Exception as e:
            logger.error(f"Error getting unprocessed count: {e}")
            return 0
    
    def get_total_tweets_count(self):
        """Get total tweet count"""
        try:
            return Tweet.query.count()
        except Exception as e:
            logger.error(f"Error getting total tweets count: {e}")
            return 0
    
    def get_failed_ai_tweets(self, limit=50):
        """Get tweets that failed AI processing"""
        try:
            # For now, return tweets that are not AI processed
            # In a full implementation, we'd need an error tracking mechanism
            tweets = Tweet.query.filter_by(ai_processed=False).limit(limit).all()
            return [self._tweet_to_dict(tweet) for tweet in tweets]
        except Exception as e:
            logger.error(f"Error getting failed AI tweets: {e}")
            return []
    
    def clear_ai_error(self, tweet_id):
        """Clear AI processing error for a tweet"""
        try:
            tweet = Tweet.query.filter_by(id=tweet_id).first()
            if tweet:
                tweet.ai_processed = False  # Reset to allow retry
                self.db.session.commit()
                return True
            return False
        except Exception as e:
            logger.error(f"Error clearing AI error: {e}")
            self.db.session.rollback()
            return False
    
    def get_recent_ai_results(self, limit=10):
        """Get recent AI processing results"""
        try:
            results = AIResult.query.order_by(AIResult.created_at.desc()).limit(limit).all()
            return [{
                'id': result.id,
                'tweet_id': result.tweet_id,
                'prompt_used': result.prompt_used,
                'result': result.result,
                'model_used': result.model_used,
                'processing_time': result.processing_time,
                'tokens_used': result.tokens_used,
                'created_at': result.created_at.isoformat() if result.created_at else None
            } for result in results]
        except Exception as e:
            logger.error(f"Error getting recent AI results: {e}")
            return []
    
    def get_ai_parameters(self):
        """Get AI parameters from settings"""
        try:
            params_str = self.get_setting('ai_parameters', '{}')
            import json
            return json.loads(params_str)
        except Exception:
            return {}
    
    def set_ai_parameters(self, parameters):
        """Set AI parameters as JSON"""
        try:
            import json
            self.set_setting('ai_parameters', json.dumps(parameters))
            return True
        except Exception as e:
            logger.error(f"Error setting AI parameters: {e}")
            return False
    
    @property
    def db_path(self):
        """Compatibility property for old code that expects db_path"""
        return "postgresql_database"  # Return a placeholder since we're using PostgreSQL
    
    def get_tweets_without_ai_analysis(self, limit=50):
        """Get tweets that haven't been processed by AI"""
        try:
            tweets = Tweet.query.filter_by(ai_processed=False).limit(limit).all()
            return [self._tweet_to_dict(tweet) for tweet in tweets]
        except Exception as e:
            logger.error(f"Error getting unprocessed tweets: {e}")
            return []
    
    def get_tweets_with_missing_media(self, limit=50):
        """Get tweets that have missing media"""
        try:
            # This would require a more complex query with joins
            # For now, return an empty list - this method is rarely used
            return []
        except Exception as e:
            logger.error(f"Error getting tweets with missing media: {e}")
            return []
    
    def mark_telegram_sent(self, tweet_id):
        """Mark a tweet as sent via Telegram"""
        try:
            tweet = Tweet.query.filter_by(id=tweet_id).first()
            if tweet:
                tweet.telegram_sent = True
                tweet.processed_at = datetime.utcnow()
                self.db.session.commit()
                return True
            return False
        except Exception as e:
            logger.error(f"Error marking tweet as sent: {e}")
            self.db.session.rollback()
            return False
    
    def get_tweet_media(self, tweet_id, completed_only=False):
        """Get media files associated with a tweet"""
        def _get_media():
            query = Media.query.filter_by(tweet_id=tweet_id)
            
            if completed_only:
                query = query.filter_by(download_status='completed')
            
            media_records = query.order_by(Media.id.asc()).all()
            
            return [{
                'id': media.id,
                'tweet_id': media.tweet_id,
                'media_type': media.media_type,
                'original_url': media.original_url,
                'local_path': media.local_path,
                'file_size': media.file_size,
                'width': media.width,
                'height': media.height,
                'duration': media.duration,
                'download_status': media.download_status,
                'downloaded_at': media.downloaded_at.isoformat() if media.downloaded_at else None,
                'error_message': media.error_message
            } for media in media_records]
        
        try:
            return self._with_app_context(_get_media)
        except Exception as e:
            logger.error(f"Error getting tweet media for {tweet_id}: {e}")
            return []
    
    def store_media(self, media_data):
        """Store media file information in database"""
        try:
            media = Media(
                tweet_id=media_data.get('tweet_id'),
                media_type=media_data.get('media_type'),
                original_url=media_data.get('original_url'),
                local_path=media_data.get('local_path'),
                file_size=media_data.get('file_size'),
                width=media_data.get('width'),
                height=media_data.get('height'),
                duration=media_data.get('duration'),
                download_status=media_data.get('download_status', 'completed'),
                downloaded_at=media_data.get('downloaded_at', datetime.utcnow())
            )
            
            self.db.session.add(media)
            self.db.session.commit()
            logger.info(f"Media stored for tweet {media_data.get('tweet_id')}")
            return True
            
        except Exception as e:
            logger.error(f"Error storing media: {e}")
            self.db.session.rollback()
            return False
    
    def update_media_status(self, tweet_id, original_url, status, error_message=None):
        """Update media download status"""
        try:
            media = Media.query.filter_by(tweet_id=tweet_id, original_url=original_url).first()
            if media:
                media.download_status = status
                media.error_message = error_message
                if status == 'completed':
                    media.downloaded_at = datetime.utcnow()
                
                self.db.session.commit()
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error updating media status: {e}")
            self.db.session.rollback()
            return False
    
    def get_unsent_notifications(self, limit=50, username=None, ai_processed_only=True):
        """Get tweets that need Telegram notifications"""
        try:
            query = Tweet.query.filter_by(telegram_sent=False)
            
            if ai_processed_only:
                query = query.filter_by(ai_processed=True)
            
            if username:
                query = query.filter_by(username=username)
            
            tweets = query.order_by(Tweet.created_at.asc()).limit(limit).all()
            return [self._tweet_to_dict(tweet) for tweet in tweets]
            
        except Exception as e:
            logger.error(f"Error getting unsent notifications: {e}")
            return []
    
    def update_tweet_processing_status(self, tweet_id, media_downloaded=False, ai_processed=False):
        """Update tweet processing status after media download"""
        try:
            tweet = Tweet.query.filter_by(id=tweet_id).first()
            if tweet:
                if media_downloaded:
                    tweet.media_processed = True
                if ai_processed:
                    tweet.ai_processed = True
                
                self.db.session.commit()
                logger.info(f"Updated processing status for tweet {tweet_id}: media_downloaded={media_downloaded}, ai_processed={ai_processed}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error updating processing status for tweet {tweet_id}: {e}")
            self.db.session.rollback()
            return False
    
    def get_telegram_stats(self):
        """Get Telegram notification statistics"""
        try:
            sent_count = Tweet.query.filter_by(telegram_sent=True).count()
            pending_count = Tweet.query.filter_by(ai_processed=True, telegram_sent=False).count()
            total_unsent = Tweet.query.filter_by(telegram_sent=False).count()
            
            return {
                'notifications_sent': sent_count,
                'notifications_pending': pending_count,
                'total_unsent': total_unsent
            }
            
        except Exception as e:
            logger.error(f"Error getting Telegram stats: {e}")
            return {
                'notifications_sent': 0,
                'notifications_pending': 0,
                'total_unsent': 0
            }
    
    def update_telegram_status(self, tweet_id, sent, sent_at=None, error_message=None):
        """Update Telegram status for a tweet"""
        try:
            tweet = Tweet.query.filter_by(id=tweet_id).first()
            if tweet:
                tweet.telegram_sent = sent
                if sent and not tweet.processed_at:
                    tweet.processed_at = sent_at or datetime.utcnow()
                
                self.db.session.commit()
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error updating Telegram status: {e}")
            self.db.session.rollback()
            return False

def cleanup_components():
    """Cleanup components on app shutdown"""
    global scheduler, background_worker
    
    try:
        if scheduler:
            scheduler.stop()
            logger.info("Scheduler stopped successfully")
    except Exception as e:
        logger.error(f"Error stopping scheduler: {e}")
    
    try:
        if background_worker:
            background_worker.stop()
            logger.info("Background worker stopped successfully")
    except Exception as e:
        logger.error(f"Error stopping background worker: {e}")

# Register cleanup function
atexit.register(cleanup_components)

# Initialize components at module level for production/Gunicorn compatibility
logger.info("Initializing components at module level...")

# Ensure required directories exist
os.makedirs('logs', exist_ok=True)
os.makedirs('data', exist_ok=True)

# Display startup information
try:
    from startup_info import display_startup_info
    display_startup_info()
except ImportError:
    logger.warning("Could not import startup_info module")

# Initialize all components
initialization_success = initialize_components()
if not initialization_success:
    logger.error("Failed to initialize components - some features may not work")

@app.route('/')
def dashboard():
    """Main dashboard showing monitored tweets"""
    return render_template('dashboard.html', 
                         page_title="Twitter Monitor Dashboard",
                         current_time=datetime.now())

@app.route('/settings')
def settings():
    """Settings page for system configuration"""
    return render_template('settings.html',
                         page_title="Settings - Twitter Monitor",
                         current_time=datetime.now())

@app.route('/analytics')
def analytics():
    """Analytics page showing system metrics and insights"""
    return render_template('analytics.html',
                         page_title="Analytics - Twitter Monitor",
                         current_time=datetime.now())

@app.route('/health')
def health_check():
    """Health check endpoint for monitoring"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    })

@app.route('/api/webhook/info')
def get_webhook_configuration():
    """Get webhook configuration information for RSS.app setup"""
    try:
        webhook_info = get_webhook_info()
        return jsonify({
            'status': 'success',
            'webhook_configuration': webhook_info,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting webhook info: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

def get_webhook_info():
    """Helper function to get webhook configuration"""
    try:
        base_url = WebhookConfig.get_public_webhook_url()
        endpoints = WebhookConfig.get_webhook_endpoints()
        instructions = WebhookConfig.get_rss_app_instructions()
        
        return {
            'base_url': base_url,
            'webhook_url': endpoints.get('rss_webhook', ''),
            'environment': instructions.get('environment', 'unknown'),
            'endpoints': endpoints,
            'rss_app_instructions': instructions,
            'is_production': WebhookConfig._detect_koyeb_url() is not None
        }
    except Exception as e:
        logger.error(f"Error in get_webhook_info: {e}")
        return {
            'webhook_url': 'Error: Could not determine webhook URL',
            'error': str(e)
        }

@app.route('/webhook/twitter', methods=['GET'])
def twitter_webhook_crc():
    """Handle Twitter CRC challenge for webhook verification"""
    if not webhook_handler:
        return jsonify({'error': 'Webhook handler not initialized'}), 500
    
    try:
        crc_token = request.args.get('crc_token')
        if not crc_token:
            return jsonify({'error': 'Missing crc_token parameter'}), 400
        
        response = webhook_handler.handle_crc_challenge(crc_token)
        logger.info("CRC challenge handled successfully")
        return jsonify(response)
    
    except Exception as e:
        logger.error(f"Error handling CRC challenge: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/webhook/twitter', methods=['POST'])
def twitter_webhook_event():
    """Handle incoming Twitter webhook events"""
    if not webhook_handler:
        return jsonify({'error': 'Webhook handler not initialized'}), 500
    
    try:
        # Get signature for verification
        signature = request.headers.get('X-Twitter-Webhooks-Signature')
        
        # Get event data
        event_data = request.get_json()
        if not event_data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        # Process the webhook event
        result = webhook_handler.process_webhook_event(event_data, signature)
        
        logger.info(f"Webhook event processed: {result}")
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Error processing webhook event: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/webhook/test', methods=['POST'])
def test_webhook():
    """Test endpoint for webhook functionality (for development)"""
    if not webhook_handler:
        return jsonify({'error': 'Webhook handler not initialized'}), 500
    
    try:
        # Sample tweet data for testing
        test_tweet = {
            "id_str": "1234567890123456789",
            "text": "This is a test tweet for webhook functionality! #test #webhook",
            "created_at": "Wed Oct 05 00:37:15 +0000 2023",
            "user": {
                "screen_name": "elonmusk",
                "name": "Elon Musk",
                "profile_image_url_https": "https://pbs.twimg.com/profile_images/1683325380441128960/yRsRRjGO_normal.jpg"
            },
            "favorite_count": 100,
            "retweet_count": 50,
            "reply_count": 25,
            "entities": {
                "hashtags": [
                    {"text": "test"},
                    {"text": "webhook"}
                ],
                "urls": [],
                "user_mentions": []
            }
        }
        
        # Process the test tweet
        result = webhook_handler._handle_single_tweet(test_tweet)
        
        logger.info(f"Test webhook processed: {result}")
        return jsonify({
            'status': 'success',
            'message': 'Test webhook processed successfully',
            'result': result
        })
    
    except Exception as e:
        logger.error(f"Error processing test webhook: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/webhook/rss', methods=['POST'])
def rss_webhook_event():
    """Handle incoming RSS.app webhook events"""
    if not rss_webhook_handler:
        return jsonify({'error': 'RSS webhook handler not initialized'}), 500
    
    try:
        # Get event data
        event_data = request.get_json()
        if not event_data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        # Process the RSS webhook event (RSS.app doesn't provide signatures)
        result = rss_webhook_handler.process_rss_webhook(event_data)
        
        logger.info(f"RSS webhook event processed: {result}")
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Error processing RSS webhook event: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/webhook/rss/test', methods=['POST', 'GET'])
def test_rss_webhook():
    """Test endpoint for RSS webhook functionality"""
    if not rss_webhook_handler:
        return jsonify({'error': 'RSS webhook handler not initialized'}), 500
    
    try:
        # Use the handler's test method
        result = rss_webhook_handler.handle_test_webhook()
        
        if result['status'] == 'success':
            logger.info(f"Test RSS webhook processed: {result}")
            return jsonify(result)
        else:
            logger.error(f"Test RSS webhook failed: {result}")
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error in test RSS webhook: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/rss/stats')
def get_rss_webhook_stats():
    """Get RSS webhook statistics"""
    if not rss_webhook_handler:
        return jsonify({'error': 'RSS webhook handler not initialized'}), 500
    
    try:
        stats = rss_webhook_handler.get_webhook_stats()
        return jsonify({
            'status': 'success',
            'stats': stats,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting RSS webhook stats: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/version')
def get_version_info():
    """Get current version and development information"""
    try:
        import git
        from datetime import datetime
        
        repo = git.Repo('.')
        current_branch = repo.active_branch.name
        current_commit = repo.head.commit.hexsha[:8]
        commit_date = datetime.fromtimestamp(repo.head.commit.committed_date)
        
        # Check if there are uncommitted changes
        is_dirty = repo.is_dirty()
        untracked_files = len(repo.untracked_files)
        
        return jsonify({
            'version': '1.0.0-dev',
            'branch': current_branch,
            'commit': current_commit,
            'commit_date': commit_date.isoformat(),
            'is_dirty': is_dirty,
            'untracked_files': untracked_files,
            'development_mode': app.config.get('DEBUG', False),
            'webhook_url': get_webhook_info()['webhook_url'],
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'version': '1.0.0-dev',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        })

@app.route('/api/errors')
def get_error_statistics():
    """API endpoint to get comprehensive error statistics"""
    try:
        error_stats = get_system_health()
        return jsonify({
            'status': 'success',
            'error_statistics': error_stats,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        error_id = log_error(e, "flask_app", "get_error_statistics")
        return jsonify({
            'status': 'error',
            'error': str(e),
            'error_id': error_id
        }), 500

@app.route('/api/tweets')
def get_tweets():
    """API endpoint to fetch tweets with filtering and search"""
    if not database:
        return jsonify({'error': 'Database not initialized'}), 500
    
    try:
        # Get parameters
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        username = request.args.get('username')
        search_query = request.args.get('q')  # Search query
        filter_type = request.args.get('filter', 'all')  # all, images, videos, ai
        since = request.args.get('since')  # timestamp for real-time updates
        
        # Get tweets from database with filters
        tweets = get_filtered_tweets(
            limit=limit, 
            offset=offset,
            username=username,
            search_query=search_query,
            filter_type=filter_type,
            since=since
        )
        
        # Get additional data for each tweet
        enriched_tweets = []
        for tweet in tweets:
            # Get media for this tweet
            media = database.get_tweet_media(tweet['id'], completed_only=True)
            
            # Format media URLs for web display
            formatted_media = []
            for media_item in media:
                formatted_item = dict(media_item)
                if media_item.get('local_path'):
                    # Convert local path to web-accessible URL
                    import os
                    filename = os.path.basename(media_item['local_path'])
                    formatted_item['url'] = f"/media/{filename}"
                formatted_media.append(formatted_item)
            
            # Get AI results for this tweet
            ai_results = database.get_recent_ai_results(limit=100)  # Get more to find matches
            ai_result = None
            for result in ai_results:
                if result['tweet_id'] == tweet['id']:
                    ai_result = result['result'] if result else None
                    break
            
            # Add enriched data
            tweet_dict = dict(tweet)
            tweet_dict['media'] = formatted_media
            tweet_dict['ai_analysis'] = ai_result
            tweet_dict['has_media'] = len(formatted_media) > 0
            tweet_dict['has_ai_analysis'] = ai_result is not None
            
            enriched_tweets.append(tweet_dict)
        
        return jsonify({
            'tweets': enriched_tweets,
            'count': len(enriched_tweets),
            'status': 'success',
            'filters_applied': {
                'username': username,
                'search_query': search_query,
                'filter_type': filter_type,
                'since': since
            }
        })
    except Exception as e:
        logger.error(f"Error fetching tweets: {e}")
        return jsonify({'error': str(e)}), 500

def get_filtered_tweets(limit=50, offset=0, username=None, search_query=None, filter_type='all', since=None):
    """Get tweets with applied filters - SQLAlchemy version"""
    try:
        # Build SQLAlchemy query
        query = Tweet.query
        
        # ALWAYS filter by monitored users (unless specific username is requested)
        if not username:
            monitored_users = database.get_monitored_users()
            if monitored_users:
                query = query.filter(Tweet.username.in_(monitored_users))
            else:
                # No monitored users - return empty result
                return []
        else:
            # Specific username filter
            query = query.filter(Tweet.username == username)
        
        # Search query filter
        if search_query:
            search_pattern = f"%{search_query}%"
            query = query.filter(
                db.or_(
                    Tweet.content.like(search_pattern),
                    Tweet.display_name.like(search_pattern)
                )
            )
        
        # Filter type
        if filter_type == 'ai':
            query = query.filter(Tweet.ai_processed == True)
        elif filter_type in ['images', 'videos']:
            # For media filters, we'll use a simpler approach for now
            if filter_type == 'images':
                # Find tweets with image media
                media_tweet_ids = db.session.query(Media.tweet_id).filter(
                    Media.media_type.in_(['photo', 'image'])
                ).distinct()
                query = query.filter(Tweet.id.in_(media_tweet_ids))
            elif filter_type == 'videos':
                # Find tweets with video media
                media_tweet_ids = db.session.query(Media.tweet_id).filter(
                    Media.media_type.in_(['video', 'gif', 'animated_gif'])
                ).distinct()
                query = query.filter(Tweet.id.in_(media_tweet_ids))
        
        # Since timestamp for real-time updates
        if since:
            try:
                since_dt = datetime.fromisoformat(since.replace('Z', '+00:00'))
                query = query.filter(Tweet.detected_at > since_dt)
            except Exception:
                logger.warning(f"Invalid since timestamp: {since}")
        
        # Order by created_at desc (newest first)
        query = query.order_by(Tweet.created_at.desc(), Tweet.detected_at.desc())
        
        # Apply pagination
        query = query.offset(offset).limit(limit)
        
        # Execute query and convert to dictionaries
        tweets = []
        for tweet in query.all():
            tweets.append({
                'id': tweet.id,
                'username': tweet.username,
                'display_name': tweet.display_name,
                'content': tweet.content,
                'tweet_type': tweet.tweet_type,
                'created_at': tweet.created_at.isoformat() if tweet.created_at else None,
                'detected_at': tweet.detected_at.isoformat() if tweet.detected_at else None,
                'processed_at': tweet.processed_at.isoformat() if tweet.processed_at else None,
                'ai_processed': tweet.ai_processed,
                'media_processed': tweet.media_processed,
                'telegram_sent': tweet.telegram_sent,
                'likes_count': tweet.likes_count,
                'retweets_count': tweet.retweets_count,
                'replies_count': tweet.replies_count,
                'ai_analysis': tweet.ai_analysis
            })
        
        logger.debug(f"Filtered tweets query returned {len(tweets)} results")
        if not username:
            logger.debug(f"Filtering by monitored users: {database.get_monitored_users()}")
        
        return tweets
        
    except Exception as e:
        logger.error(f"Error in get_filtered_tweets: {e}")
        return []

@app.route('/api/status')
def get_system_status():
    """Get comprehensive system status"""
    if not scheduler:
        return jsonify({'error': 'Scheduler not initialized'}), 500
    
    try:
        # Get scheduler status
        scheduler_status = scheduler.get_status()
        
        # Get AI status
        ai_status = scheduler.get_ai_status()
        
        # Get Telegram status
        telegram_status = scheduler.get_telegram_status()
        
        # Get recent activity
        recent_activity = scheduler.get_recent_activity(limit=5)
        
        return jsonify({
            'scheduler': scheduler_status,
            'ai_processing': ai_status,
            'notifications': telegram_status,
            'recent_activity': recent_activity,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/statistics')
def get_statistics():
    """Get system statistics"""
    if not database:
        return jsonify({'error': 'Database not initialized'}), 500
    
    try:
        # Get database statistics
        db_stats = database.get_stats()
        
        # Get scheduler statistics if available
        scheduler_stats = {}
        if scheduler:
            try:
                scheduler_stats = scheduler.get_statistics()
            except Exception as e:
                logger.warning(f"Could not get scheduler stats: {e}")
        
        # Combine stats
        combined_stats = {
            **db_stats,
            'scheduler': scheduler_stats,
            'timestamp': datetime.now().isoformat()
        }
        
        return jsonify(combined_stats)
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/notifications/status')
def get_notification_status():
    """Get notification system status"""
    if not scheduler:
        return jsonify({'error': 'Scheduler not initialized'}), 500
    
    try:
        telegram_status = scheduler.get_telegram_status()
        
        # Add notification configuration
        notification_config = {
            'enabled': scheduler.notification_enabled,
            'telegram_enabled': scheduler.telegram_enabled,
            'notify_all_tweets': scheduler.notify_all_tweets,
            'notify_ai_processed_only': scheduler.notify_ai_processed_only,
            'notification_delay': scheduler.notification_delay,
            'paused': scheduler.is_notifications_paused()
        }
        
        return jsonify({
            'config': notification_config,
            'stats': telegram_status,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting notification status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/notifications/send', methods=['POST'])
def force_send_notifications():
    """Force sending of pending notifications"""
    if not scheduler:
        return jsonify({'error': 'Scheduler not initialized'}), 500
    
    try:
        data = request.get_json() or {}
        username = data.get('username')
        limit = data.get('limit', 5)
        
        result = scheduler.force_telegram_notifications(username=username, limit=limit)
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error forcing notifications: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/notifications/pause', methods=['POST'])
def pause_notifications():
    """Pause notifications"""
    if not scheduler:
        return jsonify({'error': 'Scheduler not initialized'}), 500
    
    try:
        scheduler.pause_notifications()
        return jsonify({
            'success': True,
            'message': 'Notifications paused'
        })
    except Exception as e:
        logger.error(f"Error pausing notifications: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/notifications/resume', methods=['POST'])
def resume_notifications():
    """Resume notifications"""
    if not scheduler:
        return jsonify({'error': 'Scheduler not initialized'}), 500
    
    try:
        scheduler.resume_notifications()
        return jsonify({
            'success': True,
            'message': 'Notifications resumed'
        })
    except Exception as e:
        logger.error(f"Error resuming notifications: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/poll/force', methods=['POST'])
def force_poll():
    """Force immediate polling"""
    if not scheduler:
        return jsonify({'error': 'Scheduler not initialized'}), 500
    
    try:
        result = scheduler.force_poll_now()
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error forcing poll: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai/force', methods=['POST'])
def force_ai_processing():
    """Force AI processing of unprocessed tweets"""
    if not scheduler:
        return jsonify({'error': 'Scheduler not initialized'}), 500
    
    # Check if AI is enabled
    if not hasattr(scheduler, 'ai_enabled') or not scheduler.ai_enabled:
        from config import Config
        if not getattr(Config, 'OPENAI_API_KEY', None):
            return jsonify({
                'error': 'AI processing is not configured. Please set OPENAI_API_KEY in environment variables.',
                'success': False
            }), 400
        else:
            return jsonify({
                'error': 'AI processing is disabled',
                'success': False
            }), 400
    
    try:
        data = request.get_json() or {}
        batch_size = data.get('batch_size', 10)
        
        result = scheduler.force_ai_processing(batch_size=batch_size)
        
        # Add more detailed error information if available
        if not result.get('success') and 'error' not in result:
            result['error'] = result.get('message', 'Unknown error occurred')
            
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error forcing AI processing: {e}")
        return jsonify({
            'error': f'Failed to start AI processing: {str(e)}',
            'success': False
        }), 500

@app.route('/api/ai/models')
def get_ai_models():
    """Get available AI models and their capabilities"""
    try:
        from core.ai_models import get_available_models, get_all_presets
        
        return jsonify({
            'models': get_available_models(),
            'presets': get_all_presets(),
            'status': 'success'
        })
    except Exception as e:
        logger.error(f"Error getting AI models: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai/model/<model_id>/parameters')
def get_model_parameters(model_id):
    """Get parameter definitions for a specific model"""
    try:
        from core.ai_models import get_model_parameters, get_model_info
        
        model_info = get_model_info(model_id)
        if not model_info:
            return jsonify({'error': 'Model not found'}), 404
            
        return jsonify({
            'model_id': model_id,
            'model_info': model_info,
            'parameters': get_model_parameters(model_id),
            'status': 'success'
        })
    except Exception as e:
        logger.error(f"Error getting model parameters: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings')
def get_settings():
    """Get all system settings"""
    try:
        # Import config here to avoid circular imports
        from config import Config
        
        # Get monitored users with timeout fallback
        monitored_users = []
        if database:
            try:
                monitored_users = database.get_monitored_users()
            except Exception as e:
                logger.warning(f"Timeout getting monitored users, using direct fallback: {e}")
                try:
                    setting = Setting.query.filter_by(key='monitored_users').first()
                    if setting and setting.value:
                        monitored_users = [u.strip() for u in setting.value.split(',') if u.strip()]
                except Exception as e2:
                    logger.error(f"Failed to get monitored users via fallback: {e2}")
                    monitored_users = []

        # Get AI parameters with fallback
        ai_parameters = {}
        if database:
            try:
                ai_parameters = database.get_ai_parameters() or {}
            except Exception as e:
                logger.warning(f"Failed to get AI parameters: {e}")
                ai_parameters = {}

        settings = {
            'monitored_users': monitored_users,
            'check_interval': int(database.get_setting('check_interval', '60')) if database else 60,
            'monitoring_mode': database.get_setting('monitoring_mode', 'hybrid') if database else 'hybrid',
            'historical_hours': int(database.get_setting('historical_hours', '2')) if database else 2,
            'twitter_api_configured': bool(Config.TWITTER_API_KEY),
            'openai_api_configured': bool(getattr(Config, 'OPENAI_API_KEY', None) or (database and database.get_setting('openai_api_key'))),
            'telegram_configured': bool(Config.TELEGRAM_BOT_TOKEN and Config.TELEGRAM_CHAT_ID),
            'media_storage_path': getattr(Config, 'MEDIA_STORAGE_PATH', './media'),
            'telegram_config': {
                'bot_token': database.get_setting('telegram_bot_token', Config.TELEGRAM_BOT_TOKEN) if database else Config.TELEGRAM_BOT_TOKEN,
                'chat_id': database.get_setting('telegram_chat_id', Config.TELEGRAM_CHAT_ID) if database else Config.TELEGRAM_CHAT_ID
            },
            'notification_settings': {
                'enabled': scheduler.notification_enabled if scheduler else False,
                'notify_all_tweets': scheduler.notify_all_tweets if scheduler else False,
                'notify_ai_processed_only': scheduler.notify_ai_processed_only if scheduler else True,
                'notification_delay': scheduler.notification_delay if scheduler else 5
            },
            'ai_settings': {
                'enabled': scheduler.ai_enabled if scheduler else False,
                'batch_size': 10,
                'auto_process': True,
                'model': database.get_setting('ai_model', Config.DEFAULT_AI_MODEL) if database else Config.DEFAULT_AI_MODEL,
                'max_tokens': int(database.get_setting('ai_max_tokens', str(Config.DEFAULT_AI_MAX_TOKENS))) if database else Config.DEFAULT_AI_MAX_TOKENS,
                'prompt': database.get_setting('ai_prompt', Config.DEFAULT_AI_PROMPT) if database else Config.DEFAULT_AI_PROMPT,
                'parameters': ai_parameters
            }
        }
        return jsonify(settings)
    except Exception as e:
        logger.error(f"Error getting settings: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings', methods=['POST'])
def update_settings():
    """Update system settings"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        updated_settings = []
        
        # Update notification settings
        if 'notification_settings' in data and scheduler:
            notification_settings = data['notification_settings']
            
            if 'enabled' in notification_settings:
                if notification_settings['enabled']:
                    scheduler.resume_notifications()
                else:
                    scheduler.pause_notifications()
                updated_settings.append('notification_enabled')
            
            if 'notify_all_tweets' in notification_settings:
                scheduler.notify_all_tweets = notification_settings['notify_all_tweets']
                updated_settings.append('notify_all_tweets')
            
            if 'notify_ai_processed_only' in notification_settings:
                scheduler.notify_ai_processed_only = notification_settings['notify_ai_processed_only']
                updated_settings.append('notify_ai_processed_only')
        
        # Update AI settings
        if 'ai_settings' in data:
            ai_settings = data['ai_settings']
            
            if 'auto_process' in ai_settings and scheduler:
                # This would need to be implemented in scheduler
                updated_settings.append('ai_auto_process')
            
            # Handle new AI parameters format
            if 'parameters' in ai_settings and database:
                # Validate parameters before saving
                from core.ai_models import validate_parameters
                
                params = ai_settings['parameters']
                if 'model' in params:
                    is_valid, errors = validate_parameters(params['model'], params)
                    if not is_valid:
                        return jsonify({'error': 'Invalid parameters', 'details': errors}), 400
                
                # Save all parameters as JSON
                database.set_ai_parameters(params)
                updated_settings.append('ai_parameters')
            else:
                # Backward compatibility - save individual settings
                if 'prompt' in ai_settings and database:
                    database.set_setting('ai_prompt', ai_settings['prompt'])
                    updated_settings.append('ai_prompt')
                
                if 'model' in ai_settings and database:
                    database.set_setting('ai_model', ai_settings['model'])
                    updated_settings.append('ai_model')
                
                if 'max_tokens' in ai_settings and database:
                    database.set_setting('ai_max_tokens', str(ai_settings['max_tokens']))
                    updated_settings.append('ai_max_tokens')
        
        # Update Twitter settings
        if 'twitter_settings' in data and database:
            twitter_settings = data['twitter_settings']
            
            if 'check_interval' in twitter_settings:
                database.set_setting('check_interval', str(twitter_settings['check_interval']))
                if scheduler:
                    scheduler.check_interval = int(twitter_settings['check_interval'])
                updated_settings.append('check_interval')
            
            if 'monitoring_mode' in twitter_settings:
                database.set_setting('monitoring_mode', twitter_settings['monitoring_mode'])
                updated_settings.append('monitoring_mode')
            
            if 'historical_hours' in twitter_settings:
                database.set_setting('historical_hours', str(twitter_settings['historical_hours']))
                updated_settings.append('historical_hours')
        
        # Add Telegram configuration handling
        if 'telegram_config' in data and database:
            telegram_config = data['telegram_config']
            
            if 'bot_token' in telegram_config:
                database.set_setting('telegram_bot_token', telegram_config['bot_token'])
                updated_settings.append('telegram_bot_token')
                
                # Update scheduler if needed
                if scheduler and hasattr(scheduler, 'telegram_notifier'):
                    # Recreate telegram notifier with new token
                    old_notifier = scheduler.telegram_notifier
                    if old_notifier:
                        old_notifier.stop_worker()
                    
                    # Create new notifier with updated config
                    telegram_token = telegram_config['bot_token']
                    telegram_chat_id = telegram_config.get('chat_id') or database.get_setting('telegram_chat_id', '')
                    
                    if telegram_token and telegram_chat_id:
                        from core.telegram_bot import create_telegram_notifier
                        new_config = {
                            'TELEGRAM_BOT_TOKEN': telegram_token,
                            'TELEGRAM_CHAT_ID': telegram_chat_id
                        }
                        scheduler.telegram_notifier = create_telegram_notifier(new_config, database)
                        if scheduler.telegram_notifier:
                            scheduler.telegram_notifier.start_worker()
            
            if 'chat_id' in telegram_config:
                database.set_setting('telegram_chat_id', telegram_config['chat_id'])
                updated_settings.append('telegram_chat_id')
                
                # Update scheduler if needed  
                if scheduler and hasattr(scheduler, 'telegram_notifier'):
                    # Recreate telegram notifier with new chat ID
                    old_notifier = scheduler.telegram_notifier
                    if old_notifier:
                        old_notifier.stop_worker()
                    
                    # Create new notifier with updated config
                    telegram_token = telegram_config.get('bot_token') or database.get_setting('telegram_bot_token', '')
                    telegram_chat_id = telegram_config['chat_id']
                    
                    if telegram_token and telegram_chat_id:
                        from core.telegram_bot import create_telegram_notifier
                        new_config = {
                            'TELEGRAM_BOT_TOKEN': telegram_token,
                            'TELEGRAM_CHAT_ID': telegram_chat_id
                        }
                        scheduler.telegram_notifier = create_telegram_notifier(new_config, database)
                        if scheduler.telegram_notifier:
                            scheduler.telegram_notifier.start_worker()
        
        return jsonify({
            'success': True,
            'updated_settings': updated_settings,
            'message': f"Updated {len(updated_settings)} settings"
        })
        
    except Exception as e:
        logger.error(f"Error updating settings: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/system/restart', methods=['POST'])
def restart_system():
    """Restart system components"""
    try:
        data = request.get_json() or {}
        component = data.get('component', 'all')
        
        if component == 'scheduler' or component == 'all':
            if scheduler:
                scheduler.stop()
                time.sleep(2)
                scheduler.start()
        
        return jsonify({
            'success': True,
            'message': f"Restarted {component} successfully",
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error restarting system: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/system/status/detailed')
def get_detailed_system_status():
    """Get comprehensive system status"""
    try:
        # Import config here to avoid circular imports
        from config import Config
        status = {
            'system_health': 'healthy',
            'uptime': time.time() - start_time if 'start_time' in globals() else 0,
            'components': {
                'database': {
                    'status': 'connected' if database else 'disconnected',
                    'location': 'PostgreSQL via SQLAlchemy' if database else None,
                    'last_backup': None  # Could implement backup tracking
                },
                'scheduler': {
                    'status': 'running' if scheduler and hasattr(scheduler, 'is_running') and scheduler.is_running else 'stopped',
                    'monitored_users': scheduler.monitored_users if scheduler else [],
                    'last_poll': scheduler.last_poll_time if scheduler and hasattr(scheduler, 'last_poll_time') and scheduler.last_poll_time else None,
                    'next_poll': scheduler.next_poll_time if scheduler and hasattr(scheduler, 'next_poll_time') and scheduler.next_poll_time else None
                },
                'twitter_api': {
                    'status': 'configured' if Config.TWITTER_API_KEY else 'not_configured',
                    'rate_limit_remaining': None  # Could implement rate limit tracking
                },
                'openai_api': {
                    'status': 'configured' if getattr(Config, 'OPENAI_API_KEY', None) else 'not_configured',
                    'model': getattr(Config, 'OPENAI_MODEL', 'gpt-3.5-turbo')
                },
                'telegram': {
                    'status': 'configured' if (Config.TELEGRAM_BOT_TOKEN and Config.TELEGRAM_CHAT_ID) else 'not_configured',
                    'bot_token_valid': bool(Config.TELEGRAM_BOT_TOKEN),
                    'chat_id_valid': bool(Config.TELEGRAM_CHAT_ID)
                }
            },
            'storage': {
                'media_directory': getattr(Config, 'MEDIA_STORAGE_PATH', './media'),
                'database_size': get_database_size() if database else 0,
                'media_files_count': get_media_files_count() if database else 0
            },
            'performance': {
                'avg_processing_time': get_avg_processing_time() if database else 0,
                'total_api_calls': get_total_api_calls() if database else 0,
                'success_rate': get_success_rate() if database else 100
            }
        }
        
        return jsonify(status)
        
    except Exception as e:
        logger.error(f"Error getting detailed system status: {e}")
        return jsonify({'error': str(e)}), 500

def get_database_size():
    """Get database size info for PostgreSQL"""
    try:
        # For PostgreSQL, we can't get file size directly
        # Return approximate size based on record count
        if database:
            tweet_count = Tweet.query.count()
            media_count = Media.query.count()
            ai_result_count = AIResult.query.count()
            # Rough estimate: 1KB per tweet, 0.5KB per media, 2KB per AI result
            estimated_mb = (tweet_count + media_count * 0.5 + ai_result_count * 2) / 1024
            return round(max(estimated_mb, 0.1), 2)  # Minimum 0.1 MB
        return 0
    except:
        return 0

def get_media_files_count():
    """Get count of media files"""
    try:
        import os
        from config import Config
        media_path = getattr(Config, 'MEDIA_STORAGE_PATH', './media')
        if os.path.exists(media_path):
            count = 0
            for root, dirs, files in os.walk(media_path):
                count += len(files)
            return count
        return 0
    except:
        return 0

def get_avg_processing_time():
    """Get average tweet processing time"""
    # This would require implementation in database
    return 0.5  # Placeholder

def get_total_api_calls():
    """Get total API calls made"""
    # This would require implementation in database
    return 0  # Placeholder

def get_success_rate():
    """Get success rate percentage"""
    # This would require implementation in database
    return 95.5  # Placeholder

@app.route('/api/users')
def get_monitored_users():
    """Get list of currently monitored users"""
    try:
        # Get monitored users from database settings
        if database:
            users = database.get_monitored_users()
        else:
            # Fallback to empty list if no database
            users = []
        
        # Get stats for each user using SQLAlchemy
        user_stats = []
        for username in users:
            if database:
                try:
                    # Get tweet count for user
                    tweet_count = Tweet.query.filter_by(username=username).count()
                    
                    # Get last tweet
                    last_tweet_obj = Tweet.query.filter_by(username=username).order_by(Tweet.created_at.desc()).first()
                    last_tweet = last_tweet_obj.created_at.isoformat() if last_tweet_obj else None
                    
                    # Get AI processed count
                    ai_processed = Tweet.query.filter_by(username=username, ai_processed=True).count()
                    
                    user_stats.append({
                        'username': username,
                        'tweet_count': tweet_count,
                        'last_tweet': last_tweet,
                        'ai_processed': ai_processed
                    })
                except Exception as e:
                    logger.error(f"Error getting stats for user {username}: {e}")
                    user_stats.append({
                        'username': username,
                        'tweet_count': 0,
                        'last_tweet': None,
                        'ai_processed': 0
                    })
            else:
                user_stats.append({
                    'username': username,
                    'tweet_count': 0,
                    'last_tweet': None,
                    'ai_processed': 0
                })
        
        return jsonify({
            'users': user_stats,
            'total_users': len(users)
        })
    except Exception as e:
        logger.error(f"Error getting monitored users: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/users/add', methods=['POST'])
def add_monitored_user():
    """Add a new user to monitor"""
    try:
        data = request.get_json()
        if not data or 'username' not in data:
            return jsonify({'error': 'Username is required'}), 400
        
        username = data['username'].strip()
        
        # Extract username from URL if provided
        if 'twitter.com/' in username or 'x.com/' in username:
            username = username.split('/')[-1].split('?')[0]
        
        # Remove @ if present
        username = username.lstrip('@')
        
        if not username:
            return jsonify({'error': 'Invalid username'}), 400
        
        # Add user to database AND scheduler
        success = False
        if database:
            if scheduler:
                # Use scheduler's add_user method which updates both database and in-memory list
                success = scheduler.add_user(username)
            else:
                # Fallback to database only if scheduler not available
                success = database.add_monitored_user(username)
            
            if success:
                return jsonify({
                    'success': True,
                    'message': f'User @{username} added to monitoring',
                    'username': username
                })
            else:
                return jsonify({'error': f'Failed to add user @{username}'}), 400
        else:
            return jsonify({'error': 'Database not available'}), 500
            
    except Exception as e:
        logger.error(f"Error adding monitored user: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/users/remove', methods=['POST'])
def remove_monitored_user():
    """Remove a user from monitoring"""
    try:
        data = request.get_json()
        if not data or 'username' not in data:
            return jsonify({'error': 'Username is required'}), 400
        
        username = data['username'].strip()
        
        # Remove user from database AND scheduler
        success = False
        if database:
            if scheduler:
                # Use scheduler's remove_user method which updates both database and in-memory list
                success = scheduler.remove_user(username)
            else:
                # Fallback to database only if scheduler not available
                success = database.remove_monitored_user(username)
            
            if success:
                return jsonify({
                    'success': True,
                    'message': f'User @{username} removed from monitoring',
                    'username': username
                })
            else:
                return jsonify({'error': f'Failed to remove user @{username}'}), 400
        else:
            return jsonify({'error': 'Database not available'}), 500
            
    except Exception as e:
        logger.error(f"Error removing monitored user: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/historical/scrape', methods=['POST'])
def scrape_historical_tweets():
    """Trigger historical tweet scraping"""
    try:
        data = request.get_json() or {}
        hours = data.get('hours', 2)
        
        if scheduler:
            # Trigger historical scrape
            scheduler._historical_scrape(hours)
            return jsonify({
                'success': True,
                'message': f'Historical scrape initiated for last {hours} hours'
            })
        else:
            return jsonify({'error': 'Scheduler not available'}), 500
            
    except Exception as e:
        logger.error(f"Error triggering historical scrape: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/test/notification', methods=['POST'])
def test_notification():
    """Send a test notification to Telegram"""
    try:
        if scheduler and scheduler.telegram_notifier:
            message = "🔔 Test notification from Persian News Translator System\n\n"
            message += "If you see this message, your Telegram notifications are working correctly!"
            
            # Use the correct method to queue a text message
            success = scheduler.telegram_notifier.queue_text_message(message)
            
            if success:
                return jsonify({
                    'success': True,
                    'message': 'Test notification queued successfully'
                })
            else:
                return jsonify({'error': 'Failed to queue test notification'}), 500
        else:
            return jsonify({'error': 'Telegram bot not configured or scheduler not available'}), 400
            
    except Exception as e:
        logger.error(f"Error sending test notification: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/telegram/test/formatted', methods=['POST'])
def test_formatted_notification():
    """Send a test notification with HTML formatting"""
    try:
        if scheduler and scheduler.telegram_notifier:
            message = (
                "🧪 <b>HTML Formatting Test</b>\n\n"
                "✅ <i>Bold text</i> and <u>underlined text</u>\n"
                "🔗 <a href='https://telegram.org'>Link example</a>\n"
                "💻 <code>Inline code</code>\n\n"
                "📅 <b>Time:</b> " + datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )
            
            success = scheduler.telegram_notifier.queue_text_message(message, disable_preview=False)
            
            if success:
                return jsonify({
                    'success': True,
                    'message': 'HTML formatted test notification queued successfully'
                })
            else:
                return jsonify({'error': 'Failed to queue formatted test notification'}), 500
        else:
            return jsonify({'error': 'Telegram bot not configured or scheduler not available'}), 400
            
    except Exception as e:
        logger.error(f"Error sending formatted test notification: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/telegram/status')
def get_telegram_status():
    """Get detailed Telegram bot status and statistics"""
    try:
        if scheduler and scheduler.telegram_notifier:
            status = scheduler.telegram_notifier.get_queue_status()
            return jsonify({
                'success': True,
                'status': status
            })
        else:
            return jsonify({'error': 'Telegram bot not configured or scheduler not available'}), 400
            
    except Exception as e:
        logger.error(f"Error getting Telegram status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/telegram/queue/clear', methods=['POST'])
def clear_telegram_queue():
    """Clear the Telegram message queue"""
    try:
        if scheduler and scheduler.telegram_notifier:
            cleared_count = scheduler.telegram_notifier.clear_queue()
            return jsonify({
                'success': True,
                'message': f'Cleared {cleared_count} messages from queue',
                'cleared_count': cleared_count
            })
        else:
            return jsonify({'error': 'Telegram bot not configured or scheduler not available'}), 400
            
    except Exception as e:
        logger.error(f"Error clearing Telegram queue: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/debug/initialization')
def debug_initialization_status():
    """Debug endpoint to check component initialization status"""
    try:
        status = {
            'database': database is not None,
            'rss_webhook_handler': rss_webhook_handler is not None,
            'webhook_handler': webhook_handler is not None,
            'twitter_client': twitter_client is not None,
            'ai_processor': ai_processor is not None,
            'scheduler': scheduler is not None,
            'background_worker': background_worker is not None,
            'initialization_success': initialization_success if 'initialization_success' in globals() else False
        }
        
        # Test database connection if available
        if database:
            try:
                Setting.query.limit(1).all()
                status['database_test'] = 'success'
            except Exception as e:
                status['database_test'] = f'failed: {str(e)}'
        else:
            status['database_test'] = 'no database instance'
            
        return jsonify(status)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/debug/users')
def debug_monitored_users():
    """Debug endpoint to check monitored users directly"""
    try:
        result = {}
        if database:
            result['database_get_monitored_users'] = database.get_monitored_users()
            
            # Try SQLAlchemy query
            try:
                setting = Setting.query.filter_by(key='monitored_users').first()
                result['sqlalchemy_query'] = {
                    'exists': setting is not None,
                    'value': setting.value if setting else None
                }
            except Exception as e:
                result['sqlalchemy_query'] = {'error': str(e)}
                
        else:
            result['error'] = 'No database connection'
            
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/cache/clear', methods=['POST'])
def clear_cache():
    """Clear application cache"""
    try:
        # Clear any in-memory caches
        cleared_items = []
        
        # Clear scheduler cache if available
        if scheduler:
            if hasattr(scheduler, 'clear_cache'):
                scheduler.clear_cache()
                cleared_items.append('scheduler_cache')
        
        # Clear database cache if available
        if database:
            if hasattr(database, 'clear_cache'):
                database.clear_cache()
                cleared_items.append('database_cache')
            
            # Also clear any temporary data
            database.execute("DELETE FROM tweets WHERE created_at < datetime('now', '-7 days')")
            cleared_items.append('old_tweets')
        
        # Clear Flask cache if using caching
        if hasattr(app, 'cache'):
            app.cache.clear()
            cleared_items.append('flask_cache')
        
        return jsonify({
            'success': True,
            'message': f'Cache cleared successfully',
            'cleared': cleared_items
        })
        
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/media/<filename>')
def serve_media(filename):
    """Serve media files"""
    try:
        from config import Config
        media_dir = getattr(Config, 'MEDIA_STORAGE_PATH', './media')
        
        # Security check - ensure filename doesn't contain path traversal
        import os
        if '..' in filename or '/' in filename or '\\' in filename:
            return "Invalid filename", 400
        
        filepath = os.path.join(media_dir, filename)
        
        if not os.path.exists(filepath):
            return "File not found", 404
        
        from flask import send_file
        return send_file(filepath)
        
    except Exception as e:
        logger.error(f"Error serving media file {filename}: {e}")
        return "Error serving file", 500

@app.route('/api/background-worker/stats')
def get_background_worker_stats():
    """Get background worker statistics"""
    if not background_worker:
        return jsonify({'error': 'Background worker not initialized'}), 500
    
    try:
        stats = background_worker.get_stats()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting background worker stats: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/background-worker/process/<tweet_id>', methods=['POST'])
def force_process_tweet(tweet_id):
    """Force immediate processing of a specific tweet"""
    if not background_worker:
        return jsonify({'error': 'Background worker not initialized'}), 500
    
    try:
        result = background_worker.force_process_tweet(tweet_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error force processing tweet {tweet_id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/database/completion-stats')
def get_database_completion_stats():
    """Get statistics about database completeness (AI analysis and media downloads)"""
    try:
        # Get tweets missing AI analysis
        missing_ai = database.get_tweets_without_ai_analysis(limit=1000)
        missing_ai_count = len(missing_ai)
        
        # Get tweets with missing media
        missing_media = database.get_tweets_with_missing_media(limit=1000)
        missing_media_count = len(missing_media)
        
        # Get total tweet count
        total_tweets = database.get_total_tweets_count()
        
        # Calculate completion percentages
        ai_completion = ((total_tweets - missing_ai_count) / total_tweets * 100) if total_tweets > 0 else 100
        media_completion = ((total_tweets - missing_media_count) / total_tweets * 100) if total_tweets > 0 else 100
        
        return jsonify({
            'total_tweets': total_tweets,
            'missing_ai_analysis': missing_ai_count,
            'missing_media_downloads': missing_media_count,
            'ai_completion_percentage': round(ai_completion, 1),
            'media_completion_percentage': round(media_completion, 1),
            'overall_completion': round((ai_completion + media_completion) / 2, 1)
        })
        
    except Exception as e:
        logger.error(f"Error getting database completion stats: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics/summary')
def get_analytics_summary():
    """Get analytics summary data"""
    try:
        time_range = request.args.get('range', '7d')
        
        # Get basic statistics
        db_stats = database.get_stats() if database else {}
        
        # Get time-based data
        activity_data = get_activity_data(time_range)
        distribution_data = get_distribution_data(time_range)
        performance_data = get_performance_data(time_range)
        
        # Get top users
        top_users = get_top_users_stats(limit=10)
        
        # Get AI insights
        ai_insights = get_ai_insights(time_range)
        
        # Get system health
        system_health = get_system_health_metrics()
        
        return jsonify({
            'summary': {
                'total_tweets': db_stats.get('total_tweets', 0),
                'ai_processed': db_stats.get('ai_processed', 0),
                'media_downloaded': db_stats.get('media_files', 0),
                'notifications_sent': db_stats.get('telegram_sent', 0)
            },
            'activity_data': activity_data,
            'distribution_data': distribution_data,
            'performance_data': performance_data,
            'top_users': top_users,
            'ai_insights': ai_insights,
            'system_health': system_health,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting analytics summary: {e}")
        return jsonify({'error': str(e)}), 500

def get_activity_data(time_range):
    """Get tweet activity data for charts"""
    # This is a simplified implementation
    # In production, you'd query the database for actual time-series data
    return {
        'labels': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
        'tweets': [120, 150, 180, 170, 200, 160, 140],
        'ai_processed': [100, 130, 160, 150, 180, 140, 120]
    }

def get_distribution_data(time_range):
    """Get tweet type distribution data - SQLAlchemy version"""
    try:
        if database:
            # Get tweet type counts using SQLAlchemy
            regular = Tweet.query.filter_by(tweet_type='tweet').count()
            retweets = Tweet.query.filter_by(tweet_type='retweet').count()
            replies = Tweet.query.filter_by(tweet_type='reply').count()
            
            # Count tweets with media
            media_tweet_ids = db.session.query(Media.tweet_id).distinct().all()
            media = len(media_tweet_ids) if media_tweet_ids else 0
            
            return {
                'regular': regular,
                'retweets': retweets,
                'replies': replies,
                'media': media
            }
    except Exception as e:
        logger.error(f"Error getting distribution data: {e}")
        return {'regular': 0, 'retweets': 0, 'replies': 0, 'media': 0}

def get_performance_data(time_range):
    """Get performance metrics data"""
    # Simplified implementation
    return {
        'labels': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
        'values': [2.5, 2.8, 2.3, 2.6, 2.4, 2.7, 2.5]
    }

def get_top_users_stats(limit=10):
    """Get statistics for top users by tweet count - SQLAlchemy version"""
    try:
        users = []
        if database:
            monitored_users = database.get_monitored_users()
            for username in monitored_users[:limit]:
                # Get tweet count and AI processed count using SQLAlchemy
                tweet_count = Tweet.query.filter_by(username=username).count()
                ai_processed = Tweet.query.filter_by(username=username, ai_processed=True).count()
                
                users.append({
                    'username': username,
                    'tweet_count': tweet_count,
                    'ai_processed': ai_processed
                })
        return users
    except Exception as e:
        logger.error(f"Error getting top users stats: {e}")
        return []

def get_ai_insights(time_range):
    """Get AI processing insights"""
    try:
        # This would query actual AI processing metrics
        return {
            'avg_processing_time': 2.5,
            'success_rate': 95.5,
            'tokens_used': 150000,
            'cost_estimate': 4.50
        }
    except:
        return {
            'avg_processing_time': 0,
            'success_rate': 0,
            'tokens_used': 0,
            'cost_estimate': 0
        }

def get_system_health_metrics():
    """Get system health metrics"""
    try:
        # Database health (simplified - check if we can connect)
        db_health = 100 if database else 0
        
        # API health
        from config import Config
        api_health = 0
        if Config.TWITTER_API_KEY:
            api_health += 33
        if getattr(Config, 'OPENAI_API_KEY', None):
            api_health += 33
        if Config.TELEGRAM_BOT_TOKEN:
            api_health += 34
            
        # Storage usage
        storage_used = 0
        try:
            import shutil
            total, used, free = shutil.disk_usage("/")
            storage_used_percentage = (used / total) * 100
        except:
            storage_used_percentage = 0
            
        return {
            'database': db_health,
            'api': api_health,
            'storage_used_percentage': round(storage_used_percentage, 1),
            'recent_errors': []  # Would fetch from error logs
        }
    except Exception as e:
        logger.error(f"Error getting system health: {e}")
        return {
            'database': 0,
            'api': 0,
            'storage_used_percentage': 0,
            'recent_errors': []
        }

@app.route('/api/analytics/export')
def export_analytics_data():
    """Export analytics data as CSV"""
    try:
        import csv
        import io
        from flask import Response
        
        time_range = request.args.get('range', '7d')
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write headers
        writer.writerow(['Metric', 'Value', 'Timestamp'])
        
        # Get data
        db_stats = database.get_stats() if database else {}
        timestamp = datetime.now().isoformat()
        
        # Write data
        writer.writerow(['Total Tweets', db_stats.get('total_tweets', 0), timestamp])
        writer.writerow(['AI Processed', db_stats.get('ai_processed', 0), timestamp])
        writer.writerow(['Media Downloaded', db_stats.get('media_files', 0), timestamp])
        writer.writerow(['Notifications Sent', db_stats.get('telegram_sent', 0), timestamp])
        
        # Create response
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename=analytics_{time_range}.csv'}
        )
        
    except Exception as e:
        logger.error(f"Error exporting analytics: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/deployment/status')
def deployment_status():
    """Check deployment status and build info"""
    return jsonify({
        'status': 'LATEST_BUILD_DEPLOYED',
        'build_date': '2024-12-28',
        'commit_info': 'PostgreSQL_SQLAlchemy_Fixed',
        'database_type': 'PostgreSQL via SQLAlchemy',
        'user_management_fixed': True,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/debug/direct-db-test')
def direct_database_test():
    """Direct database test without component dependencies"""
    try:
        # Test basic database query
        with app.app_context():
            # Try to create tables
            db.create_all()
            
            # Test a simple query
            test_setting = Setting.query.limit(1).all()
            
            # Try to count records
            settings_count = Setting.query.count()
            tweets_count = Tweet.query.count()
            
            return jsonify({
                'status': 'success',
                'database_url': DatabaseConfig.get_database_url(),
                'is_postgresql': DatabaseConfig.is_postgresql(),
                'settings_count': settings_count,
                'tweets_count': tweets_count,
                'tables_created': True
            })
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'database_url': DatabaseConfig.get_database_url(),
            'is_postgresql': DatabaseConfig.is_postgresql()
        }), 500

@app.route('/api/users/direct')
def get_monitored_users_direct():
    """Get list of currently monitored users - Direct SQLAlchemy version"""
    try:
        # Get monitored users directly from SQLAlchemy settings
        monitored_users_setting = Setting.query.filter_by(key='monitored_users').first()
        if monitored_users_setting and monitored_users_setting.value:
            users = [u.strip() for u in monitored_users_setting.value.split(',') if u.strip()]
        else:
            users = []
        
        # Get stats for each user using direct SQLAlchemy
        user_stats = []
        for username in users:
            try:
                # Get tweet count for user
                tweet_count = Tweet.query.filter_by(username=username).count()
                
                # Get last tweet
                last_tweet_obj = Tweet.query.filter_by(username=username).order_by(Tweet.created_at.desc()).first()
                last_tweet = last_tweet_obj.created_at.isoformat() if last_tweet_obj else None
                
                # Get AI processed count
                ai_processed = Tweet.query.filter_by(username=username, ai_processed=True).count()
                
                user_stats.append({
                    'username': username,
                    'tweet_count': tweet_count,
                    'last_tweet': last_tweet,
                    'ai_processed': ai_processed
                })
            except Exception as e:
                logger.error(f"Error getting stats for user {username}: {e}")
                user_stats.append({
                    'username': username,
                    'tweet_count': 0,
                    'last_tweet': None,
                    'ai_processed': 0,
                    'error': str(e)
                })
        
        return jsonify({
            'users': user_stats,
            'total_users': len(users),
            'method': 'direct_sqlalchemy',
            'success': True
        })
    except Exception as e:
        logger.error(f"Error getting monitored users directly: {e}")
        return jsonify({'error': str(e), 'method': 'direct_sqlalchemy'}), 500

@app.route('/api/test/simple')
def simple_test():
    """Simple test endpoint to verify deployment"""
    return jsonify({
        'test': 'DEPLOYMENT_WORKING',
        'timestamp': datetime.now().isoformat(),
        'commit': '7c13cc1_manual_redeploy_test'
    })

@app.route('/api/debug/database-methods')
def debug_database_methods():
    """Debug endpoint to check which methods are available on database wrapper"""
    try:
        if database:
            methods = [method for method in dir(database) if not method.startswith('_')]
            missing_methods = []
            
            # Check for specific methods that were failing
            required_methods = ['get_ai_parameters', 'set_ai_parameters', 'get_monitored_users']
            for method in required_methods:
                if not hasattr(database, method):
                    missing_methods.append(method)
            
            return jsonify({
                'available_methods': methods,
                'missing_methods': missing_methods,
                'database_type': str(type(database)),
                'has_db_path': hasattr(database, 'db_path'),
                'test_get_monitored_users': len(database.get_monitored_users()) if hasattr(database, 'get_monitored_users') else 'NOT_AVAILABLE'
            })
        else:
            return jsonify({'error': 'No database instance available'})
    except Exception as e:
        return jsonify({'error': str(e), 'database_available': database is not None})

@app.route('/api/version/check')
def version_check():
    """Simple endpoint to verify latest deployment"""
    return "LATEST_DEPLOYMENT_33b90df_CRITICAL_FIX"

@app.route('/api/debug/database-wrapper-test')
def test_database_wrapper():
    """Test database wrapper methods"""
    try:
        if not database:
            return jsonify({'error': 'Database not initialized'}), 500
        
        # Test that all required methods exist
        required_methods = [
            'get_monitored_users', 'add_monitored_user', 'remove_monitored_user',
            'get_tweets', 'insert_tweet', 'tweet_exists', 'store_tweet',
            'get_stats', 'get_setting', 'set_setting',
            'get_unprocessed_tweets', 'store_ai_result', 'update_tweet_ai_status',
            'get_unprocessed_count', 'get_total_tweets_count', 'get_failed_ai_tweets',
            'clear_ai_error', 'get_recent_ai_results', 'get_ai_parameters', 'set_ai_parameters',
            'get_tweets_without_ai_analysis', 'get_tweets_with_missing_media', 'mark_telegram_sent'
        ]
        
        required_properties = ['db_path']
        
        missing_methods = []
        for method in required_methods:
            if not hasattr(database, method):
                missing_methods.append(method)
        
        missing_properties = []
        for prop in required_properties:
            if not hasattr(database, prop):
                missing_properties.append(prop)
        
        return jsonify({
            'status': 'success',
            'database_type': str(type(database)),
            'has_all_methods': len(missing_methods) == 0,
            'missing_methods': missing_methods,
            'missing_properties': missing_properties,
            'total_required_methods': len(required_methods),
            'total_required_properties': len(required_properties)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/telegram/validate', methods=['POST'])
def validate_telegram_config():
    """Validate Telegram bot configuration and get bot info"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        bot_token = data.get('bot_token', '').strip()
        chat_id = data.get('chat_id', '').strip()
        
        if not bot_token or not chat_id:
            return jsonify({'error': 'Bot token and chat ID are required'}), 400
        
        # Create temporary notifier to validate
        from core.telegram_bot import TelegramNotifier
        temp_notifier = TelegramNotifier(bot_token, chat_id)
        
        # Validate bot token
        import asyncio
        async def validate_bot():
            try:
                bot_info = await temp_notifier.bot.get_me()
                
                # Try to get chat info
                chat_info = None
                try:
                    chat_info = await temp_notifier.bot.get_chat(chat_id)
                except Exception as chat_error:
                    logger.warning(f"Could not get chat info: {chat_error}")
                
                return {
                    'valid': True,
                    'bot_info': {
                        'id': bot_info.id,
                        'username': bot_info.username,
                        'first_name': bot_info.first_name,
                        'is_bot': bot_info.is_bot
                    },
                    'chat_info': {
                        'id': chat_info.id if chat_info else chat_id,
                        'title': getattr(chat_info, 'title', None),
                        'type': getattr(chat_info, 'type', 'unknown'),
                        'username': getattr(chat_info, 'username', None)
                    } if chat_info else None
                }
            except Exception as e:
                logger.error(f"Bot validation failed: {e}")
                return {'valid': False, 'error': str(e)}
        
        # Run validation
        result = asyncio.run(validate_bot())
        
        if result['valid']:
            return jsonify({
                'success': True,
                'bot_info': result['bot_info'],
                'chat_info': result['chat_info']
            })
        else:
            return jsonify({'error': result['error']}), 400
            
    except Exception as e:
        logger.error(f"Error validating Telegram config: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/openai/set-key', methods=['POST'])
def set_openai_key():
    """Simple endpoint to set OpenAI API key"""
    try:
        data = request.get_json()
        if not data or 'api_key' not in data:
            return jsonify({'error': 'API key required'}), 400
        
        api_key = data['api_key'].strip()
        if not api_key.startswith('sk-'):
            return jsonify({'error': 'Invalid API key format'}), 400
        
        # Set the API key in database
        if database:
            success = database.set_setting('openai_api_key', api_key)
            if success:
                # Update the config at runtime
                from config import Config
                Config.OPENAI_API_KEY = api_key
                
                # Update scheduler's OpenAI client if available
                if scheduler and hasattr(scheduler, 'ai_processor') and scheduler.ai_processor:
                    try:
                        scheduler.ai_processor.openai_client.api_key = api_key
                    except:
                        pass
                
                return jsonify({
                    'success': True,
                    'message': 'OpenAI API key updated successfully',
                    'key_prefix': api_key[:10] + '...'
                })
            else:
                return jsonify({'error': 'Failed to save API key to database'}), 500
        else:
            return jsonify({'error': 'Database not available'}), 500
            
    except Exception as e:
        logger.error(f"Error setting OpenAI API key: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Ensure required directories exist
    os.makedirs('logs', exist_ok=True)
    os.makedirs('data', exist_ok=True)  # Changed from 'media' to 'data' for production
    
    # Display startup information
    try:
        from startup_info import display_startup_info
        display_startup_info()
    except ImportError:
        logger.warning("Could not import startup_info module")
    
    # Record start time for uptime calculation
    start_time = time.time()
    
    logger.info("Starting Twitter Monitor Application")
    
    # Initialize components
    if initialize_components():
        logger.info("All components initialized successfully")
        
        # Production-ready configuration
        port = int(os.environ.get('PORT', 5001))
        host = os.environ.get('HOST', '0.0.0.0')
        debug = os.environ.get('FLASK_ENV', 'production') != 'production'
        
        logger.info(f"Starting server on {host}:{port} (debug={debug})")
        
        # Start the web application
        app.run(
            host=host,
            port=port,
            debug=debug,
            threaded=True  # Enable threading for better performance
        )
    else:
        logger.error("Failed to initialize components")
        exit(1) 