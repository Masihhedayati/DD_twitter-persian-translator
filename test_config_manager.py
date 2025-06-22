"""
Test suite for Enhanced Configuration Management System
Tests configuration loading, validation, dynamic reloading, and settings management.
"""

import pytest
import os
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime

from core.config_manager import (
    ConfigManager, ConfigSource, ConfigPriority, ConfigValue,
    TwitterConfig, OpenAIConfig, TelegramConfig,
    get_config_manager, get_twitter_config, get_openai_config, get_telegram_config
)

class TestConfigValue:
    """Test ConfigValue class"""
    
    def test_config_value_creation(self):
        """Test creating a config value"""
        validator = lambda x: isinstance(x, str) and len(x) > 0
        config_val = ConfigValue(
            value="test_value",
            source=ConfigSource.ENVIRONMENT,
            priority=ConfigPriority.HIGH,
            validator=validator,
            description="Test configuration value"
        )
        
        assert config_val.value == "test_value"
        assert config_val.source == ConfigSource.ENVIRONMENT
        assert config_val.priority == ConfigPriority.HIGH
        assert config_val.validator == validator
        assert config_val.description == "Test configuration value"
        assert config_val.sensitive == False
        assert isinstance(config_val.last_updated, datetime)
    
    def test_config_value_validation_pass(self):
        """Test config value validation success"""
        validator = lambda x: isinstance(x, int) and x > 0
        config_val = ConfigValue(
            value=42,
            source=ConfigSource.ENVIRONMENT,
            priority=ConfigPriority.HIGH,
            validator=validator
        )
        
        assert config_val.validate() == True
    
    def test_config_value_validation_fail(self):
        """Test config value validation failure"""
        validator = lambda x: isinstance(x, int) and x > 0
        config_val = ConfigValue(
            value=-5,
            source=ConfigSource.ENVIRONMENT,
            priority=ConfigPriority.HIGH,
            validator=validator
        )
        
        assert config_val.validate() == False
    
    def test_config_value_no_validator(self):
        """Test config value without validator"""
        config_val = ConfigValue(
            value="any_value",
            source=ConfigSource.ENVIRONMENT,
            priority=ConfigPriority.HIGH
        )
        
        assert config_val.validate() == True


class TestConfigDataClasses:
    """Test configuration data classes"""
    
    def test_twitter_config_defaults(self):
        """Test TwitterConfig default values"""
        config = TwitterConfig()
        
        assert config.api_key == ""
        assert config.base_url == "https://api.twitterapi.io"
        assert config.timeout == 30
        assert config.max_retries == 3
        assert config.rate_limit_per_minute == 60
        assert config.monitored_users == ["elonmusk", "naval", "paulg"]
        assert config.check_interval == 60
    
    def test_openai_config_defaults(self):
        """Test OpenAIConfig default values"""
        config = OpenAIConfig()
        
        assert config.api_key == ""
        assert config.model == "gpt-3.5-turbo"
        assert config.max_tokens == 1000
        assert config.temperature == 0.7
        assert config.timeout == 30
        assert config.max_retries == 3
        assert config.rate_limit_per_minute == 20
        assert config.cost_limit_daily == 10.0
    
    def test_telegram_config_defaults(self):
        """Test TelegramConfig default values"""
        config = TelegramConfig()
        
        assert config.bot_token == ""
        assert config.chat_id == ""
        assert config.timeout == 30
        assert config.max_retries == 3
        assert config.rate_limit_per_minute == 30
        assert "🐦 New Tweet from @{username}" in config.notification_template


class TestConfigManager:
    """Test ConfigManager class"""
    
    def setup_method(self):
        """Setup for each test"""
        # Clear global config manager
        import core.config_manager
        core.config_manager._config_manager = None
    
    def test_config_manager_initialization(self):
        """Test ConfigManager initialization"""
        config_manager = ConfigManager(auto_reload=False)
        
        assert isinstance(config_manager.twitter, TwitterConfig)
        assert isinstance(config_manager.openai, OpenAIConfig)
        assert isinstance(config_manager.telegram, TelegramConfig)
        assert len(config_manager.config_values) > 0
        assert len(config_manager.validators) > 0
    
    def test_load_from_environment(self):
        """Test loading configuration from environment variables"""
        with patch.dict(os.environ, {
            'TWITTER_API_KEY': 'test_twitter_key_12345',
            'OPENAI_API_KEY': 'sk-test_openai_key',
            'TELEGRAM_BOT_TOKEN': '123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11',
            'TELEGRAM_CHAT_ID': '-123456789',
            'MONITORED_USERS': 'user1,user2,user3',
            'CHECK_INTERVAL': '120'
        }):
            config_manager = ConfigManager(auto_reload=False)
            
            assert config_manager.twitter.api_key == 'test_twitter_key_12345'
            assert config_manager.openai.api_key == 'sk-test_openai_key'
            assert config_manager.telegram.bot_token == '123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11'
            assert config_manager.telegram.chat_id == '-123456789'
            assert config_manager.twitter.monitored_users == ['user1', 'user2', 'user3']
            assert config_manager.twitter.check_interval == 120
    
    def test_load_from_env_file(self):
        """Test loading configuration from .env file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("""
