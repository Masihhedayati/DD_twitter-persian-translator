# Twitter Monitoring & Notification System
# Main Flask Application

from flask import Flask, render_template, request, jsonify
import os
import logging
from datetime import datetime
import atexit
import threading
import time

# Import core components
from core.database import Database
from core.polling_scheduler import PollingScheduler
from core.error_handler import get_system_health, log_error
from core.webhook_handler import TwitterWebhookHandler
from core.ai_processor import AIProcessor
from config import Config
from core.openai_client import OpenAIClient

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

# Global variables for components
database = None
scheduler = None
webhook_handler = None
ai_processor = None

def initialize_components():
    """Initialize database, scheduler, and webhook components"""
    global database, scheduler, webhook_handler, ai_processor
    
    try:
        # Initialize database
        database = Database(app.config.get('DATABASE_PATH', './tweets.db'))
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
        
        # Initialize webhook handler
        webhook_handler = TwitterWebhookHandler(database, ai_processor, config)
        logger.info("Webhook handler initialized successfully")
        
        # Initialize scheduler based on mode
        webhook_only_mode = config.get('WEBHOOK_ONLY_MODE', False)
        hybrid_mode = config.get('HYBRID_MODE', True)
        
        if not webhook_only_mode:
            scheduler = PollingScheduler(config)
            logger.info("Polling scheduler initialized successfully")
            
            # Start scheduler
            scheduler.start()
            
            if hybrid_mode:
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

def cleanup_components():
    """Cleanup components on app shutdown"""
    global scheduler
    
    try:
        if scheduler:
            scheduler.stop()
            logger.info("Scheduler stopped successfully")
    except Exception as e:
        logger.error(f"Error stopping scheduler: {e}")

# Register cleanup function
atexit.register(cleanup_components)

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

@app.route('/health')
def health_check():
    """Health check endpoint for monitoring"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    })

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
            media = database.get_tweet_media(tweet['id'])
            
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
    """Get tweets with applied filters"""
    try:
        import sqlite3
        with sqlite3.connect(database.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Build query with filters
            query = "SELECT * FROM tweets WHERE 1=1"
            params = []
            
            # Username filter
            if username:
                query += " AND username = ?"
                params.append(username)
            
            # Search query filter
            if search_query:
                query += " AND (content LIKE ? OR display_name LIKE ?)"
                search_param = f"%{search_query}%"
                params.extend([search_param, search_param])
            
            # Filter type
            if filter_type == 'images':
                query += " AND id IN (SELECT DISTINCT tweet_id FROM media WHERE media_type = 'image')"
            elif filter_type == 'videos':
                query += " AND id IN (SELECT DISTINCT tweet_id FROM media WHERE media_type IN ('video', 'gif'))"
            elif filter_type == 'ai':
                query += " AND ai_processed = 1"
            
            # Since timestamp for real-time updates
            if since:
                query += " AND detected_at > ?"
                params.append(since)
            
            # Order by detected_at for chronological ordering (newest first)
            query += " ORDER BY detected_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            tweets = [dict(row) for row in cursor.fetchall()]
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
    
    try:
        data = request.get_json() or {}
        batch_size = data.get('batch_size', 10)
        
        result = scheduler.force_ai_processing(batch_size=batch_size)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error forcing AI processing: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings')
def get_settings():
    """Get all system settings"""
    try:
        # Import config here to avoid circular imports
        from config import Config
        
        settings = {
            'monitored_users': Config.MONITORED_USERS,
            'check_interval': int(database.get_setting('check_interval', '60')) if database else 60,
            'monitoring_mode': database.get_setting('monitoring_mode', 'hybrid') if database else 'hybrid',
            'historical_hours': int(database.get_setting('historical_hours', '2')) if database else 2,
            'twitter_api_configured': bool(Config.TWITTER_API_KEY),
            'openai_api_configured': bool(getattr(Config, 'OPENAI_API_KEY', None)),
            'telegram_configured': bool(Config.TELEGRAM_BOT_TOKEN and Config.TELEGRAM_CHAT_ID),
            'media_storage_path': getattr(Config, 'MEDIA_STORAGE_PATH', './media'),
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
                'prompt': database.get_setting('ai_prompt', Config.DEFAULT_AI_PROMPT) if database else Config.DEFAULT_AI_PROMPT
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
            
            # Save AI prompt and model settings to database
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
                    'location': database.db_path if database else None,
                    'last_backup': None  # Could implement backup tracking
                },
                'scheduler': {
                    'status': 'running' if scheduler and hasattr(scheduler, 'running') and scheduler.running else 'stopped',
                    'monitored_users': scheduler.monitored_users if scheduler else [],
                    'last_poll': scheduler.last_poll_time.isoformat() if scheduler and hasattr(scheduler, 'last_poll_time') and scheduler.last_poll_time else None,
                    'next_poll': scheduler.next_poll_time.isoformat() if scheduler and hasattr(scheduler, 'next_poll_time') and scheduler.next_poll_time else None
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
    """Get database file size in MB"""
    try:
        import os
        if os.path.exists(database.db_path):
            size_bytes = os.path.getsize(database.db_path)
            return round(size_bytes / 1024 / 1024, 2)
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
            users = app.config.get('MONITORED_USERS', ['elonmusk', 'naval', 'paulg'])
        
        # Get stats for each user
        user_stats = []
        for username in users:
            if database:
                # Get basic tweet count for user
                import sqlite3
                with sqlite3.connect(database.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM tweets WHERE username = ?", (username,))
                    tweet_count = cursor.fetchone()[0]
                    
                    cursor.execute("SELECT MAX(created_at) FROM tweets WHERE username = ?", (username,))
                    last_tweet = cursor.fetchone()[0]
                    
                    cursor.execute("SELECT COUNT(*) FROM tweets WHERE username = ? AND ai_processed = 1", (username,))
                    ai_processed = cursor.fetchone()[0]
                
                user_stats.append({
                    'username': username,
                    'tweet_count': tweet_count,
                    'last_tweet': last_tweet,
                    'ai_processed': ai_processed
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
        
        # Add user to database
        if database:
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
        
        # Remove user from database
        if database:
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
        if scheduler and scheduler.telegram_bot:
            message = "🔔 Test notification from Persian News Translator System\n\n"
            message += "If you see this message, your Telegram notifications are working correctly!"
            
            success = scheduler.telegram_bot.send_message(message)
            
            if success:
                return jsonify({
                    'success': True,
                    'message': 'Test notification sent successfully'
                })
            else:
                return jsonify({'error': 'Failed to send test notification'}), 500
        else:
            return jsonify({'error': 'Telegram bot not configured or scheduler not available'}), 400
            
    except Exception as e:
        logger.error(f"Error sending test notification: {e}")
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

if __name__ == '__main__':
    # Ensure required directories exist
    os.makedirs('logs', exist_ok=True)
    os.makedirs('media', exist_ok=True)
    
    # Record start time for uptime calculation
    start_time = time.time()
    
    logger.info("Starting Twitter Monitor Application")
    
    # Initialize components
    if initialize_components():
        logger.info("All components initialized successfully")
        
        # Start the web application
        app.run(
            host=app.config.get('HOST', '0.0.0.0'),
            port=app.config.get('PORT', 5001),  # Changed default to avoid AirPlay conflict
            debug=app.config.get('DEBUG', True)
        )
    else:
        logger.error("Failed to initialize components")
        exit(1) 