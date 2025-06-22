"""
Enhanced Configuration Management System
Provides advanced environment-based configuration with validation, dynamic reloading, and settings management.
"""

import os
import json
import yaml
from typing import Dict, Any, Optional, List, Union, Callable
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum
import logging
from datetime import datetime, timedelta
import threading
import time
import hashlib
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class ConfigSource(Enum):
    """Configuration source types"""
    ENVIRONMENT = "environment"
    FILE = "file"
    DATABASE = "database"
    DEFAULT = "default"

class ConfigPriority(Enum):
    """Configuration priority levels"""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4

@dataclass
class ConfigValue:
    """Represents a configuration value with metadata"""
    value: Any
    source: ConfigSource
    priority: ConfigPriority
    last_updated: datetime = field(default_factory=datetime.now)
    validator: Optional[Callable] = None
    description: str = ""
    sensitive: bool = False
    
    def validate(self) -> bool:
        """Validate the configuration value"""
        if self.validator:
            try:
                return self.validator(self.value)
            except Exception:
                return False
        return True

@dataclass 
class TwitterConfig:
    """Twitter API configuration"""
    api_key: str = ""
    base_url: str = "https://api.twitterapi.io"
    timeout: int = 30
    max_retries: int = 3
    rate_limit_per_minute: int = 60
    monitored_users: List[str] = field(default_factory=lambda: ["elonmusk", "naval", "paulg"])
    check_interval: int = 60

@dataclass
class OpenAIConfig:
    """OpenAI API configuration"""
    api_key: str = ""
    model: str = "gpt-3.5-turbo"
    max_tokens: int = 1000
    temperature: float = 0.7
    timeout: int = 30
    max_retries: int = 3
    rate_limit_per_minute: int = 20
    cost_limit_daily: float = 10.0

@dataclass
class TelegramConfig:
    """Telegram bot configuration"""
    bot_token: str = ""
    chat_id: str = ""
    timeout: int = 30
    max_retries: int = 3
    rate_limit_per_minute: int = 30
    notification_template: str = "🐦 New Tweet from @{username}:\n\n{content}\n\n🤖 AI Analysis:\n{ai_result}"

@dataclass
class DatabaseConfig:
    """Database configuration"""
    path: str = "./tweets.db"
    pool_size: int = 10
    timeout: int = 30
    backup_enabled: bool = True
    backup_interval_hours: int = 6
    cleanup_days: int = 90

@dataclass
class MediaConfig:
    """Media storage configuration"""
    storage_path: str = "./media"
    max_file_size_mb: int = 100
    concurrent_downloads: int = 5
    cleanup_days: int = 90
    supported_formats: List[str] = field(default_factory=lambda: ["jpg", "jpeg", "png", "gif", "mp4", "mov", "m4a"])

@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_enabled: bool = True
    file_path: str = "./logs/app.log"
    max_file_size_mb: int = 10
    backup_count: int = 5
    structured_enabled: bool = False

@dataclass
class PerformanceConfig:
    """Performance optimization configuration"""
    cache_enabled: bool = True
    cache_size_mb: int = 100
    async_enabled: bool = True
    thread_pool_size: int = 10
    connection_pool_size: int = 20
    gc_threshold: int = 1000

class ConfigFileHandler(FileSystemEventHandler):
    """Handles configuration file changes for dynamic reloading"""
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
    
    def on_modified(self, event):
        if not event.is_directory and event.src_path in self.config_manager.watched_files:
            self.logger.info(f"Configuration file changed: {event.src_path}")
            self.config_manager._reload_from_file(event.src_path)

