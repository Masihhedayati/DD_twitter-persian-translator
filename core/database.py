# Database module for Twitter Monitoring System
import sqlite3
import os
from typing import Dict, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class Database:
    """Database management class for Twitter Monitor"""
    
    def __init__(self, db_path: str = "./tweets.db"):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Initialize database with required tables"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create tweets table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS tweets (
                        id TEXT PRIMARY KEY,
                        username TEXT NOT NULL,
                        display_name TEXT,
                        content TEXT NOT NULL,
                        tweet_type TEXT DEFAULT 'tweet',
                        created_at TIMESTAMP NOT NULL,
                        detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        processed_at TIMESTAMP,
                        ai_processed BOOLEAN DEFAULT 0,
                        media_processed BOOLEAN DEFAULT 0,
                        telegram_sent BOOLEAN DEFAULT 0,
                        likes_count INTEGER DEFAULT 0,
                        retweets_count INTEGER DEFAULT 0,
                        replies_count INTEGER DEFAULT 0
                    )
                ''')
                
                # Create media table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS media (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        tweet_id TEXT NOT NULL,
                        media_type TEXT NOT NULL,
                        original_url TEXT NOT NULL,
                        local_path TEXT,
                        file_size INTEGER,
                        width INTEGER,
                        height INTEGER,
                        duration INTEGER,
                        download_status TEXT DEFAULT 'pending',
                        downloaded_at TIMESTAMP,
                        error_message TEXT,
                        FOREIGN KEY (tweet_id) REFERENCES tweets(id)
                    )
                ''')
                
                # Create AI results table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS ai_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        tweet_id TEXT NOT NULL,
                        prompt_used TEXT NOT NULL,
                        result TEXT,
                        model_used TEXT,
                        processing_time REAL,
                        tokens_used INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (tweet_id) REFERENCES tweets(id)
                    )
                ''')
                
                # Create settings table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS settings (
                        key TEXT PRIMARY KEY,
                        value TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Create indexes for performance
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_tweets_username ON tweets(username)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_tweets_created_at ON tweets(created_at)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_media_tweet_id ON media(tweet_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_ai_results_tweet_id ON ai_results(tweet_id)')
                
                # Run migrations
                self._run_migrations(cursor)
                
                conn.commit()
                logger.info("Database initialized successfully")
                
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise
    
    def _run_migrations(self, cursor):
        """Run database migrations for schema updates"""
        try:
            # Migration 1: Add media_processed column if it doesn't exist
            cursor.execute("PRAGMA table_info(tweets)")
            columns = [row[1] for row in cursor.fetchall()]
            
            if 'media_processed' not in columns:
                cursor.execute('ALTER TABLE tweets ADD COLUMN media_processed BOOLEAN DEFAULT 0')
                logger.info("Added media_processed column to tweets table")
            
        except Exception as e:
            logger.error(f"Error running migrations: {e}")
            # Don't raise here, let the app continue
    
    def get_tweets(self, limit: int = 50, offset: int = 0) -> List[Dict]:
        """Get tweets from database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT * FROM tweets 
                    ORDER BY created_at DESC 
                    LIMIT ? OFFSET ?
                ''', (limit, offset))
                
                tweets = [dict(row) for row in cursor.fetchall()]
                return tweets
                
        except Exception as e:
            logger.error(f"Error fetching tweets: {e}")
            return []
    
    def insert_tweet(self, tweet_data: Dict) -> bool:
        """Insert a new tweet into database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                detected_at = datetime.now().isoformat()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO tweets 
                    (id, username, display_name, content, tweet_type, created_at, 
                     likes_count, retweets_count, replies_count, detected_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    tweet_data.get('id'),
                    tweet_data.get('username'),
                    tweet_data.get('display_name'),
                    tweet_data.get('content'),
                    tweet_data.get('tweet_type', 'tweet'),
                    tweet_data.get('created_at'),
                    tweet_data.get('likes_count', 0),
                    tweet_data.get('retweets_count', 0),
                    tweet_data.get('replies_count', 0),
                    detected_at
                ))
                
                conn.commit()
                logger.info(f"Tweet {tweet_data.get('id')} inserted successfully")
                return True
                
        except Exception as e:
            logger.error(f"Error inserting tweet: {e}")
            return False
    
    def get_stats(self) -> Dict:
        """Get database statistics"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get total tweets
                cursor.execute('SELECT COUNT(*) FROM tweets')
                total_tweets = cursor.fetchone()[0]
                
                # Get media files count
                cursor.execute('SELECT COUNT(*) FROM media WHERE download_status = "completed"')
                media_files = cursor.fetchone()[0]
                
                # Get AI processed count
                cursor.execute('SELECT COUNT(*) FROM tweets WHERE ai_processed = 1')
                ai_processed = cursor.fetchone()[0]
                
                # Get telegram sent count
                cursor.execute('SELECT COUNT(*) FROM tweets WHERE telegram_sent = 1')
                telegram_sent = cursor.fetchone()[0]
                
                return {
                    'total_tweets': total_tweets,
                    'media_files': media_files,
                    'ai_processed': ai_processed,
                    'notifications': telegram_sent
                }
                
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {
                'total_tweets': 0,
                'media_files': 0,
                'ai_processed': 0,
                'notifications': 0
            }
    
    def get_unprocessed_tweets(self, limit: int = 50) -> List[Dict]:
        """Get tweets that haven't been processed by AI yet"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT * FROM tweets 
                    WHERE ai_processed = 0 
                    ORDER BY created_at ASC 
                    LIMIT ?
                ''', (limit,))
                
                tweets = [dict(row) for row in cursor.fetchall()]
                return tweets
                
        except Exception as e:
            logger.error(f"Error fetching unprocessed tweets: {e}")
            return []
    
    def store_ai_result(self, result_data: Dict) -> bool:
        """Store AI analysis result"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO ai_results 
                    (tweet_id, prompt_used, result, model_used, processing_time, tokens_used)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    result_data.get('tweet_id'),
                    result_data.get('prompt_type', 'default'),
                    result_data.get('result'),
                    result_data.get('model_used'),
                    result_data.get('processing_time'),
                    result_data.get('tokens_used')
                ))
                
                conn.commit()
                logger.info(f"AI result stored for tweet {result_data.get('tweet_id')}")
                return True
                
        except Exception as e:
            logger.error(f"Error storing AI result: {e}")
            return False
    
    def update_tweet_ai_status(self, tweet_id: str, processed: bool) -> bool:
        """Update tweet's AI processing status"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    UPDATE tweets 
                    SET ai_processed = ?, processed_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (1 if processed else 0, tweet_id))
                
                conn.commit()
                logger.info(f"Tweet {tweet_id} AI status updated to {processed}")
                return True
                
        except Exception as e:
            logger.error(f"Error updating tweet AI status: {e}")
            return False
    
    def get_unprocessed_count(self) -> int:
        """Get count of unprocessed tweets"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('SELECT COUNT(*) FROM tweets WHERE ai_processed = 0')
                count = cursor.fetchone()[0]
                return count
                
        except Exception as e:
            logger.error(f"Error getting unprocessed count: {e}")
            return 0
    
    def get_total_tweets_count(self) -> int:
        """Get total count of tweets"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('SELECT COUNT(*) FROM tweets')
                count = cursor.fetchone()[0]
                return count
                
        except Exception as e:
            logger.error(f"Error getting total tweets count: {e}")
            return 0
    
    def get_tweet_by_id(self, tweet_id: str) -> Optional[Dict]:
        """Get a specific tweet by ID"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('SELECT * FROM tweets WHERE id = ?', (tweet_id,))
                row = cursor.fetchone()
                
                if row:
                    return dict(row)
                return None
                
        except Exception as e:
            logger.error(f"Error getting tweet by ID: {e}")
            return None
    
    def tweet_exists(self, tweet_id: str) -> bool:
        """Check if a tweet exists in the database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('SELECT 1 FROM tweets WHERE id = ? LIMIT 1', (tweet_id,))
                return cursor.fetchone() is not None
                
        except Exception as e:
            logger.error(f"Error checking if tweet exists: {e}")
            return True  # Assume exists to avoid duplicates
    
    def get_failed_ai_tweets(self, limit: int = 50) -> List[Dict]:
        """Get tweets that failed AI processing"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT t.* FROM tweets t
                    LEFT JOIN ai_results ar ON t.id = ar.tweet_id
                    WHERE t.ai_processed = 0 AND ar.id IS NULL
                    ORDER BY t.created_at ASC
                    LIMIT ?
                ''', (limit,))
                
                tweets = [dict(row) for row in cursor.fetchall()]
                return tweets
                
        except Exception as e:
            logger.error(f"Error getting failed AI tweets: {e}")
            return []
    
    def clear_ai_error(self, tweet_id: str) -> bool:
        """Clear AI error status for a tweet"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    UPDATE tweets 
                    SET ai_processed = 0 
                    WHERE id = ?
                ''', (tweet_id,))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error clearing AI error: {e}")
            return False
    
    def get_recent_ai_results(self, limit: int = 10) -> List[Dict]:
        """Get recent AI processing results"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT ar.*, t.username, t.content 
                    FROM ai_results ar
                    JOIN tweets t ON ar.tweet_id = t.id
                    ORDER BY ar.created_at DESC
                    LIMIT ?
                ''', (limit,))
                
                results = [dict(row) for row in cursor.fetchall()]
                return results
                
        except Exception as e:
            logger.error(f"Error getting recent AI results: {e}")
            return []
    
    def update_telegram_status(self, tweet_id: str, sent: bool, sent_at=None, error_message: str = None) -> bool:
        """Update Telegram notification status for a tweet"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Update the telegram_sent status
                cursor.execute('''
                    UPDATE tweets 
                    SET telegram_sent = ?
                    WHERE id = ?
                ''', (1 if sent else 0, tweet_id))
                
                # Log the status change
                logger.info(f"Tweet {tweet_id} Telegram status updated: {'sent' if sent else 'failed'}")
                if error_message:
                    logger.error(f"Telegram error for tweet {tweet_id}: {error_message}")
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error updating Telegram status: {e}")
            return False
    
    def get_tweet_media(self, tweet_id: str, completed_only: bool = False) -> List[Dict]:
        """Get media files associated with a tweet"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                if completed_only:
                    # Only return completed downloads (for API responses)
                    cursor.execute('''
                        SELECT * FROM media 
                        WHERE tweet_id = ? AND download_status = 'completed'
                        ORDER BY id ASC
                    ''', (tweet_id,))
                else:
                    # Return all media (for background worker processing)
                    cursor.execute('''
                        SELECT * FROM media 
                        WHERE tweet_id = ?
                        ORDER BY id ASC
                    ''', (tweet_id,))
                
                media_files = [dict(row) for row in cursor.fetchall()]
                return media_files
                
        except Exception as e:
            logger.error(f"Error getting tweet media for {tweet_id}: {e}")
            return []
    
    def store_media(self, media_data: Dict) -> bool:
        """Store media file information in database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO media 
                    (tweet_id, media_type, original_url, local_path, file_size, 
                     width, height, duration, download_status, downloaded_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    media_data.get('tweet_id'),
                    media_data.get('media_type'),
                    media_data.get('original_url'),
                    media_data.get('local_path'),
                    media_data.get('file_size'),
                    media_data.get('width'),
                    media_data.get('height'),
                    media_data.get('duration'),
                    media_data.get('download_status', 'completed'),
                    media_data.get('downloaded_at', datetime.now())
                ))
                
                conn.commit()
                logger.info(f"Media stored for tweet {media_data.get('tweet_id')}")
                return True
                
        except Exception as e:
            logger.error(f"Error storing media: {e}")
            return False
    
    def update_media_status(self, tweet_id: str, original_url: str, status: str, error_message: str = None) -> bool:
        """Update media download status"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    UPDATE media 
                    SET download_status = ?, error_message = ?, downloaded_at = ?
                    WHERE tweet_id = ? AND original_url = ?
                ''', (status, error_message, datetime.now() if status == 'completed' else None, tweet_id, original_url))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error updating media status: {e}")
            return False
    
    def get_unsent_notifications(self, limit: int = 50, username: str = None, ai_processed_only: bool = True) -> List[Dict]:
        """Get tweets that need Telegram notifications"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Build query conditions
                conditions = ['telegram_sent = 0']
                params = []
                
                # Add AI processing filter
                if ai_processed_only:
                    conditions.append('ai_processed = 1')
                
                # Add username filter
                if username:
                    conditions.append('username = ?')
                    params.append(username)
                
                # Build final query
                query = f'''
                    SELECT * FROM tweets 
                    WHERE {' AND '.join(conditions)}
                    ORDER BY created_at ASC 
                    LIMIT ?
                '''
                params.append(limit)
                
                cursor.execute(query, params)
                tweets = [dict(row) for row in cursor.fetchall()]
                return tweets
                
        except Exception as e:
            logger.error(f"Error getting unsent notifications: {e}")
            return []
    
    def update_tweet_processing_status(self, tweet_id: str, media_downloaded: bool = False, ai_processed: bool = False) -> bool:
        """Update tweet processing status after media download"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Update processing status
                cursor.execute('''
                    UPDATE tweets 
                    SET media_processed = ?, ai_processed = ?
                    WHERE id = ?
                ''', (1 if media_downloaded else 0, 1 if ai_processed else 0, tweet_id))
                
                conn.commit()
                logger.info(f"Updated processing status for tweet {tweet_id}: media_downloaded={media_downloaded}, ai_processed={ai_processed}")
                return True
                
        except Exception as e:
            logger.error(f"Error updating processing status for tweet {tweet_id}: {e}")
            return False

    def get_telegram_stats(self) -> Dict:
        """Get Telegram notification statistics"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Total notifications sent
                cursor.execute('SELECT COUNT(*) FROM tweets WHERE telegram_sent = 1')
                sent_count = cursor.fetchone()[0]
                
                # Pending notifications (AI processed but not sent)
                cursor.execute('SELECT COUNT(*) FROM tweets WHERE ai_processed = 1 AND telegram_sent = 0')
                pending_count = cursor.fetchone()[0]
                
                # Failed notifications (would need a separate error tracking mechanism)
                cursor.execute('SELECT COUNT(*) FROM tweets WHERE telegram_sent = 0')
                total_unsent = cursor.fetchone()[0]
                
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

    def store_tweet(self, tweet_data: Dict) -> str:
        """Store a tweet and return its ID (alias for insert_tweet)"""
        success = self.insert_tweet(tweet_data)
        if success:
            return tweet_data.get('id')
        else:
            raise Exception(f"Failed to store tweet {tweet_data.get('id')}")
    
    def mark_telegram_sent(self, tweet_id: str) -> bool:
        """Mark a tweet as having been sent via Telegram"""
        return self.update_telegram_status(tweet_id, sent=True)
    
    def get_monitored_users(self) -> List[str]:
        """Get list of monitored users from database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT value FROM settings WHERE key = ?', ('monitored_users',))
                result = cursor.fetchone()
                
                if result is not None:
                    # If setting exists (even if empty), parse it
                    if result[0]:
                        users = [user.strip() for user in result[0].split(',') if user.strip()]
                        logger.debug(f"Retrieved monitored users from database: {users}")
                        return users
                    else:
                        # Empty string means explicitly set to no users
                        logger.debug("No monitored users - explicitly set to empty")
                        return []
                else:
                    # Setting doesn't exist - initialize with empty list for first run
                    logger.info("Monitored users setting not found - initializing with empty list")
                    self.set_monitored_users([])
                    return []
                    
        except Exception as e:
            logger.error(f"Error getting monitored users: {e}")
            # On database error, return empty list to be safe
            return []
    
    def set_monitored_users(self, users: List[str]) -> bool:
        """Store list of monitored users in database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # Allow empty list - store as empty string
                users_str = ','.join(users) if users else ''
                cursor.execute('''
                    INSERT OR REPLACE INTO settings (key, value, updated_at)
                    VALUES (?, ?, ?)
                ''', ('monitored_users', users_str, datetime.now()))
                conn.commit()
                if users:
                    logger.info(f"Updated monitored users: {users}")
                else:
                    logger.info("Cleared all monitored users")
                return True
                
        except Exception as e:
            logger.error(f"Error setting monitored users: {e}")
            return False
    
    def add_monitored_user(self, username: str) -> bool:
        """Add a user to the monitored users list"""
        try:
            current_users = self.get_monitored_users()
            if username not in current_users:
                current_users.append(username)
                return self.set_monitored_users(current_users)
            return True
            
        except Exception as e:
            logger.error(f"Error adding monitored user {username}: {e}")
            return False
    
    def remove_monitored_user(self, username: str) -> bool:
        """Remove a user from monitoring"""
        try:
            current_users = self.get_monitored_users()
            if username in current_users:
                current_users.remove(username)
                return self.set_monitored_users(current_users)
            return True  # User not in list, consider it success
            
        except Exception as e:
            logger.error(f"Error removing monitored user {username}: {e}")
            return False

    def get_setting(self, key: str, default_value: str = None) -> str:
        """Get a setting value from the database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
                result = cursor.fetchone()
                return result[0] if result else default_value
        except Exception as e:
            logger.error(f"Error getting setting {key}: {e}")
            return default_value

    def set_setting(self, key: str, value: str) -> bool:
        """Set a setting value in the database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO settings (key, value) 
                    VALUES (?, ?)
                ''', (key, value))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error setting {key}: {e}")
            return False

    def add_normalized_timestamp_column(self):
        """Add a normalized timestamp column for proper chronological ordering"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check if column already exists
                cursor.execute("PRAGMA table_info(tweets)")
                columns = [col[1] for col in cursor.fetchall()]
                
                if 'normalized_timestamp' not in columns:
                    # Add the new column
                    cursor.execute('''
                        ALTER TABLE tweets 
                        ADD COLUMN normalized_timestamp INTEGER
                    ''')
                    logger.info("Added normalized_timestamp column to tweets table")
                
                # Update existing tweets with normalized timestamps
                cursor.execute('''
                    UPDATE tweets 
                    SET normalized_timestamp = CASE
                        WHEN created_at LIKE '%2025%' THEN
                            strftime('%s', substr(created_at, 5, 20) || ' UTC')
                        ELSE
                            strftime('%s', detected_at)
                    END
                    WHERE normalized_timestamp IS NULL
                ''')
                
                updated_count = cursor.rowcount
                conn.commit()
                
                logger.info(f"Updated {updated_count} tweets with normalized timestamps")
                return True
                
        except Exception as e:
            logger.error(f"Error adding normalized timestamp column: {e}")
            return False

    def normalize_tweet_timestamp(self, created_at: str, detected_at: str) -> int:
        """
        Convert tweet timestamps to Unix timestamp for consistent ordering
        
        Args:
            created_at: Tweet creation time (Twitter format)
            detected_at: Detection time (ISO format)
            
        Returns:
            Unix timestamp (integer)
        """
        try:
            from datetime import datetime
            import time
            
            # Try to parse created_at first (more accurate)
            if created_at:
                # Handle Twitter format: "Sun Jun 22 09:28:23 +0000 2025"
                try:
                    dt = datetime.strptime(created_at, '%a %b %d %H:%M:%S %z %Y')
                    return int(dt.timestamp())
                except ValueError:
                    pass
                
                # Handle ISO format
                try:
                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    return int(dt.timestamp())
                except ValueError:
                    pass
            
            # Fallback to detected_at
            if detected_at:
                try:
                    dt = datetime.fromisoformat(detected_at.replace('Z', '+00:00'))
                    return int(dt.timestamp())
                except ValueError:
                    pass
            
            # Last resort: current time
            return int(time.time())
            
        except Exception as e:
            logger.error(f"Error normalizing timestamp: {e}")
            return int(time.time())

    def get_tweets_without_ai_analysis(self, limit: int = 50) -> List[Dict]:
        """
        Get tweets that don't have AI analysis yet
        
        Args:
            limit: Maximum number of tweets to return
            
        Returns:
            List of tweet dictionaries without AI analysis
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, username, content, created_at, detected_at
                    FROM tweets 
                    WHERE (ai_analysis IS NULL OR ai_analysis = '') 
                    AND ai_processed = 0
                    ORDER BY detected_at DESC
                    LIMIT ?
                ''', (limit,))
                
                columns = [desc[0] for desc in cursor.description]
                tweets = []
                
                for row in cursor.fetchall():
                    tweet_dict = dict(zip(columns, row))
                    tweets.append(tweet_dict)
                
                return tweets
                
        except Exception as e:
            logger.error(f"Error getting tweets without AI analysis: {e}")
            return []

    def get_tweets_with_missing_media(self, limit: int = 50) -> List[Dict]:
        """
        Get tweets that have media in database but missing local files
        
        Args:
            limit: Maximum number of tweets to return
            
        Returns:
            List of tweet dictionaries with missing media
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT DISTINCT t.id, t.username, t.content, t.created_at, t.detected_at
                    FROM tweets t
                    INNER JOIN media m ON t.id = m.tweet_id
                    WHERE (m.local_path IS NULL OR m.local_path = '' OR m.download_status != 'completed')
                    ORDER BY t.detected_at DESC
                    LIMIT ?
                ''', (limit,))
                
                columns = [desc[0] for desc in cursor.description]
                tweets = []
                
                for row in cursor.fetchall():
                    tweet_dict = dict(zip(columns, row))
                    tweets.append(tweet_dict)
                
                return tweets
                
        except Exception as e:
            logger.error(f"Error getting tweets with missing media: {e}")
            return []

    def update_tweet_ai_analysis(self, tweet_id: str, ai_analysis: str, sentiment_score: float = None, keywords: List[str] = None) -> bool:
        """
        Update tweet with AI analysis results
        
        Args:
            tweet_id: Tweet ID
            ai_analysis: AI analysis text
            sentiment_score: Sentiment score (optional)
            keywords: List of keywords (optional)
            
        Returns:
            True if update successful
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                keywords_str = ','.join(keywords) if keywords else None
                
                cursor.execute('''
                    UPDATE tweets 
                    SET ai_analysis = ?, 
                        ai_processed = 1,
                        sentiment_score = ?,
                        keywords = ?,
                        ai_processed_at = ?
                    WHERE id = ?
                ''', (ai_analysis, sentiment_score, keywords_str, datetime.now(), tweet_id))
                
                conn.commit()
                
                if cursor.rowcount > 0:
                    logger.debug(f"Updated AI analysis for tweet {tweet_id}")
                    return True
                else:
                    logger.warning(f"No tweet found with ID {tweet_id} for AI analysis update")
                    return False
                
        except Exception as e:
            logger.error(f"Error updating AI analysis for tweet {tweet_id}: {e}")
            return False

    def update_media_local_path(self, media_id: int, local_path: str) -> bool:
        """
        Update media record with local file path
        
        Args:
            media_id: Media record ID
            local_path: Path to downloaded file
            
        Returns:
            True if update successful
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE media 
                    SET local_path = ?, 
                        download_status = 'completed',
                        downloaded_at = ?
                    WHERE id = ?
                ''', (local_path, datetime.now(), media_id))
                
                conn.commit()
                
                if cursor.rowcount > 0:
                    logger.debug(f"Updated local path for media {media_id}")
                    return True
                else:
                    logger.warning(f"No media found with ID {media_id}")
                    return False
                
        except Exception as e:
            logger.error(f"Error updating media local path for media {media_id}: {e}")
            return False

# Initialize database function for external use
def init_db(db_path: str = "./tweets.db"):
    """Initialize database - can be called from command line"""
    db = Database(db_path)
    print(f"Database initialized at {db_path}")
    return db

if __name__ == "__main__":
    # If run directly, initialize database
    init_db() 