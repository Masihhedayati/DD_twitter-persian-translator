"""
Test Suite for Error Handler Module

Tests comprehensive error handling, categorization, severity determination,
and component health tracking functionality.
"""

import unittest
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from core.error_handler import (
    ErrorHandler, ErrorCategory, ErrorSeverity, ErrorDetails,
    global_error_handler, log_error, get_system_health, safe_execute
)


class TestErrorHandler(unittest.TestCase):
    """Test cases for ErrorHandler class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.error_handler = ErrorHandler()
    
    def test_error_categorization(self):
        """Test automatic error categorization"""
        # API errors
        api_error = ValueError("HTTP 429 rate limit exceeded")
        self.assertEqual(
            self.error_handler.categorize_error(api_error),
            ErrorCategory.RATE_LIMIT_ERROR
        )
        
        # Network errors
        network_error = ConnectionError("Connection timeout")
        self.assertEqual(
            self.error_handler.categorize_error(network_error),
            ErrorCategory.NETWORK_ERROR
        )
        
        # Database errors
        db_error = Exception("SQLite database is locked")
        self.assertEqual(
            self.error_handler.categorize_error(db_error),
            ErrorCategory.DATABASE_ERROR
        )
        
        # Authentication errors
        auth_error = Exception("401 Unauthorized access")
        self.assertEqual(
            self.error_handler.categorize_error(auth_error),
            ErrorCategory.AUTHENTICATION_ERROR
        )
        
        # Unknown errors
        unknown_error = Exception("Something went wrong")
        self.assertEqual(
            self.error_handler.categorize_error(unknown_error),
            ErrorCategory.UNKNOWN_ERROR
        )
    
    def test_severity_determination(self):
        """Test error severity determination"""
        # Critical errors
        critical_error = Exception("Database connection failed")
        severity = self.error_handler.determine_severity(
            ErrorCategory.DATABASE_ERROR, critical_error
        )
        self.assertEqual(severity, ErrorSeverity.CRITICAL)
        
        # High severity errors
        high_error = Exception("Authentication failed")
        severity = self.error_handler.determine_severity(
            ErrorCategory.AUTHENTICATION_ERROR, high_error
        )
        self.assertEqual(severity, ErrorSeverity.HIGH)
        
        # Medium severity errors
        medium_error = Exception("API rate limit exceeded")
        severity = self.error_handler.determine_severity(
            ErrorCategory.RATE_LIMIT_ERROR, medium_error
        )
        self.assertEqual(severity, ErrorSeverity.MEDIUM)
        
        # Low severity errors
        low_error = Exception("File not found")
        severity = self.error_handler.determine_severity(
            ErrorCategory.FILE_SYSTEM_ERROR, low_error
        )
        self.assertEqual(severity, ErrorSeverity.LOW)
    
    def test_error_logging(self):
        """Test comprehensive error logging"""
        exception = ValueError("Test error message")
        context = {"user_id": 123, "operation": "fetch_tweets"}
        
        error_id = self.error_handler.log_error(
            exception, "twitter_client", "get_tweets", context, "Custom message"
        )
        
        # Verify error was logged
        self.assertTrue(error_id.startswith("twitter_client_get_tweets_"))
        self.assertEqual(len(self.error_handler.error_history), 1)
        
        error = self.error_handler.error_history[0]
        self.assertEqual(error.component, "twitter_client")
        self.assertEqual(error.function, "get_tweets")
        self.assertEqual(error.message, "Custom message")
        self.assertEqual(error.exception_type, "ValueError")
        self.assertEqual(error.context, context)
    
    def test_component_health_tracking(self):
        """Test component health status tracking"""
        # Log multiple errors for a component
        for i in range(3):
            exception = Exception(f"Error {i}")
            self.error_handler.log_error(exception, "test_component", "test_function")
            time.sleep(0.01)  # Small delay to ensure different timestamps
        
        # Check component health
        health = self.error_handler.component_health["test_component"]
        self.assertEqual(health["error_count_24h"], 3)
        self.assertEqual(health["status"], "healthy")  # 3 errors is still healthy
        
        # Add more errors to trigger warning status
        for i in range(5):
            exception = Exception(f"Error {i+3}")
            self.error_handler.log_error(exception, "test_component", "test_function")
        
        health = self.error_handler.component_health["test_component"]
        self.assertEqual(health["error_count_24h"], 8)
        self.assertEqual(health["status"], "warning")  # 8 errors triggers warning
    
    def test_error_statistics(self):
        """Test error statistics generation"""
        # Log various errors
        errors = [
            (ValueError("API error"), "api_client", "call_api"),
            (ConnectionError("Network error"), "network", "connect"),
            (Exception("DB error"), "database", "query"),
        ]
        
        for exception, component, function in errors:
            self.error_handler.log_error(exception, component, function)
        
        stats = self.error_handler.get_error_statistics()
        
        # Verify statistics
        self.assertEqual(stats["total_errors"], 3)
        self.assertEqual(stats["errors_24h"], 3)
        self.assertEqual(stats["errors_1h"], 3)
        self.assertGreater(len(stats["errors_by_category"]), 0)
        self.assertGreater(len(stats["errors_by_severity"]), 0)
        self.assertEqual(len(stats["component_health"]), 3)
    
    def test_global_error_handler_functions(self):
        """Test global convenience functions"""
        # Test log_error function
        exception = ValueError("Global test error")
        error_id = log_error(exception, "global_test", "test_function")
        self.assertIsInstance(error_id, str)
        
        # Test get_system_health function
        health = get_system_health()
        self.assertIsInstance(health, dict)
        self.assertIn("total_errors", health)
        self.assertIn("component_health", health)
    
    def test_safe_execute_success(self):
        """Test safe_execute with successful function"""
        def successful_function():
            return "success"
        
        result = safe_execute(successful_function, "fallback", "test_component")
        self.assertEqual(result, "success")
    
    def test_safe_execute_failure(self):
        """Test safe_execute with failing function"""
        def failing_function():
            raise ValueError("Test error")
        
        result = safe_execute(failing_function, "fallback", "test_component")
        self.assertEqual(result, "fallback")
    
    def test_safe_execute_no_logging(self):
        """Test safe_execute with logging disabled"""
        def failing_function():
            raise ValueError("Test error")
        
        initial_count = len(global_error_handler.error_history)
        result = safe_execute(failing_function, "fallback", "test_component", log_errors=False)
        
        self.assertEqual(result, "fallback")
        # Error should not be logged
        self.assertEqual(len(global_error_handler.error_history), initial_count)


class TestErrorIntegration(unittest.TestCase):
    """Integration tests for error handling with existing components"""
    
    def test_error_handler_integration(self):
        """Test error handler integration with mock components"""
        error_handler = ErrorHandler()
        
        # Simulate component errors
        components = ["twitter_client", "media_extractor", "database", "ai_processor"]
        
        for component in components:
            # Simulate different types of errors
            api_error = Exception("API rate limit exceeded")
            error_handler.log_error(api_error, component, "api_call")
            
            network_error = ConnectionError("Network timeout")
            error_handler.log_error(network_error, component, "network_operation")
        
        # Verify all components are tracked
        self.assertEqual(len(error_handler.component_health), len(components))
        
        # Verify error statistics
        stats = error_handler.get_error_statistics()
        self.assertEqual(stats["total_errors"], len(components) * 2)  # 2 errors per component
    
    def test_component_health_status_transitions(self):
        """Test component health status transitions"""
        error_handler = ErrorHandler()
        component = "status_test_component"
        
        # Start healthy
        self.assertNotIn(component, error_handler.component_health)
        
        # Add a few errors (should stay healthy)
        for i in range(3):
            error_handler.log_error(Exception(f"Error {i}"), component, "test")
        
        health = error_handler.component_health[component]
        self.assertEqual(health["status"], "healthy")
        
        # Add more errors to trigger warning
        for i in range(4):  # Total 7 errors
            error_handler.log_error(Exception(f"Error {i+3}"), component, "test")
        
        health = error_handler.component_health[component]
        self.assertEqual(health["status"], "warning")
        
        # Add more errors to trigger degraded
        for i in range(5):  # Total 12 errors
            error_handler.log_error(Exception(f"Error {i+7}"), component, "test")
        
        health = error_handler.component_health[component]
        self.assertEqual(health["status"], "degraded")
        
        # Add more errors to trigger critical
        for i in range(10):  # Total 22 errors
            error_handler.log_error(Exception(f"Error {i+12}"), component, "test")
        
        health = error_handler.component_health[component]
        self.assertEqual(health["status"], "critical")


def run_error_handler_tests():
    """Run all error handler tests"""
    print("🧪 Running Error Handler Tests...")
    
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test cases using TestLoader
    loader = unittest.TestLoader()
    test_suite.addTest(loader.loadTestsFromTestCase(TestErrorHandler))
    test_suite.addTest(loader.loadTestsFromTestCase(TestErrorIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Print summary
    total_tests = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    success_rate = ((total_tests - failures - errors) / total_tests * 100) if total_tests > 0 else 0
    
    print(f"\n📊 Error Handler Test Results:")
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {total_tests - failures - errors}")
    print(f"Failed: {failures}")
    print(f"Errors: {errors}")
    print(f"Success Rate: {success_rate:.1f}%")
    
    if failures == 0 and errors == 0:
        print("✅ All error handler tests passed!")
        return True
    else:
        print("❌ Some error handler tests failed!")
        return False


if __name__ == "__main__":
    run_error_handler_tests() 