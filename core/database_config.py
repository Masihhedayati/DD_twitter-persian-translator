"""
Database Configuration for Twitter Monitor
Supports both SQLite (development) and PostgreSQL (production)
"""
import os
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class DatabaseConfig:
    """Database configuration management"""
    
    @staticmethod
    def get_database_url():
        """Get database URL from environment or default to SQLite"""
        # Check for PostgreSQL URL (Koyeb/production)
        database_url = os.environ.get('DATABASE_URL')
        if database_url:
            return database_url
            
        # Check for individual PostgreSQL components
        db_host = os.environ.get('POSTGRES_HOST')
        db_name = os.environ.get('POSTGRES_DB', 'twitter_monitor')
        db_user = os.environ.get('POSTGRES_USER', 'postgres')
        db_pass = os.environ.get('POSTGRES_PASSWORD')
        db_port = os.environ.get('POSTGRES_PORT', '5432')
        
        if all([db_host, db_pass]):
            return f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
        
        # Default to SQLite for development
        return "sqlite:///tweets.db"
    
    @staticmethod
    def is_postgresql():
        """Check if using PostgreSQL"""
        url = DatabaseConfig.get_database_url()
        return url.startswith('postgresql://') or url.startswith('postgres://')
    
    @staticmethod
    def get_sqlalchemy_config():
        """Get SQLAlchemy configuration"""
        database_url = DatabaseConfig.get_database_url()
        
        # Fix postgres:// URLs to postgresql:// for SQLAlchemy compatibility
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        
        config = {
            'SQLALCHEMY_DATABASE_URI': database_url,
            'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        }
        
        if DatabaseConfig.is_postgresql():
            # PostgreSQL specific settings
            config.update({
                'SQLALCHEMY_ENGINE_OPTIONS': {
                    'pool_pre_ping': True,
                    'pool_recycle': 300,
                    'connect_args': {
                        'connect_timeout': 10,
                        'application_name': 'twitter_monitor'
                    }
                }
            })
        else:
            # SQLite specific settings
            config.update({
                'SQLALCHEMY_ENGINE_OPTIONS': {
                    'pool_timeout': 20,
                    'pool_recycle': -1,
                    'pool_pre_ping': True,
                    'connect_args': {
                        'timeout': 30,
                        'check_same_thread': False
                    }
                }
            })
        
        return config
    
    @staticmethod
    def get_raw_connection_params():
        """Get raw connection parameters for direct database access"""
        database_url = DatabaseConfig.get_database_url()
        
        if DatabaseConfig.is_postgresql():
            # Parse PostgreSQL URL
            parsed = urlparse(database_url)
            return {
                'engine': 'postgresql',
                'host': parsed.hostname,
                'port': parsed.port or 5432,
                'database': parsed.path.lstrip('/'),
                'user': parsed.username,
                'password': parsed.password,
            }
        else:
            # SQLite
            return {
                'engine': 'sqlite',
                'database': database_url.replace('sqlite:///', './'),
            }
    
    @staticmethod
    def test_connection():
        """Test database connection"""
        try:
            if DatabaseConfig.is_postgresql():
                import psycopg2
                params = DatabaseConfig.get_raw_connection_params()
                conn = psycopg2.connect(
                    host=params['host'],
                    port=params['port'],
                    database=params['database'],
                    user=params['user'],
                    password=params['password'],
                    connect_timeout=10
                )
                conn.close()
                logger.info("PostgreSQL connection test successful")
                return True
            else:
                import sqlite3
                params = DatabaseConfig.get_raw_connection_params()
                conn = sqlite3.connect(params['database'], timeout=10)
                conn.close()
                logger.info("SQLite connection test successful")
                return True
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False 