TWITTER_API_KEY=test_file_twitter_key
OPENAI_API_KEY=sk-test_file_openai_key
TELEGRAM_BOT_TOKEN=123456:FILE-TOKEN
TELEGRAM_CHAT_ID=-987654321
MONITORED_USERS=file_user1,file_user2
CHECK_INTERVAL=90
            """.strip())
            env_file = f.name
        
        try:
            config_manager = ConfigManager(config_file=env_file, auto_reload=False)
            
            assert config_manager.twitter.api_key == 'test_file_twitter_key'
            assert config_manager.openai.api_key == 'sk-test_file_openai_key'
            assert config_manager.telegram.bot_token == '123456:FILE-TOKEN'
            assert config_manager.telegram.chat_id == '-987654321'
            assert config_manager.twitter.monitored_users == ['file_user1', 'file_user2']
            assert config_manager.twitter.check_interval == 90
        finally:
            Path(env_file).unlink()
    
    def test_environment_overrides_file(self):
        """Test that environment variables override file configuration"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("TWITTER_API_KEY=file_key\nCHECK_INTERVAL=90")
            env_file = f.name
        
        try:
            with patch.dict(os.environ, {
                'TWITTER_API_KEY': 'env_key_override',
                'CHECK_INTERVAL': '180'
            }):
                config_manager = ConfigManager(config_file=env_file, auto_reload=False)
                
                # Environment should override file
                assert config_manager.twitter.api_key == 'env_key_override'
                assert config_manager.twitter.check_interval == 180
        finally:
            Path(env_file).unlink()
    
    def test_config_validation(self):
        """Test configuration validation"""
        config_manager = ConfigManager(auto_reload=False)
        
        # Test valid values
        assert config_manager.set('twitter.check_interval', 120) == True
        assert config_manager.twitter.check_interval == 120
        
        # Test invalid values
        assert config_manager.set('twitter.check_interval', 10) == False  # Too low
        assert config_manager.set('twitter.check_interval', 'invalid') == False  # Wrong type
        
        # OpenAI validation
        assert config_manager.set('openai.api_key', 'sk-valid_key') == True
        assert config_manager.set('openai.api_key', 'invalid_key') == False
        
        # Temperature validation
        assert config_manager.set('openai.temperature', 0.5) == True
        assert config_manager.set('openai.temperature', 3.0) == False  # Too high
    
    def test_get_config_value(self):
        """Test getting configuration values"""
        config_manager = ConfigManager(auto_reload=False)
        
        # Test existing value
        value = config_manager.get('twitter.check_interval')
        assert value == 60  # Default
        
        # Test non-existing value with default
        value = config_manager.get('non.existing.key', 'default_value')
        assert value == 'default_value'
        
        # Test non-existing value without default
        value = config_manager.get('non.existing.key')
        assert value is None
    
    def test_change_listeners(self):
        """Test configuration change listeners"""
        config_manager = ConfigManager(auto_reload=False)
        
        # Track changes
        changes = []
        def change_listener(config_path, value):
            changes.append((config_path, value))
        
        config_manager.add_change_listener(change_listener)
        
        # Make a change
        config_manager.set('twitter.check_interval', 300)
        
        # Verify listener was called
        assert len(changes) == 1
        assert changes[0] == ('twitter.check_interval', 300)
    
    def test_configuration_summary(self):
        """Test getting configuration summary"""
        with patch.dict(os.environ, {
            'TWITTER_API_KEY': 'test_key',
            'OPENAI_API_KEY': 'sk-test'
        }):
            config_manager = ConfigManager(auto_reload=False)
            
            summary = config_manager.get_configuration_summary()
            
            assert 'sources' in summary
            assert 'validation_status' in summary
            assert 'last_reload' in summary
            assert 'sections' in summary
            
            # Check sources
            assert summary['sources']['environment'] > 0
            assert summary['sources']['default'] > 0
            
            # Check sections
            assert 'twitter' in summary['sections']
            assert 'openai' in summary['sections']
            assert 'telegram' in summary['sections']
            
            # Check section values
            assert summary['sections']['twitter']['api_key'] == 'test_key'
            assert summary['sections']['openai']['api_key'] == 'sk-test'


