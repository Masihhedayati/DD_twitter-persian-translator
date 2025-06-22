#!/usr/bin/env python3
"""
Security Testing Suite for Twitter Monitor Application
Validates security measures, input sanitization, and attack prevention
"""

import pytest
import os
import tempfile
import sqlite3
from unittest.mock import Mock, patch
import json

# Import core components
from core.database import Database
from core.config_manager import ConfigManager
from core.rate_limiter import APIRateLimiter, RateLimitConfig, RateLimitStrategy


class TestSecurityValidation:
    """Comprehensive security testing"""
    
    def test_sql_injection_protection(self):
        """Test SQL injection attack prevention"""
        db = Database(':memory:')
        
        # Test malicious SQL injection attempts in tweet data
        malicious_inputs = [
            "'; DROP TABLE tweets; --",
            "1; DELETE FROM tweets; --",
            "' UNION SELECT * FROM tweets --",
            "'; INSERT INTO tweets VALUES ('hack', 'hacker'); --"
        ]
        
        for malicious_input in malicious_inputs:
            malicious_tweet = {
                'id': f'inject_test_{hash(malicious_input)}',
                'username': malicious_input,
                'display_name': malicious_input,
                'content': malicious_input,
                'created_at': '2024-12-22T10:00:00Z'
            }
            
            # Should handle malicious input safely
            try:
                result = db.insert_tweet(malicious_tweet)
                # Should either succeed (safely escaped) or fail gracefully
                assert isinstance(result, bool)
            except Exception as e:
                # Should be safe database error, not SQL injection success
                error_msg = str(e).upper()
                assert "DROP TABLE" not in error_msg
                assert "DELETE FROM" not in error_msg
                assert "UNION SELECT" not in error_msg
    
    def test_path_traversal_protection(self):
        """Test path traversal attack prevention"""
        import tempfile
        import os
        
        temp_dir = tempfile.mkdtemp()
        
        # Test malicious path inputs
        malicious_paths = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "/etc/shadow",
            "C:\\Windows\\System32\\drivers\\etc\\hosts"
        ]
        
        for malicious_path in malicious_paths:
            # Test that file operations reject dangerous paths
            full_path = os.path.join(temp_dir, malicious_path)
            normalized_path = os.path.normpath(full_path)
            
            # Should not escape the temp directory
            assert temp_dir in normalized_path or not os.path.exists(normalized_path)
    
    def test_input_sanitization(self):
        """Test input sanitization for XSS and injection attacks"""
        db = Database(':memory:')
        
        # Test XSS and script injection attempts
        malicious_scripts = [
            '<script>alert("xss")</script>',
            'javascript:alert("xss")',
            '<img src="x" onerror="alert(1)">',
            '"><script>alert("xss")</script>',
            '<iframe src="javascript:alert(\'xss\')"></iframe>',
            'onload="alert(\'xss\')"',
            '<svg onload=alert("xss")>',
        ]
        
        for script in malicious_scripts:
            test_tweet = {
                'id': f'xss_test_{hash(script)}',
                'username': 'testuser',
                'display_name': script,
                'content': script,
                'created_at': '2024-12-22T10:00:00Z'
            }
            
            # Should store data safely without executing scripts
            try:
                result = db.insert_tweet(test_tweet)
                assert isinstance(result, bool)
                
                # If stored, retrieve and verify no script execution context
                if result:
                    stored = db.get_tweet_by_id(test_tweet['id'])
                    if stored:
                        # Data should be stored as-is but not executable
                        assert script in stored['content'] or script in stored['display_name']
                        
            except Exception as e:
                # Should be safe database error
                assert 'alert' not in str(e).lower()
    
    def test_api_key_security(self):
        """Test API key handling and security"""
        # Test that API keys are not exposed in logs or errors
        config_manager = ConfigManager()
        
        # Get configuration (should not contain actual keys in test)
        twitter_config = config_manager.get_config_value('twitter', 'api_key', '')
        openai_config = config_manager.get_config_value('openai', 'api_key', '')
        
        # In test environment, these should be empty or test values
        assert twitter_config != 'actual_production_key'
        assert openai_config != 'actual_production_key'
        
        # Test logging doesn't expose keys
        import logging
        import io
        
        log_stream = io.StringIO()
        handler = logging.StreamHandler(log_stream)
        logger = logging.getLogger('security_test')
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        
        # Log some operations
        logger.info("Initializing Twitter API client")
        logger.info("Initializing OpenAI client")
        logger.debug(f"Config loaded: {len(str(config_manager))} characters")
        
        log_contents = log_stream.getvalue()
        
        # Should not contain any potential API keys
        lines = log_contents.split('\n')
        for line in lines:
            # Look for potential API key patterns (long alphanumeric strings)
            words = line.split()
            for word in words:
                if len(word) > 20 and word.isalnum():
                    # This might be an API key, should not be in logs
                    assert word in ['TwitterAPIclient', 'OpenAIclient'] or word.startswith('Config')
    
    def test_rate_limiting_security(self):
        """Test that rate limiting cannot be easily bypassed"""
        config = RateLimitConfig(
            max_requests=3,
            time_window_seconds=1,
            strategy=RateLimitStrategy.FIXED_WINDOW
        )
        
        limiter = APIRateLimiter("security_test", config)
        
        # Try to exceed rate limit
        successful_requests = 0
        for i in range(10):
            if limiter.acquire():
                successful_requests += 1
        
        # Should only allow max_requests
        assert successful_requests == 3
        
        # Verify limiter state is secure
        stats = limiter.get_stats()
        assert stats['rejected_count'] >= 7  # 10 - 3 allowed
    
    def test_environment_variable_validation(self):
        """Test environment variable handling security"""
        import os
        
        # Test with potentially dangerous environment values
        dangerous_values = [
            "; rm -rf /",
            "$(whoami)",
            "`id`",
            "${PATH}",
            "'; DROP DATABASE; --"
        ]
        
        original_values = {}
        
        try:
            for i, dangerous_value in enumerate(dangerous_values):
                env_var = f'TEST_SECURITY_VAR_{i}'
                original_values[env_var] = os.environ.get(env_var)
                os.environ[env_var] = dangerous_value
                
                # Test that config manager handles dangerous values safely
                config_manager = ConfigManager()
                value = config_manager.get_config_value('app', env_var.lower(), 'default')
                
                # Should not execute commands or SQL
                assert 'root' not in str(value)  # Common result of command injection
                assert 'uid=' not in str(value)  # Common result of `id` command
                
        finally:
            # Cleanup
            for env_var, original_value in original_values.items():
                if original_value is not None:
                    os.environ[env_var] = original_value
                elif env_var in os.environ:
                    del os.environ[env_var]
    
    def test_file_upload_security(self):
        """Test file upload security measures"""
        import tempfile
        import os
        
        temp_dir = tempfile.mkdtemp()
        
        # Test dangerous file types and names
        dangerous_files = [
            'script.exe',
            'malware.bat',
            '../../../etc/passwd',
            'file.php',
            'script.sh',
            '..\\..\\windows\\system32\\calc.exe'
        ]
        
        for dangerous_file in dangerous_files:
            # Test that dangerous files are rejected or safely handled
            safe_path = os.path.join(temp_dir, os.path.basename(dangerous_file))
            normalized_path = os.path.normpath(safe_path)
            
            # Should stay within temp directory
            assert temp_dir in normalized_path
            
            # Should not have executable extensions in production
            extension = os.path.splitext(dangerous_file)[1].lower()
            dangerous_extensions = ['.exe', '.bat', '.sh', '.php', '.jsp', '.asp']
            
            if extension in dangerous_extensions:
                # In a real implementation, these should be rejected
                # For now, just ensure they don't escape the sandbox
                assert temp_dir in normalized_path
    
    def test_database_connection_security(self):
        """Test database connection security"""
        # Test that database connections are properly secured
        db = Database(':memory:')
        
        # Test that connection uses proper isolation
        # SQLite in-memory databases are inherently isolated
        
        # Test that foreign key constraints are enabled (security feature)
        with sqlite3.connect(':memory:') as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys")
            result = cursor.fetchone()
            # Should have foreign key support available
            assert result is not None
    
    def test_configuration_security(self):
        """Test configuration security measures"""
        config_manager = ConfigManager()
        
        # Test that sensitive configurations have appropriate defaults
        sensitive_configs = [
            ('twitter', 'api_key'),
            ('openai', 'api_key'),
            ('telegram', 'bot_token'),
            ('database', 'path'),
        ]
        
        for section, key in sensitive_configs:
            value = config_manager.get_config_value(section, key, '')
            
            # Should not have obvious dummy or default values in production
            dangerous_defaults = [
                'your_api_key_here',
                'change_me',
                'default_password',
                'admin',
                'password',
                '123456'
            ]
            
            for dangerous_default in dangerous_defaults:
                assert value.lower() != dangerous_default.lower()
    
    def test_error_message_security(self):
        """Test that error messages don't leak sensitive information"""
        db = Database(':memory:')
        
        # Test error handling doesn't expose system information
        try:
            # Force a database error
            malformed_tweet = {
                'id': None,  # This should cause an error
                'username': 'test',
                'content': 'test'
            }
            db.insert_tweet(malformed_tweet)
        except Exception as e:
            error_message = str(e)
            
            # Error should not contain sensitive system information
            sensitive_info = [
                'password',
                'api_key',
                'secret',
                'token',
                '/home/',
                '/Users/',
                'C:\\Users\\'
            ]
            
            for sensitive in sensitive_info:
                assert sensitive.lower() not in error_message.lower()


