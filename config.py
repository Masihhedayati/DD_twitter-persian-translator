# Configuration Management for Twitter Monitor
import os
from datetime import timedelta

def parse_int_env(key, default):
    """Safely parse integer environment variables, handling comments"""
    value = os.environ.get(key, str(default))
    if isinstance(value, str):
        # Strip comments if present (anything after #)
        value = value.split('#')[0].strip()
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

class Config:
    """Base configuration class"""
    
    # Flask Configuration
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    HOST = os.environ.get('HOST', '0.0.0.0')
    PORT = parse_int_env('PORT', 5001)
    DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    # Database Configuration
    DATABASE_PATH = os.environ.get('DATABASE_PATH', './tweets.db')
    
    # Twitter API Configuration (TwitterAPI.io)
    TWITTER_API_KEY = os.environ.get('TWITTER_API_KEY')
    TWITTER_API_BASE_URL = 'https://api.twitterapi.io'
    
    # Twitter API v2 Configuration (for video URL resolution)
    TWITTER_BEARER_TOKEN = os.environ.get('TWITTER_BEARER_TOKEN')
    
    # Webhook Configuration
    TWITTER_WEBHOOK_SECRET = os.environ.get('TWITTER_WEBHOOK_SECRET')
    WEBHOOK_ONLY_MODE = os.environ.get('WEBHOOK_ONLY_MODE', 'false').lower() == 'true'
    HYBRID_MODE = os.environ.get('HYBRID_MODE', 'true').lower() == 'true'  # Initial scrape + webhooks
    HISTORICAL_HOURS = parse_int_env('HISTORICAL_HOURS', 2)  # Hours to look back
    WEBHOOK_URL = os.environ.get('WEBHOOK_URL')  # Your public webhook URL
    
    # OpenAI Configuration
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    OPENAI_MODEL = os.environ.get('OPENAI_MODEL', 'gpt-4o')  # Updated default to GPT-4o
    OPENAI_MAX_TOKENS = parse_int_env('OPENAI_MAX_TOKENS', 1000)
    
    # Telegram Configuration
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
    
    # Notification Configuration
    NOTIFICATION_ENABLED = os.environ.get('NOTIFICATION_ENABLED', 'true').lower() == 'true'
    NOTIFY_ALL_TWEETS = os.environ.get('NOTIFY_ALL_TWEETS', 'false').lower() == 'true'
    NOTIFY_AI_PROCESSED_ONLY = os.environ.get('NOTIFY_AI_PROCESSED_ONLY', 'true').lower() == 'true'
    NOTIFICATION_DELAY = parse_int_env('NOTIFICATION_DELAY', 10)
    
    # Monitoring Configuration
    # MONITORED_USERS is now managed dynamically through the database
    # Environment variable is only used for initial setup if needed
    MONITORED_USERS = os.environ.get("MONITORED_USERS", "").split(",") if os.environ.get("MONITORED_USERS") else []
    
    # Media Storage Configuration
    MEDIA_STORAGE_PATH = os.environ.get('MEDIA_STORAGE_PATH', './media')
    MAX_MEDIA_SIZE = parse_int_env('MAX_MEDIA_SIZE', 104857600)  # 100MB in bytes
    MEDIA_RETENTION_DAYS = parse_int_env('MEDIA_RETENTION_DAYS', 90)
    
    # Processing Configuration
    MAX_CONCURRENT_DOWNLOADS = parse_int_env('MAX_CONCURRENT_DOWNLOADS', 5)
    DOWNLOAD_TIMEOUT = parse_int_env('DOWNLOAD_TIMEOUT', 30)  # seconds
    MAX_RETRY_ATTEMPTS = parse_int_env('MAX_RETRY_ATTEMPTS', 3)
    
    # AI Processing Configuration
    DEFAULT_AI_PROMPT = os.environ.get('DEFAULT_AI_PROMPT', 
        'Persian News Translator & Formatter - Translate English breaking news to Persian for Telegram channels.')
    DEFAULT_AI_MODEL = os.environ.get('DEFAULT_AI_MODEL', 'gpt-4o')  # Updated default to GPT-4o
    DEFAULT_AI_MAX_TOKENS = parse_int_env('DEFAULT_AI_MAX_TOKENS', 1000)
    
    @staticmethod
    def validate_required_config():
        """Validate that all required configuration is present"""
        required_vars = [
            'TWITTER_API_KEY',
            'OPENAI_API_KEY', 
            'TELEGRAM_BOT_TOKEN',
            'TELEGRAM_CHAT_ID'
        ]
        
        missing_vars = []
        for var in required_vars:
            if not os.environ.get(var):
                missing_vars.append(var)
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        return True

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    
class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    SECRET_KEY = os.environ.get('SECRET_KEY')
    
    @staticmethod
    def init_app(app):
        Config.init_app(app)
        
        # Production-specific logging
        import logging
        from logging.handlers import RotatingFileHandler
        
        file_handler = RotatingFileHandler(
            'logs/twitter-monitor.log',
            maxBytes=10240000,  # 10MB
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        
        app.logger.setLevel(logging.INFO)
        app.logger.info('Twitter Monitor startup')

# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
} 