class TestGlobalFunctions:
    """Test global convenience functions"""
    
    def setup_method(self):
        """Setup for each test"""
        # Clear global config manager
        import core.config_manager
        core.config_manager._config_manager = None
    
    def test_get_config_manager(self):
        """Test get_config_manager function"""
        manager1 = get_config_manager()
        manager2 = get_config_manager()
        
        # Should return the same instance (singleton)
        assert manager1 is manager2
    
    def test_convenience_functions(self):
        """Test convenience functions for getting specific configs"""
        twitter_config = get_twitter_config()
        openai_config = get_openai_config()
        telegram_config = get_telegram_config()
        
        assert isinstance(twitter_config, TwitterConfig)
        assert isinstance(openai_config, OpenAIConfig)
        assert isinstance(telegram_config, TelegramConfig)


class TestConfigValidators:
    """Test configuration validators"""
    
    def setup_method(self):
        """Setup for each test"""
        import core.config_manager
        core.config_manager._config_manager = None
    
    def test_twitter_validators(self):
        """Test Twitter configuration validators"""
        config_manager = ConfigManager(auto_reload=False)
        
        # API key validation
        assert config_manager.validators['twitter.api_key']('valid_key_longer_than_10') == True
        assert config_manager.validators['twitter.api_key']('short') == False
        assert config_manager.validators['twitter.api_key'](123) == False
        
        # Check interval validation
        assert config_manager.validators['twitter.check_interval'](60) == True
        assert config_manager.validators['twitter.check_interval'](30) == True
        assert config_manager.validators['twitter.check_interval'](3600) == True
        assert config_manager.validators['twitter.check_interval'](29) == False  # Too low
        assert config_manager.validators['twitter.check_interval'](3601) == False  # Too high
        assert config_manager.validators['twitter.check_interval']('60') == False  # Wrong type
    
    def test_openai_validators(self):
        """Test OpenAI configuration validators"""
        config_manager = ConfigManager(auto_reload=False)
        
        # API key validation
        assert config_manager.validators['openai.api_key']('sk-valid_key') == True
        assert config_manager.validators['openai.api_key']('') == True  # Empty allowed
        assert config_manager.validators['openai.api_key']('invalid_key') == False
        assert config_manager.validators['openai.api_key'](123) == False
        
        # Temperature validation
        assert config_manager.validators['openai.temperature'](0.0) == True
        assert config_manager.validators['openai.temperature'](1.0) == True
        assert config_manager.validators['openai.temperature'](2.0) == True
        assert config_manager.validators['openai.temperature'](-0.1) == False  # Too low
        assert config_manager.validators['openai.temperature'](2.1) == False  # Too high
        
        # Max tokens validation
        assert config_manager.validators['openai.max_tokens'](1) == True
        assert config_manager.validators['openai.max_tokens'](1000) == True
        assert config_manager.validators['openai.max_tokens'](4000) == True
        assert config_manager.validators['openai.max_tokens'](0) == False  # Too low
        assert config_manager.validators['openai.max_tokens'](4001) == False  # Too high
    
    def test_telegram_validators(self):
        """Test Telegram configuration validators"""
        config_manager = ConfigManager(auto_reload=False)
        
        # Bot token validation
        assert config_manager.validators['telegram.bot_token']('123456:ABC-DEF') == True
        assert config_manager.validators['telegram.bot_token']('') == True  # Empty allowed
        assert config_manager.validators['telegram.bot_token']('invalid_token') == False
        assert config_manager.validators['telegram.bot_token'](123) == False
        
        # Chat ID validation (any string is valid)
        assert config_manager.validators['telegram.chat_id']('-123456789') == True
        assert config_manager.validators['telegram.chat_id']('') == True
        assert config_manager.validators['telegram.chat_id']('any_string') == True


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"]) 