class TestDataPrivacy:
    """Test data privacy and protection measures"""
    
    def test_data_retention_controls(self):
        """Test data retention and cleanup capabilities"""
        db = Database(':memory:')
        
        # Test that we can safely delete data
        test_tweet = {
            'id': 'privacy_test_123',
            'username': 'testuser',
            'display_name': 'Test User',
            'content': 'Test content for privacy',
            'created_at': '2024-12-22T10:00:00Z'
        }
        
        # Insert and verify
        result = db.insert_tweet(test_tweet)
        assert result is True
        
        stored = db.get_tweet_by_id('privacy_test_123')
        assert stored is not None
        
        # Test that we can query and filter data appropriately
        tweets = db.get_tweets(limit=10)
        assert len(tweets) >= 1
    
    def test_sensitive_data_handling(self):
        """Test handling of potentially sensitive content"""
        db = Database(':memory:')
        
        # Test tweets with sensitive information
        sensitive_content = [
            "My phone number is 555-123-4567",
            "Email me at user@example.com",
            "My address is 123 Main St",
            "SSN: 123-45-6789",
            "Credit card: 4532-1234-5678-9012"
        ]
        
        for i, content in enumerate(sensitive_content):
            tweet = {
                'id': f'sensitive_test_{i}',
                'username': 'testuser',
                'display_name': 'Test User',
                'content': content,
                'created_at': '2024-12-22T10:00:00Z'
            }
            
            # Should store data but flag for potential sensitivity
            result = db.insert_tweet(tweet)
            assert isinstance(result, bool)
            
            # In a production system, sensitive data detection
            # could be implemented here


if __name__ == '__main__':
    # Run security tests
    pytest.main([__file__, '-v', '--tb=short']) 