class ConfigManager:
    """Enhanced configuration management system"""
    
    def __init__(self, config_file: Optional[str] = None, auto_reload: bool = True):
        self.logger = logging.getLogger(__name__)
        self.config_file = config_file or ".env"
        self.auto_reload = auto_reload
        self.watched_files: List[str] = []
        self.file_checksums: Dict[str, str] = {}
        
        # Configuration sections
        self.twitter = TwitterConfig()
        self.openai = OpenAIConfig()
        self.telegram = TelegramConfig()
        self.database = DatabaseConfig()
        self.media = MediaConfig()
        self.logging = LoggingConfig()
        self.performance = PerformanceConfig()
        
        # Configuration values with metadata
        self.config_values: Dict[str, ConfigValue] = {}
        self.change_listeners: List[Callable] = []
        
        # File watcher for dynamic reloading
        self.observer = None
        self.reload_lock = threading.Lock()
        
        # Validation rules
        self._setup_validators()
        
        # Load initial configuration
        self.load_configuration()
        
        # Start file watcher if auto-reload enabled
        if self.auto_reload:
            self.start_file_watcher()
    
    def _setup_validators(self):
        """Setup configuration validators"""
        self.validators = {
            'twitter.api_key': lambda x: isinstance(x, str) and len(x) > 10,
            'twitter.check_interval': lambda x: isinstance(x, int) and 30 <= x <= 3600,
            'twitter.rate_limit_per_minute': lambda x: isinstance(x, int) and x > 0,
            
            'openai.api_key': lambda x: isinstance(x, str) and (len(x) == 0 or x.startswith('sk-')),
            'openai.temperature': lambda x: isinstance(x, (int, float)) and 0 <= x <= 2,
            'openai.max_tokens': lambda x: isinstance(x, int) and 1 <= x <= 4000,
            'openai.cost_limit_daily': lambda x: isinstance(x, (int, float)) and x >= 0,
            
            'telegram.bot_token': lambda x: isinstance(x, str) and (len(x) == 0 or ':' in x),
            'telegram.chat_id': lambda x: isinstance(x, str),
            
            'database.timeout': lambda x: isinstance(x, int) and x > 0,
            'database.cleanup_days': lambda x: isinstance(x, int) and x >= 0,
            
            'media.max_file_size_mb': lambda x: isinstance(x, int) and x > 0,
            'media.concurrent_downloads': lambda x: isinstance(x, int) and 1 <= x <= 20,
            
            'logging.level': lambda x: x.upper() in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
            'logging.max_file_size_mb': lambda x: isinstance(x, int) and x > 0,
            
            'performance.cache_size_mb': lambda x: isinstance(x, int) and x > 0,
            'performance.thread_pool_size': lambda x: isinstance(x, int) and 1 <= x <= 50,
        }
    
    def load_configuration(self):
        """Load configuration from all sources"""
        self.logger.info("Loading configuration from all sources")
        
        # Apply defaults first
        self._apply_defaults()
        
        # Load from configuration file (lower priority)
        if self.config_file and Path(self.config_file).exists():
            self._load_from_file(self.config_file)
        
        # Load from environment variables (higher priority - should override file)
        self._load_from_environment()
        
        # Validate final configuration
        self._validate_configuration()
        
        self.logger.info("Configuration loaded successfully")
    
    def _load_from_environment(self):
        """Load configuration from environment variables"""
        env_mapping = {
            # Twitter
            'TWITTER_API_KEY': ('twitter.api_key', str),
            'TWITTER_BASE_URL': ('twitter.base_url', str),
            'TWITTER_TIMEOUT': ('twitter.timeout', int),
            'TWITTER_MAX_RETRIES': ('twitter.max_retries', int),
            'TWITTER_RATE_LIMIT': ('twitter.rate_limit_per_minute', int),
            'MONITORED_USERS': ('twitter.monitored_users', lambda x: x.split(',')),
            'CHECK_INTERVAL': ('twitter.check_interval', int),
            
            # OpenAI
            'OPENAI_API_KEY': ('openai.api_key', str),
            'OPENAI_MODEL': ('openai.model', str),
            'OPENAI_MAX_TOKENS': ('openai.max_tokens', int),
            'OPENAI_TEMPERATURE': ('openai.temperature', float),
            'OPENAI_TIMEOUT': ('openai.timeout', int),
            'OPENAI_MAX_RETRIES': ('openai.max_retries', int),
            'OPENAI_RATE_LIMIT': ('openai.rate_limit_per_minute', int),
            'OPENAI_COST_LIMIT_DAILY': ('openai.cost_limit_daily', float),
            
            # Telegram
            'TELEGRAM_BOT_TOKEN': ('telegram.bot_token', str),
            'TELEGRAM_CHAT_ID': ('telegram.chat_id', str),
            'TELEGRAM_TIMEOUT': ('telegram.timeout', int),
            'TELEGRAM_MAX_RETRIES': ('telegram.max_retries', int),
            'TELEGRAM_RATE_LIMIT': ('telegram.rate_limit_per_minute', int),
            
            # Database
            'DATABASE_PATH': ('database.path', str),
            'DATABASE_POOL_SIZE': ('database.pool_size', int),
            'DATABASE_TIMEOUT': ('database.timeout', int),
            'DATABASE_BACKUP_ENABLED': ('database.backup_enabled', lambda x: x.lower() == 'true'),
            'DATABASE_BACKUP_INTERVAL': ('database.backup_interval_hours', int),
            'DATABASE_CLEANUP_DAYS': ('database.cleanup_days', int),
            
            # Media
            'MEDIA_STORAGE_PATH': ('media.storage_path', str),
            'MEDIA_MAX_FILE_SIZE': ('media.max_file_size_mb', int),
            'MEDIA_CONCURRENT_DOWNLOADS': ('media.concurrent_downloads', int),
            'MEDIA_CLEANUP_DAYS': ('media.cleanup_days', int),
            
            # Logging
            'LOG_LEVEL': ('logging.level', str),
            'LOG_FORMAT': ('logging.format', str),
            'LOG_FILE_ENABLED': ('logging.file_enabled', lambda x: x.lower() == 'true'),
            'LOG_FILE_PATH': ('logging.file_path', str),
            'LOG_MAX_FILE_SIZE': ('logging.max_file_size_mb', int),
            'LOG_BACKUP_COUNT': ('logging.backup_count', int),
            'LOG_STRUCTURED_ENABLED': ('logging.structured_enabled', lambda x: x.lower() == 'true'),
            
            # Performance
            'CACHE_ENABLED': ('performance.cache_enabled', lambda x: x.lower() == 'true'),
            'CACHE_SIZE_MB': ('performance.cache_size_mb', int),
            'ASYNC_ENABLED': ('performance.async_enabled', lambda x: x.lower() == 'true'),
            'THREAD_POOL_SIZE': ('performance.thread_pool_size', int),
            'CONNECTION_POOL_SIZE': ('performance.connection_pool_size', int),
            'GC_THRESHOLD': ('performance.gc_threshold', int),
        }
        
        for env_var, (config_path, converter) in env_mapping.items():
            value = os.getenv(env_var)
            if value is not None:
                try:
                    converted_value = converter(value)
                    self._set_config_value(config_path, converted_value, ConfigSource.ENVIRONMENT)
                except (ValueError, TypeError) as e:
                    self.logger.warning(f"Invalid environment variable {env_var}={value}: {e}")
    
    def _load_from_file(self, file_path: str):
        """Load configuration from file (JSON or YAML)"""
        try:
            file_path_obj = Path(file_path)
            
            # Calculate file checksum
            checksum = self._calculate_file_checksum(file_path)
            self.file_checksums[file_path] = checksum
            
            if file_path not in self.watched_files:
                self.watched_files.append(file_path)
            
            if file_path_obj.suffix.lower() in ['.json']:
                with open(file_path, 'r') as f:
                    config_data = json.load(f)
            elif file_path_obj.suffix.lower() in ['.yml', '.yaml']:
                with open(file_path, 'r') as f:
                    config_data = yaml.safe_load(f)
            else:
                # Treat as .env file
                config_data = self._parse_env_file(file_path)
            
            self._apply_config_data(config_data, ConfigSource.FILE)
            self.logger.info(f"Configuration loaded from file: {file_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to load configuration from {file_path}: {e}")
    
    def _parse_env_file(self, file_path: str) -> Dict[str, str]:
        """Parse .env file format"""
        config_data = {}
        try:
            with open(file_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"\'')
                        config_data[key] = value
        except Exception as e:
            self.logger.error(f"Failed to parse .env file {file_path}: {e}")
        
        return config_data
    
    def _apply_config_data(self, config_data: Dict[str, Any], source: ConfigSource):
        """Apply configuration data from dictionary"""
        for key, value in config_data.items():
            if isinstance(value, dict):
                # Handle nested configuration
                for sub_key, sub_value in value.items():
                    config_path = f"{key}.{sub_key}"
                    self._set_config_value(config_path, sub_value, source)
            else:
                # Handle flat configuration (environment style)
                env_mapping = {
                    'TWITTER_API_KEY': 'twitter.api_key',
                    'OPENAI_API_KEY': 'openai.api_key',
                    'TELEGRAM_BOT_TOKEN': 'telegram.bot_token',
                    'TELEGRAM_CHAT_ID': 'telegram.chat_id',
                    'MONITORED_USERS': 'twitter.monitored_users',
                    'CHECK_INTERVAL': 'twitter.check_interval',
                    # Add more mappings as needed
                }
                
                config_path = env_mapping.get(key, key.lower().replace('_', '.'))
                self._set_config_value(config_path, value, source)
    
    def _set_config_value(self, config_path: str, value: Any, source: ConfigSource):
        """Set configuration value with metadata"""
        # Convert string values for known numeric fields  
        if config_path in ['twitter.check_interval', 'twitter.timeout', 'twitter.max_retries', 'twitter.rate_limit_per_minute',
                          'openai.timeout', 'openai.max_retries', 'openai.rate_limit_per_minute', 'openai.max_tokens',
                          'telegram.timeout', 'telegram.max_retries', 'telegram.rate_limit_per_minute',
                          'database.timeout', 'database.pool_size', 'database.backup_interval_hours', 'database.cleanup_days',
                          'media.max_file_size_mb', 'media.concurrent_downloads', 'media.cleanup_days',
                          'logging.max_file_size_mb', 'logging.backup_count',
                          'performance.cache_size_mb', 'performance.thread_pool_size', 'performance.connection_pool_size', 'performance.gc_threshold']:
            try:
                if isinstance(value, str):
                    value = int(value)
            except (ValueError, TypeError):
                pass
        elif config_path in ['openai.temperature', 'openai.cost_limit_daily']:
            try:
                if isinstance(value, str):
                    value = float(value)
            except (ValueError, TypeError):
                pass
        elif config_path.endswith('.monitored_users') and isinstance(value, str):
            value = [user.strip() for user in value.split(',')]
        elif config_path in ['database.backup_enabled', 'logging.file_enabled', 'logging.structured_enabled', 
                           'performance.cache_enabled', 'performance.async_enabled'] and isinstance(value, str):
            value = value.lower() in ('true', '1', 'yes', 'on')
        
        # Store with metadata - only override if higher priority
        existing = self.config_values.get(config_path)
        new_priority = ConfigPriority.HIGH if source == ConfigSource.ENVIRONMENT else ConfigPriority.MEDIUM
        
        if not existing or new_priority.value <= existing.priority.value:
            self.config_values[config_path] = ConfigValue(
                value=value,
                source=source,
                priority=new_priority,
                validator=self.validators.get(config_path)
            )
            
            # Apply to configuration objects
            self._apply_to_config_objects(config_path, value)
    
    def _apply_to_config_objects(self, config_path: str, value: Any):
        """Apply configuration value to appropriate config object"""
        parts = config_path.split('.')
        if len(parts) != 2:
            return
        
        section, key = parts
        config_obj = getattr(self, section, None)
        if config_obj and hasattr(config_obj, key):
            setattr(config_obj, key, value)
    
    def _apply_defaults(self):
        """Apply default values for missing configuration"""
        defaults = {
            'twitter.api_key': '',
            'twitter.base_url': 'https://api.twitterapi.io',
            'twitter.timeout': 30,
            'twitter.max_retries': 3,
            'twitter.rate_limit_per_minute': 60,
            'twitter.monitored_users': ['elonmusk', 'naval', 'paulg'],
            'twitter.check_interval': 60,
            
            'openai.api_key': '',
            'openai.model': 'gpt-3.5-turbo',
            'openai.max_tokens': 1000,
            'openai.temperature': 0.7,
            'openai.timeout': 30,
            'openai.max_retries': 3,
            'openai.rate_limit_per_minute': 20,
            'openai.cost_limit_daily': 10.0,
            
            'telegram.bot_token': '',
            'telegram.chat_id': '',
            'telegram.timeout': 30,
            'telegram.max_retries': 3,
            'telegram.rate_limit_per_minute': 30,
            
            'database.path': './tweets.db',
            'database.pool_size': 10,
            'database.timeout': 30,
            'database.backup_enabled': True,
            'database.backup_interval_hours': 6,
            'database.cleanup_days': 90,
            
            'media.storage_path': './media',
            'media.max_file_size_mb': 100,
            'media.concurrent_downloads': 5,
            'media.cleanup_days': 90,
            
            'logging.level': 'INFO',
            'logging.file_enabled': True,
            'logging.file_path': './logs/app.log',
            'logging.max_file_size_mb': 10,
            'logging.backup_count': 5,
            'logging.structured_enabled': False,
            
            'performance.cache_enabled': True,
            'performance.cache_size_mb': 100,
            'performance.async_enabled': True,
            'performance.thread_pool_size': 10,
            'performance.connection_pool_size': 20,
            'performance.gc_threshold': 1000,
        }
        
        for config_path, default_value in defaults.items():
            if config_path not in self.config_values:
                self._set_config_value(config_path, default_value, ConfigSource.DEFAULT)
    
    def _validate_configuration(self):
        """Validate all configuration values"""
        validation_errors = []
        
        for config_path, config_val in self.config_values.items():
            if not config_val.validate():
                validation_errors.append(f"Invalid value for {config_path}: {config_val.value}")
        
        if validation_errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(validation_errors)
            self.logger.error(error_msg)
            # Don't raise exception, just log errors
        else:
            self.logger.info("Configuration validation passed")
    
    def get(self, config_path: str, default: Any = None) -> Any:
        """Get configuration value"""
        config_val = self.config_values.get(config_path)
        if config_val:
            return config_val.value
        return default
    
    def set(self, config_path: str, value: Any, source: ConfigSource = ConfigSource.ENVIRONMENT) -> bool:
        """Set configuration value with validation"""
        try:
            # Create temporary config value for validation
            temp_config_val = ConfigValue(
                value=value,
                source=source,
                priority=ConfigPriority.HIGH,
                validator=self.validators.get(config_path)
            )
            
            if not temp_config_val.validate():
                self.logger.error(f"Validation failed for {config_path}={value}")
                return False
            
            # Store the value
            self._set_config_value(config_path, value, source)
            
            # Notify listeners
            self._notify_change_listeners(config_path, value)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to set configuration {config_path}={value}: {e}")
            return False
    
    def add_change_listener(self, listener: Callable[[str, Any], None]):
        """Add configuration change listener"""
        self.change_listeners.append(listener)
    
    def _notify_change_listeners(self, config_path: str, value: Any):
        """Notify all change listeners"""
        for listener in self.change_listeners:
            try:
                listener(config_path, value)
            except Exception as e:
                self.logger.error(f"Error in configuration change listener: {e}")
    
    def start_file_watcher(self):
        """Start file system watcher for configuration files"""
        if self.observer is None and self.watched_files:
            try:
                self.observer = Observer()
                handler = ConfigFileHandler(self)
                
                # Watch all directories containing config files
                watched_dirs = set()
                for file_path in self.watched_files:
                    dir_path = str(Path(file_path).parent)
                    if dir_path not in watched_dirs:
                        self.observer.schedule(handler, dir_path, recursive=False)
                        watched_dirs.add(dir_path)
                
                self.observer.start()
                self.logger.info("Configuration file watcher started")
                
            except Exception as e:
                self.logger.error(f"Failed to start file watcher: {e}")
    
    def stop_file_watcher(self):
        """Stop file system watcher"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None
            self.logger.info("Configuration file watcher stopped")
    
    def _reload_from_file(self, file_path: str):
        """Reload configuration from specific file"""
        with self.reload_lock:
            # Check if file actually changed
            new_checksum = self._calculate_file_checksum(file_path)
            old_checksum = self.file_checksums.get(file_path)
            
            if new_checksum != old_checksum:
                self.logger.info(f"Reloading configuration from {file_path}")
                self._load_from_file(file_path)
                self._notify_change_listeners("config.reloaded", file_path)
    
    def _calculate_file_checksum(self, file_path: str) -> str:
        """Calculate MD5 checksum of file"""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return ""
    
    def reload(self):
        """Manually reload configuration"""
        self.logger.info("Manually reloading configuration")
        self.load_configuration()
        self._notify_change_listeners("config.reloaded", "manual")
    
    def get_configuration_summary(self) -> Dict[str, Any]:
        """Get summary of current configuration"""
        summary = {
            'sources': {},
            'validation_status': 'valid',
            'last_reload': datetime.now().isoformat(),
            'watched_files': self.watched_files,
            'sections': {}
        }
        
        # Count sources
        for config_val in self.config_values.values():
            source = config_val.source.value
            summary['sources'][source] = summary['sources'].get(source, 0) + 1
        
        # Check validation status
        for config_val in self.config_values.values():
            if not config_val.validate():
                summary['validation_status'] = 'invalid'
                break
        
        # Add section summaries
        for section in ['twitter', 'openai', 'telegram', 'database', 'media', 'logging', 'performance']:
            config_obj = getattr(self, section)
            summary['sections'][section] = {
                key: getattr(config_obj, key) for key in config_obj.__dict__.keys()
                if not key.startswith('_')
            }
        
        return summary
    
    def export_configuration(self, file_path: str, format: str = 'json'):
        """Export current configuration to file"""
        config_data = {}
        
        for config_path, config_val in self.config_values.items():
            parts = config_path.split('.')
            if len(parts) == 2:
                section, key = parts
                if section not in config_data:
                    config_data[section] = {}
                
                # Don't export sensitive values
                if config_val.sensitive and config_val.value:
                    config_data[section][key] = "***HIDDEN***"
                else:
                    config_data[section][key] = config_val.value
        
        try:
            with open(file_path, 'w') as f:
                if format.lower() == 'json':
                    json.dump(config_data, f, indent=2, default=str)
                elif format.lower() in ['yml', 'yaml']:
                    yaml.dump(config_data, f, default_flow_style=False)
                else:
                    # Export as .env format
                    for section, values in config_data.items():
                        for key, value in values.items():
                            env_key = f"{section.upper()}_{key.upper()}"
                            f.write(f"{env_key}={value}\n")
            
            self.logger.info(f"Configuration exported to {file_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to export configuration: {e}")
    
    def __del__(self):
        """Cleanup when object is destroyed"""
        self.stop_file_watcher()


# Global configuration manager instance
_config_manager: Optional[ConfigManager] = None

def get_config_manager(config_file: Optional[str] = None, auto_reload: bool = True) -> ConfigManager:
    """Get global configuration manager instance"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager(config_file, auto_reload)
    return _config_manager

def get_config() -> ConfigManager:
    """Get configuration manager (shorthand)"""
    return get_config_manager()

# Convenience functions
def get_twitter_config() -> TwitterConfig:
    """Get Twitter configuration"""
    return get_config_manager().twitter

def get_openai_config() -> OpenAIConfig:
    """Get OpenAI configuration"""
    return get_config_manager().openai

def get_telegram_config() -> TelegramConfig:
    """Get Telegram configuration"""
    return get_config_manager().telegram

def get_database_config() -> DatabaseConfig:
    """Get database configuration"""
    return get_config_manager().database

def get_media_config() -> MediaConfig:
    """Get media configuration"""
    return get_config_manager().media

def get_logging_config() -> LoggingConfig:
    """Get logging configuration"""
    return get_config_manager().logging

def get_performance_config() -> PerformanceConfig:
    """Get performance configuration"""
    return get_config_manager().performance 